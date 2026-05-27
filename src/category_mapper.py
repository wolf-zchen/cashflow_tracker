"""
Category Mapper - Auto-standardize categories during import

Learns from your existing categories and automatically maps similar
categories to prevent duplicates.
"""
from pathlib import Path
import json
from difflib import SequenceMatcher


class CategoryMapper:
    """Automatically map categories to standardized names"""

    def __init__(self, mappings_file="data/category_mappings.json"):
        self.mappings_file = Path(mappings_file)
        self.mappings = self._load_mappings()
        self.auto_learned_mappings = {}

    def _load_mappings(self):
        """Load category mappings from file"""
        if self.mappings_file.exists():
            with open(self.mappings_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_mappings(self):
        """Save category mappings to file"""
        self.mappings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.mappings_file, 'w') as f:
            json.dump(self.mappings, f, indent=2)

    def add_mapping(self, from_category, to_category):
        """
        Add a manual category mapping

        Args:
            from_category: Original category name
            to_category: Standardized category name
        """
        self.mappings[from_category] = to_category
        self._save_mappings()

    def remove_mapping(self, from_category):
        """Remove a category mapping"""
        if from_category in self.mappings:
            del self.mappings[from_category]
            self._save_mappings()
            return True
        return False

    def get_all_mappings(self):
        """Get all category mappings"""
        return self.mappings.copy()

    def similarity(self, str1, str2):
        """Calculate similarity between two strings (0-1)"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def learn_from_database(self, db_manager):
        """
        Learn category mappings from existing database

        Analyzes existing categories to create smart mappings for:
        - Capitalization differences
        - Hyphenated variations
        - Common prefixes/suffixes
        """
        conn = db_manager.get_connection()
        cursor = conn.cursor()

        # Get all unique categories with counts
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM transactions
            WHERE category IS NOT NULL AND category != 'Uncategorized'
            GROUP BY category
            ORDER BY count DESC
        """)

        categories = cursor.fetchall()

        # Build mapping rules based on existing data
        learned = {}
        canonical_categories = {}  # category_lower -> most_common_version

        # First pass: identify canonical versions (most common spelling)
        for cat in categories:
            cat_name = cat['category']
            cat_lower = cat_name.lower()

            if cat_lower not in canonical_categories:
                canonical_categories[cat_lower] = cat_name
            else:
                # Keep the version with more transactions
                existing = canonical_categories[cat_lower]
                cursor.execute(
                    "SELECT COUNT(*) as count FROM transactions WHERE category = ?",
                    (existing,)
                )
                existing_count = cursor.fetchone()['count']

                if cat['count'] > existing_count:
                    canonical_categories[cat_lower] = cat_name

        # Second pass: create mappings for variations
        for cat in categories:
            cat_name = cat['category']
            cat_lower = cat_name.lower()
            canonical = canonical_categories[cat_lower]

            if cat_name != canonical:
                learned[cat_name] = canonical

        # Third pass: find similar categories (fuzzy matching)
        category_names = [cat['category'] for cat in categories]

        for i, cat1 in enumerate(category_names):
            if cat1 in learned:
                continue  # Already mapped

            for cat2 in category_names[:i]:  # Only check against earlier categories
                if cat2 in learned:
                    continue

                # Check similarity
                sim = self.similarity(cat1, cat2)

                # If very similar (>0.8), map to the more common one
                if sim > 0.8 and cat1 != cat2:
                    # Determine which is more common
                    cursor.execute(
                        "SELECT COUNT(*) as count FROM transactions WHERE category = ?",
                        (cat1,)
                    )
                    count1 = cursor.fetchone()['count']

                    cursor.execute(
                        "SELECT COUNT(*) as count FROM transactions WHERE category = ?",
                        (cat2,)
                    )
                    count2 = cursor.fetchone()['count']

                    if count1 > count2:
                        learned[cat2] = cat1
                    else:
                        learned[cat1] = cat2

                    break

        # Fourth pass: handle common patterns
        # Map hyphenated categories to their base
        for cat_name in category_names:
            if '-' in cat_name and cat_name not in learned:
                # "Restaurant-Bar & Café" -> "Restaurant" or "Restaurants"
                base = cat_name.split('-')[0].strip()

                # Find if base or plural exists
                for potential in [base, base + 's']:
                    if potential in category_names and potential != cat_name:
                        cursor.execute(
                            "SELECT COUNT(*) as count FROM transactions WHERE category = ?",
                            (potential,)
                        )
                        if cursor.fetchone()['count'] > 0:
                            learned[cat_name] = potential
                            break

        self.auto_learned_mappings = learned
        return learned

    def map_category(self, category, existing_categories=None):
        """
        Map a category to its standardized version

        Args:
            category: Category to map
            existing_categories: List of existing categories in database

        Returns:
            Standardized category name
        """
        if not category or category == 'Uncategorized':
            return category

        # Check exact mapping first
        if category in self.mappings:
            return self.mappings[category]

        # Check auto-learned mappings
        if category in self.auto_learned_mappings:
            return self.auto_learned_mappings[category]

        # If we have existing categories, try fuzzy matching
        if existing_categories:
            # Check for exact match (case-insensitive)
            for existing in existing_categories:
                if category.lower() == existing.lower():
                    return existing  # Return existing capitalization

            # Check for very similar matches
            best_match = None
            best_similarity = 0.85  # Threshold

            for existing in existing_categories:
                sim = self.similarity(category, existing)
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = existing

            if best_match:
                # Auto-learn this mapping for future
                self.auto_learned_mappings[category] = best_match
                return best_match

        # No mapping found, return original
        return category

    def bulk_map_categories(self, categories, existing_categories=None):
        """
        Map multiple categories at once

        Args:
            categories: List of category names
            existing_categories: List of existing categories in database

        Returns:
            Dictionary mapping original -> standardized
        """
        result = {}
        for cat in categories:
            result[cat] = self.map_category(cat, existing_categories)
        return result

    def apply_to_transactions(self, transactions, existing_categories=None):
        """
        Apply category mapping to a list of transaction dictionaries

        Args:
            transactions: List of transaction dicts
            existing_categories: List of existing categories

        Returns:
            List of transactions with mapped categories
        """
        for txn in transactions:
            if 'category' in txn:
                txn['category'] = self.map_category(txn['category'], existing_categories)

        return transactions

    def get_mapping_stats(self):
        """Get statistics about current mappings"""
        return {
            'manual_mappings': len(self.mappings),
            'auto_learned_mappings': len(self.auto_learned_mappings),
            'total_mappings': len(self.mappings) + len(self.auto_learned_mappings)
        }