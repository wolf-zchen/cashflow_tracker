"""
Learned Categorization Rules

Manages learned rules that are saved between sessions.
"""
import json
from pathlib import Path
from typing import Dict, List, Set


class LearnedRules:
    """Manages user-learned categorization rules"""
    
    def __init__(self, rules_file: str = "data/learned_rules.json"):
        self.rules_file = Path(rules_file)
        self.rules = self._load_rules()
        self.pending_suggestions = []  # Track suggestions during session
    
    def _load_rules(self) -> Dict[str, List[str]]:
        """Load learned rules from file"""
        if self.rules_file.exists():
            try:
                with open(self.rules_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_rules(self):
        """Save learned rules to file"""
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.rules_file, 'w') as f:
            json.dump(self.rules, f, indent=2)
    
    def add_rule(self, category: str, keyword: str):
        """Add a learned rule"""
        if category not in self.rules:
            self.rules[category] = []
        
        keyword_upper = keyword.upper()
        if keyword_upper not in self.rules[category]:
            self.rules[category].append(keyword_upper)
            self._save_rules()
            return True
        return False
    
    def get_keywords_for_category(self, category: str) -> List[str]:
        """Get all learned keywords for a category"""
        return self.rules.get(category, [])
    
    def get_all_rules(self) -> Dict[str, List[str]]:
        """Get all learned rules"""
        return self.rules
    
    def categorize(self, description: str, existing_category: str = None) -> str:
        """
        Try to categorize using learned rules
        
        Returns category if match found, otherwise returns existing_category
        """
        description_upper = description.upper()
        
        for category, keywords in self.rules.items():
            for keyword in keywords:
                if keyword in description_upper:
                    return category
        
        return existing_category if existing_category else 'Uncategorized'
    
    def extract_keywords(self, description: str) -> Set[str]:
        """
        Extract potential keywords from a description
        
        Focuses on merchant names, ignores:
        - Numbers/IDs
        - Addresses
        - Common payment terms
        
        Returns unique meaningful words
        """
        # Remove common useless patterns
        stopwords = {
            # Generic payment terms
            'THE', 'AND', 'FOR', 'WITH', 'FROM', 'THIS', 'THAT',
            'PAYMENT', 'PURCHASE', 'SALE', 'TRANSACTION', 'POS',
            'DEBIT', 'CREDIT', 'ACH', 'CHECK', 'WITHDRAWAL', 'DEPOSIT',
            
            # Corporate suffixes
            'INC', 'LLC', 'CORP', 'LTD', 'CO', 'COMPANY',
            
            # Common locations (too generic)
            'USA', 'US', 'CHICAGO', 'NEW', 'YORK', 'ANGELES',
            
            # Payment processors
            'SQ', 'TST', 'PAYPAL', 'VENMO', 'ZELLE',
            
            # Dates/times
            'AM', 'PM', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN',
            
            # Generic words
            'ONLINE', 'STORE', 'SHOP', 'MARKET', 'CENTER', 'SERVICE'
        }
        
        # Common patterns to remove entirely
        import re
        
        # Remove patterns
        desc = description.upper()
        
        # Remove dates (MM/DD, MM/DD/YY, etc.)
        desc = re.sub(r'\d{1,2}/\d{1,2}(/\d{2,4})?', '', desc)
        
        # Remove standalone numbers and IDs BEFORE splitting
        desc = re.sub(r'\s+\d+\s+', ' ', desc)  # " 10572 " → " "
        desc = re.sub(r'#\d+', '', desc)  # "#123" → ""
        desc = re.sub(r'\*\d+', '', desc)  # "*4567" → ""

        # Remove reference numbers (patterns like #123, *123, etc.)
        desc = re.sub(r'[#*]\w+', '', desc)  # More aggressive

        # Remove credit card last 4 digits patterns
        desc = re.sub(r'\*\d{4}', '', desc)

        # Remove website patterns
        desc = re.sub(r'\.COM|\.NET|\.ORG|\.CO/', '', desc)

        # Remove state codes at end (e.g., "IL", "CA", "NY")
        desc = re.sub(r'\s+[A-Z]{2}\s*$', ' ', desc)

        # Remove "PPD ID:" patterns
        desc = re.sub(r'PPD ID:\s*\w+', '', desc)
        desc = re.sub(r'WEB ID:\s*\w+', '', desc)

        # Remove trailing hyphens and extra spaces
        desc = re.sub(r'\s*-\s*', ' ', desc)
        desc = re.sub(r'\s+', ' ', desc).strip()

        # Split and clean
        words = desc.split()
        keywords = set()

        for word in words:
            # Remove special characters, keep only alphanumeric
            clean = ''.join(c for c in word if c.isalnum())

            # Skip if:
            # - Too short (< 3 chars)
            # - Is a stopword
            # - Is all numbers
            # - Contains mostly numbers (>50%)
            # - Ends with numbers followed by letters (like "3376CHICAGO")
            if (len(clean) >= 3 and
                clean not in stopwords and
                not clean.isdigit()):

                # Check if it's mixed number-letter (like "3376CHICAGO")
                # Split if it starts with 3+ digits followed by letters
                number_letter_match = re.match(r'^(\d{3,})([A-Z]{3,})', clean)
                if number_letter_match:
                    # Keep only the letter part
                    letter_part = number_letter_match.group(2)
                    if letter_part not in stopwords:
                        keywords.add(letter_part)
                # Check if mostly digits
                elif sum(c.isdigit() for c in clean) / len(clean) < 0.5:
                    keywords.add(clean)

        return keywords

    def suggest_rule(self, description: str, category: str) -> str:
        """
        Suggest the BEST keyword to add as a rule

        Prioritizes:
        1. FIRST words in description (merchant names ALWAYS come first!)
        2. Longer words (more specific, but secondary to position)
        3. Avoids generic terms

        Returns the suggested keyword or None
        """
        keywords = self.extract_keywords(description)

        if not keywords:
            return None

        # Split description to find word positions
        description_words = description.upper().split()

        # Score keywords based on:
        # 1. Position (HEAVILY weighted - position 0 is almost always the merchant!)
        # 2. Length (longer = more specific, but much less important)
        scored_keywords = []

        for keyword in keywords:
            # Find position in original description
            try:
                position = next(i for i, word in enumerate(description_words)
                              if keyword in word.upper())
            except StopIteration:
                position = 99  # Not found, low priority

            # NEW Scoring strategy:
            # - Position weight: -100 per position (position 0 >> position 3)
            # - Length weight: +2 per character (minor bonus for specificity)
            #
            # Example: "UFC STORE JACKSONVILLE FL"
            #   UFC (pos 0, len 3):          score = 6 + (0 × -100) = 6
            #   STORE (pos 1, len 5):        score = 10 + (1 × -100) = -90
            #   JACKSONVILLE (pos 2, len 12): score = 24 + (2 × -100) = -176
            # Winner: UFC! ✅

            score = (len(keyword) * 2) - (position * 100)

            scored_keywords.append((keyword, score, position))

        # Sort by score (descending)
        scored_keywords.sort(key=lambda x: x[1], reverse=True)

        # Return the best keyword
        if scored_keywords:
            best_keyword = scored_keywords[0][0]

            # Safety check: if best is a common location despite being first, try second-best
            common_locations = {
                'CHICAGO', 'NEW', 'YORK', 'LOS', 'ANGELES', 'SAN',
                'FRANCISCO', 'MIAMI', 'BOSTON', 'SEATTLE', 'DENVER',
                'ATLANTA', 'DALLAS', 'HOUSTON', 'PHILADELPHIA', 'JACKSONVILLE'
            }

            if best_keyword in common_locations and len(scored_keywords) > 1:
                # Use second-best if first is a common city
                return scored_keywords[1][0]

            return best_keyword

        return None

    def add_suggestion(self, description: str, category: str):
        """Track a suggestion for later review"""
        keyword = self.suggest_rule(description, category)
        if keyword:
            self.pending_suggestions.append({
                'description': description,
                'category': category,
                'keyword': keyword
            })

    def get_pending_suggestions(self) -> List[Dict]:
        """Get all pending suggestions"""
        return self.pending_suggestions

    def clear_suggestions(self):
        """Clear pending suggestions"""
        self.pending_suggestions = []

    def delete_rule(self, category: str, keyword: str) -> bool:
        """Delete a learned rule"""
        if category in self.rules:
            keyword_upper = keyword.upper()
            if keyword_upper in self.rules[category]:
                self.rules[category].remove(keyword_upper)
                if not self.rules[category]:
                    del self.rules[category]
                self._save_rules()
                return True
        return False

    def rule_count(self) -> int:
        """Get total number of learned rules"""
        return sum(len(keywords) for keywords in self.rules.values())