"""
Parser for Monarch Money CSV exports.

Monarch exports all accounts in one file with columns:
  Date, Merchant, Category, Account, Original Statement, Notes, Amount, Tags, Owner, Business Entity

Amounts are pre-signed: negative = expense, positive = income/credit.
Each row carries its own account name (last 4 digits included).
"""
import pandas as pd
from pathlib import Path
from typing import List
import json
import re

from .base_parser import BaseParser
from ..models import Transaction


# Map Monarch categories → app categories
CATEGORY_MAP = {
    'Auto Maintenance':           'Transportation',
    'Auto Payment':               'Transportation',
    'Book & Learning':            'Education',
    'Cash & ATM':                 'Transfer',
    'Child Activities':           'Entertainment',
    'Clothing':                   'Shopping',
    'Credit Card Payment':        'Credit Card Payment',
    'Dentist':                    'Healthcare',
    'Education':                  'Education',
    'Electronics':                'Shopping',
    'Entertainment & Recreation': 'Entertainment',
    'Financial & Legal Services': 'Banking Fees',
    'Financial Fees':             'Banking Fees',
    'Fitness':                    'Fitness & Wellness',
    'Furniture & Housewares':     'Shopping',
    'Gaming':                     'Entertainment',
    'Gas':                        'Transportation',
    'Gas & Electric':             'Bills & Utilities',
    'Gifts':                      'Gifts & Donations',
    'Groceries':                  'Groceries',
    'HOA fees':                   'Housing',
    'Home Improvement':           'Housing',
    'Insurance':                  'Bills & Utilities',
    'Interest':                   'Banking Fees',
    'Internet & Cable':           'Bills & Utilities',
    'Loan Repayment':             'Transfer',
    'Medical':                    'Healthcare',
    'Miscellaneous':              'Uncategorized',
    'Other Income':               'Uncategorized',
    'Parking & Tolls':            'Transportation',
    'Paychecks':                  'Uncategorized',
    'Personal':                   'Personal',
    'Phone':                      'Bills & Utilities',
    'Plants':                     'Shopping',
    'Postage & Shipping':         'Shopping',
    'Public Transit':             'Transportation',
    'Rent':                       'Housing',
    'Restaurants & Bars':         'Restaurants',
    'Shopping':                   'Shopping',
    'Subscription':               'Bills & Utilities',
    'Taxes':                      'Banking Fees',
    'Taxi & Ride Shares':         'Transportation',
    'Transfer':                   'Transfer',
    'Travel & Vacation':          'Travel',
    'Uncategorized':              'Uncategorized',
}

# Monarch account name → clean display name
# Pattern: strip the trailing " (...XXXX)" and identify the institution
def _clean_account_name(monarch_name: str) -> str:
    """Convert Monarch account name to a clean display name.

    Examples:
        'CREDIT CARD (...4459)'                               → 'Chase Credit *4459'
        'CHASE COLLEGE (...9506)'                             → 'Chase Checking *9506'
        'Blue Cash Preferred® (...2003)'                      → 'Amex Blue Cash *2003'
        'Customized Cash Rewards World Mastercard Card (...0424)' → 'BofA Cash Rewards *0424'
        'Discover it Card (...4351)'                          → 'Discover *4351'
        'Robinhood Credit Card (...7283)'                     → 'Robinhood *7283'
        '360 Performance Savings (...2691)'                   → 'Capital One 360 *2691'
        'High Yield Savings Account (...8502)'                → 'High Yield Savings *8502'
        'ONLINE SAVINGS (...1627)'                            → 'Online Savings *1627'
        'CASHBACK DEBIT (...2591)'                            → 'Discover Cashback *2591'
    """
    m = re.search(r'\(\.\.\.(\d+)\)', monarch_name)
    last4 = m.group(1) if m else ''
    name_lower = monarch_name.lower()

    if 'chase college' in name_lower or 'chase' in name_lower and 'college' in name_lower:
        return f'Chase Checking *{last4}'
    if 'credit card' in name_lower and last4 in ('4370', '4459', '2966', '6699', '1129'):
        return f'Chase Credit *{last4}'
    if 'blue cash' in name_lower or 'amex' in name_lower:
        return f'Amex Blue Cash *{last4}'
    if 'customized cash rewards' in name_lower or 'mastercard' in name_lower and 'bank' not in name_lower:
        return f'BofA Cash Rewards *{last4}'
    if 'bankamericard' in name_lower or 'bankamerica' in name_lower:
        return f'BofA Credit *{last4}'
    if 'discover it' in name_lower:
        return f'Discover *{last4}'
    if 'cashback debit' in name_lower:
        return f'Discover Cashback *{last4}'
    if 'robinhood' in name_lower:
        return f'Robinhood *{last4}'
    if '360 performance' in name_lower or 'capital one' in name_lower:
        return f'Capital One 360 *{last4}'
    if 'high yield savings' in name_lower:
        return f'High Yield Savings *{last4}'
    if 'online savings' in name_lower:
        return f'Online Savings *{last4}'
    # Generic fallback: strip parenthetical and tidy up
    clean = re.sub(r'\s*\(\.\.\.\d+\)', '', monarch_name).strip()
    return f'{clean} *{last4}' if last4 else clean


