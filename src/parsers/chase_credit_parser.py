"""
Parser for Chase credit card CSV files.
"""
import pandas as pd
from pathlib import Path
from typing import List
import json

from .base_parser import BaseParser
from ..models import Transaction


class ChaseCreditParser(BaseParser):
    """Parser for Chase credit card CSV files"""
    
    EXPECTED_COLUMNS = [
        'Transaction Date', 'Post Date', 'Description', 
        'Category', 'Type', 'Amount', 'Memo'
    ]
    
    def __init__(self):
        super().__init__(institution='Chase', account_type='credit_card')

    def get_account_name(self, file_path: Path) -> str:
        import re
        stem = file_path.stem
        match = re.search(r'[Cc]hase(\d{4})', stem)
        if match:
            return f"Chase Credit *{match.group(1)}"
        return "Chase Credit Card"

    def detect(self, file_path: Path) -> bool:
        """Detect if this is a Chase credit card CSV"""
        try:
            df = pd.read_csv(file_path, nrows=0)
            columns = df.columns.tolist()
            return all(col in columns for col in self.EXPECTED_COLUMNS)
        except:
            return False
    
    def parse(self, file_path: Path, account_name: str) -> List[Transaction]:
        """Parse Chase credit card CSV"""
        df = pd.read_csv(file_path)
        transactions = []

        for _, row in df.iterrows():
            # Skip if all values are NaN
            if row.isna().all():
                continue

            # Parse date (use Transaction Date as primary)
            date = self._parse_date(row['Transaction Date'])

            # Parse amount. Chase exports use the `Type` column to distinguish
            # charges from refunds/payments rather than sign alone. We normalize
            # everything to: expenses negative, refunds/income positive.
            raw_amount = self._parse_amount(row['Amount'])
            txn_type = str(row.get('Type', '')).strip().lower() if 'Type' in row else ''

            if txn_type == 'sale':
                # Charge → expense (negative)
                amount = -abs(raw_amount)
            elif txn_type in ('return', 'refund', 'adjustment', 'reimbursement'):
                # Money back on the card → income/refund (positive)
                amount = abs(raw_amount)
            elif txn_type == 'payment':
                # Payment to the card → leave sign as-is from CSV (Chase exports
                # these as negative). Will be reclassified as 'transfer' later.
                amount = -abs(raw_amount) if raw_amount > 0 else raw_amount
            elif txn_type == 'fee':
                # Fees are expenses
                amount = -abs(raw_amount)
            else:
                # Fallback: original behavior (flip sign). Better than nothing
                # if a future Chase export changes the Type vocabulary.
                amount = -raw_amount
            
            # Create transaction
            transaction = Transaction(
                date=date,
                description=row['Description'],
                amount=amount,
                account_name=account_name,
                account_type=self.account_type,
                institution=self.institution,
                category=row['Category'] if pd.notna(row['Category']) else 'Uncategorized',
                raw_data=json.dumps(row.to_dict()),
                notes=row['Memo'] if pd.notna(row['Memo']) else None
            )
            
            transactions.append(transaction)
        
        return transactions
