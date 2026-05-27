"""
Automatic transaction categorization system

This module provides rule-based automatic categorization of transactions.
You can customize the rules to match your spending patterns.
"""
import re
from typing import Optional, Dict, List


class Categorizer:
    """Categorizes transactions based on merchant/description keywords"""

    # Define your categorization rules
    # Format: 'Category Name': ['keyword1', 'keyword2', ...]
    RULES = {
        # Food & Dining
        'Groceries': [
            'WHOLE FOODS', 'TRADER JOE', 'SAFEWAY', 'COSTCO',
            'WALMART', 'TARGET', 'ALDI', 'KROGER', 'PUBLIX',
            'H MART', 'JEWEL', '88 MARKETPLACE', 'GROCERY'
        ],

        'Restaurants': [
            'RESTAURANT', 'CAFE', 'COFFEE', 'STARBUCKS',
            'MCDONALD', 'CHIPOTLE', 'PANERA', 'SUBWAY',
            'PIZZA', 'BURGER', 'GONG DONG TOFU', 'SQ *',
            'DOORDASH', 'UBER EATS', 'GRUBHUB'
        ],

        # Transportation
        'Transportation': [
            'UBER', 'LYFT', 'TAXI', 'SHELL', 'CHEVRON', 'BP ',
            'EXXON', 'MOBIL', 'GAS STATION', 'PARKING',
            'TOLLWAY', 'TOLL', 'TRANSIT', 'METRO'
        ],

        # Shopping
        'Shopping': [
            'AMAZON', 'EBAY', 'ETSY', 'TARGET', 'WALMART',
            'BEST BUY', 'APPLE STORE', 'MACYS', 'NORDSTROM',
            'GOODWILL', 'STUDIOTHREE'
        ],

        # Entertainment & Subscriptions
        'Entertainment': [
            'NETFLIX', 'SPOTIFY', 'HULU', 'DISNEY',
            'HBO', 'YOUTUBE', 'MOVIE', 'THEATER',
            'CONCERT', 'TICKET', 'MUSIC', 'GAMING',
            'STEAM', 'PLAYSTATION', 'XBOX'
        ],

        # Bills & Utilities
        'Bills & Utilities': [
            'ATT', 'VERIZON', 'T-MOBILE', 'COMCAST', 'XFINITY',
            'ELECTRIC', 'GAS COMPANY', 'WATER', 'INTERNET',
            'PHONE', 'CABLE', 'UTILITY'
        ],

        # Housing
        'Housing': [
            'RENT', 'MORTGAGE', 'PROPRTYPAY', 'PROPERTY',
            'HOA', 'LANDLORD', 'APARTMENT'
        ],

        # Education
        'Education': [
            'ACADEMY', 'SCHOOL', 'TUITION', 'COURSE',
            'UDEMY', 'COURSERA', 'LAKESHORE ACADEMY',
            'UNIVERSITY', 'COLLEGE'
        ],

        # Healthcare
        'Healthcare': [
            'PHARMACY', 'CVS', 'WALGREENS', 'DOCTOR',
            'HOSPITAL', 'MEDICAL', 'DENTAL', 'CLINIC',
            'HEALTH', 'URGENT CARE'
        ],

        # Banking & Fees
        'Banking Fees': [
            'OFFICIAL CHECKS', 'WIRE FEE', 'ATM FEE',
            'OVERDRAFT', 'MONTHLY FEE', 'SERVICE CHARGE',
            'ANNUAL FEE'
        ],

        # Transfers & Payments
        'Transfer': [
            'TRANSFER', 'WITHDRAWAL', 'ZELLE', 'VENMO',
            'PAYPAL', 'CASH APP', 'ACH'
        ],

        # Investments
        'Investment': [
            'ROBINHOOD', 'VANGUARD', 'FIDELITY', 'SCHWAB',
            'ILD529', '529', 'INVESTMENT', 'BROKERAGE',
            'ETRADE', 'WEBULL'
        ],

        # Credit Card Payments
        'Credit Card Payment': [
            'AMERICAN EXPRESS', 'CHASE CREDIT', 'PAYMENT',
            'AUTOPAY', 'CREDIT CARD', 'CARD PAYMENT'
        ],

        # Personal Care
        'Personal Care': [
            'SALON', 'HAIRCUT', 'SPA', 'BARBER',
            'MASSAGE', 'NAIL', 'BEAUTY'
        ],

        # Travel
        'Travel': [
            'AIRLINE', 'HOTEL', 'AIRBNB', 'BOOKING',
            'EXPEDIA', 'FLIGHT', 'VACATION',
            'TSA', 'AIRPORT'
        ],

        # Gifts & Donations
        'Gifts & Donations': [
            'CHARITY', 'DONATION', 'NONPROFIT',
            'CHURCH', 'GOFUNDME', 'GIFT'
        ],
    }

    # Bank category mappings (map bank categories to your categories)
    BANK_CATEGORY_MAPPING = {
        'Food & Drink': 'Restaurants',
        'Merchandise & Supplies-Groceries': 'Groceries',
        'Merchandise & Supplies-Internet Purchase': 'Shopping',
        'Gas': 'Transportation',
        'Travel': 'Travel',
        'Entertainment': 'Entertainment',
        'Health & Wellness': 'Healthcare',
        'Education': 'Education',
        'Home': 'Housing',
        'Gifts & Donations': 'Gifts & Donations',
        'Bills & Utilities': 'Bills & Utilities',
        'Shopping': 'Shopping',
    }

    @classmethod
    def categorize(cls, description: str, existing_category: str = None) -> str:
        """
        Categorize a transaction based on description.

        Args:
            description: Transaction description
            existing_category: Category from bank (if available)

        Returns:
            Category name
        """
        # If already categorized by bank (and not generic), map it
        if existing_category and existing_category not in ['Uncategorized', 'Other', '']:
            mapped = cls.BANK_CATEGORY_MAPPING.get(existing_category, existing_category)
            if mapped != 'Uncategorized':
                return mapped

        # Check against our keyword rules
        description_upper = description.upper()

        for category, keywords in cls.RULES.items():
            for keyword in keywords:
                if keyword.upper() in description_upper:
                    return category

        # If no match, return existing or uncategorized
        return existing_category if existing_category else 'Uncategorized'

    @classmethod
    def categorize_all(cls, db_manager, overwrite_existing=False):
        """
        Categorize all transactions in the database.

        Args:
            db_manager: DatabaseManager instance
            overwrite_existing: If True, re-categorize even already categorized transactions

        Returns:
            Dictionary with categorization stats
        """
        conn = db_manager.get_connection()
        cursor = conn.cursor()

        # Get transactions to categorize
        if overwrite_existing:
            cursor.execute("SELECT id, description, category, amount FROM transactions")
        else:
            cursor.execute("""
                SELECT id, description, category, amount
                FROM transactions 
                WHERE category = 'Uncategorized' OR category IS NULL
            """)

        transactions = cursor.fetchall()

        stats = {
            'total_processed': 0,
            'updated': 0,
            'already_categorized': 0,
            'by_category': {}
        }

        # Import transfer patterns to check first
        import re
        TRANSFER_PATTERNS = [
            r'CHASE.*CREDIT.*AUTOPAY',
            r'CHASE.*PAYMENT',
            r'AMERICAN EXPRESS.*PMT',
            r'AMERICAN EXPRESS.*PAYMENT',
            r'AMEX.*PAYMENT',
            r'ONLINE PAYMENT.*THANK YOU',
            r'MOBILE PAYMENT.*THANK YOU',
            r'CREDIT CARD PAYMENT',
            r'CARD PAYMENT',
            r'AUTOPAY',
            r'TRANSFER',
            r'ROBINHOOD.*CREDITS',
            r'ZELLE',
            r'VENMO',
            r'ILD529',
        ]

        for txn in transactions:
            stats['total_processed'] += 1

            # First check if it's a transfer/payment
            is_transfer = False
            desc_upper = txn['description'].upper()

            for pattern in TRANSFER_PATTERNS:
                if re.search(pattern, desc_upper):
                    is_transfer = True
                    break

            # Determine category
            if is_transfer:
                new_category = 'Credit Card Payment' if 'PAYMENT' in desc_upper or 'PMT' in desc_upper else 'Transfer'
            else:
                # Use regular categorization
                new_category = cls.categorize(txn['description'], txn['category'])

            # Determine transaction_type from category and amount
            if new_category in ('Credit Card Payment', 'Transfer', 'Investment') or is_transfer:
                new_type = 'transfer'
            elif txn['amount'] > 0:
                new_type = 'income'
            else:
                new_type = 'expense'

            if new_category != txn['category']:
                cursor.execute(
                    "UPDATE transactions SET category = ?, transaction_type = ? WHERE id = ?",
                    (new_category, new_type, txn['id'])
                )
                stats['updated'] += 1
                stats['by_category'][new_category] = stats['by_category'].get(new_category, 0) + 1
            else:
                # Category unchanged but still update type if NULL
                cursor.execute(
                    "UPDATE transactions SET transaction_type = ? WHERE id = ? AND transaction_type IS NULL",
                    (new_type, txn['id'])
                )
                stats['already_categorized'] += 1

        conn.commit()
        return stats

    @classmethod
    def add_rule(cls, category: str, keyword: str):
        """
        Add a new keyword rule (runtime only, not persisted)

        Args:
            category: Category name
            keyword: Keyword to match
        """
        if category not in cls.RULES:
            cls.RULES[category] = []

        if keyword not in cls.RULES[category]:
            cls.RULES[category].append(keyword)

    @classmethod
    def get_rules_for_category(cls, category: str) -> List[str]:
        """Get all keywords for a category"""
        return cls.RULES.get(category, [])

    @classmethod
    def get_all_categories(cls) -> List[str]:
        """Get list of all categories with rules"""
        return list(cls.RULES.keys())