def _account_type(monarch_name: str) -> str:
    name_lower = monarch_name.lower()
    if any(k in name_lower for k in ('savings', 'debit', 'checking', 'college')):
        return 'checking'
    return 'credit_card'


def _institution(monarch_name: str) -> str:
    name_lower = monarch_name.lower()
    if 'chase' in name_lower or 'credit card' in name_lower:
        return 'Chase'
    if 'blue cash' in name_lower or 'amex' in name_lower:
        return 'American Express'
    if 'customized cash' in name_lower or 'bankamericard' in name_lower:
        return 'Bank of America'
    if 'discover' in name_lower or 'cashback debit' in name_lower:
        return 'Discover'
    if 'robinhood' in name_lower:
        return 'Robinhood'
    if '360 performance' in name_lower or 'capital one' in name_lower:
        return 'Capital One'
    if 'high yield' in name_lower or 'online savings' in name_lower:
        return 'Savings'
    return 'Unknown'


class MonarchParser(BaseParser):
    """Parser for Monarch Money CSV exports (all accounts in one file)."""

    EXPECTED_COLUMNS = ['Date', 'Merchant', 'Category', 'Account',
                        'Original Statement', 'Amount']

    def __init__(self):
        super().__init__(institution='Monarch', account_type='mixed')

    def get_account_name(self, file_path: Path) -> str:
        # Account names come per-row from the CSV, not from the filename.
        # Return a generic label; the actual per-row name is set in parse().
        return 'Monarch Export'

    def detect(self, file_path: Path) -> bool:
        """Detect if this is a Monarch Money CSV export."""
        try:
            if file_path.suffix.lower() != '.csv':
                return False
            # Use utf-8-sig to handle BOM that Monarch sometimes adds
            df = pd.read_csv(file_path, nrows=0, encoding='utf-8-sig')
            columns = df.columns.tolist()
            return all(col in columns for col in self.EXPECTED_COLUMNS)
        except Exception:
            return False

    def parse(self, file_path: Path, account_name: str) -> List[Transaction]:
        """Parse a Monarch Money CSV export into transactions."""
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        transactions = []

        for _, row in df.iterrows():
            if row.isna().all():
                continue
            if pd.isna(row['Date']) or pd.isna(row['Amount']):
                continue

            try:
                date = self._parse_date(str(row['Date']))
            except Exception:
                continue

            try:
                amount = float(row['Amount'])
            except (ValueError, TypeError):
                continue

            # Use Original Statement as description (richer than Merchant)
            description = str(row['Original Statement']).strip()
            if not description or description == 'nan':
                description = str(row['Merchant']).strip()

            monarch_account = str(row['Account']).strip() if pd.notna(row['Account']) else ''
            clean_acct = _clean_account_name(monarch_account) if monarch_account else account_name

            monarch_category = str(row['Category']).strip() if pd.notna(row['Category']) else ''
            mapped_category = CATEGORY_MAP.get(monarch_category, monarch_category or 'Uncategorized')

            # Monarch tags (pipe-separated) → our tags field
            tags = str(row['Tags']).strip() if pd.notna(row.get('Tags')) else None
            if tags == 'nan':
                tags = None

            notes = str(row['Notes']).strip() if pd.notna(row.get('Notes')) else None
            if notes == 'nan':
                notes = None

            transaction = Transaction(
                date=date,
                description=description,
                amount=amount,        # already signed correctly
                account_name=clean_acct,
                account_type=_account_type(monarch_account),
                institution=_institution(monarch_account),
                category=mapped_category,
                raw_data=json.dumps({
                    'merchant': str(row['Merchant']),
                    'monarch_category': monarch_category,
                    'monarch_account': monarch_account,
                    'owner': str(row.get('Owner', '')),
                }, ensure_ascii=False),
                notes=notes,
            )
            transactions.append(transaction)

        return transactions
