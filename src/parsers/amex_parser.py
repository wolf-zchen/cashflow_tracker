"""
Parser for American Express Excel files.
"""
import pandas as pd
from pathlib import Path
from typing import List
import json

from .base_parser import BaseParser
from ..models import Transaction


class AmexParser(BaseParser):
    """Parser for American Express Excel files"""
    
    EXPECTED_COLUMNS = [
        'Date', 'Description', 'Card Member', 'Account #', 'Amount'
    ]
    
    def __init__(self):
        super().__init__(institution='American Express', account_type='credit_card')

    def get_account_name(self, file_path: Path) -> str:
        import re
        try:
            df = pd.read_excel(file_path, skiprows=6, nrows=1)
            if 'Account #' in df.columns:
                acct = str(df['Account #'].iloc[0])
                digits = re.sub(r'\D', '', acct)
                if len(digits) >= 5:
                    return f"Amex *{digits[-5:]}"
                elif digits:
                    return f"Amex *{digits}"
        except Exception:
            pass
        return "American Express"

    def detect(self, file_path: Path) -> bool:
        """Detect if this is an Amex Excel file"""
        try:
            # Check if it's an Excel file
            if file_path.suffix.lower() not in ['.xlsx', '.xls']:
                return False
            
            # Try reading with skiprows to find the header
            df = pd.read_excel(file_path, skiprows=6, nrows=0)
            columns = df.columns.tolist()
            
            # Check if key Amex columns are present
            return all(col in columns for col in self.EXPECTED_COLUMNS)
        except:
            return False
    
    def parse(self, file_path: Path, account_name: str) -> List[Transaction]:
        """Parse Amex Excel file"""
        # Amex files have 6 header rows before the data
        df = pd.read_excel(file_path, skiprows=6)
        transactions = []
        
        for _, row in df.iterrows():
            # Skip if all values are NaN
            if row.isna().all():
                continue
            
            # Skip rows without a date (like footer rows)
            if pd.isna(row['Date']):
                continue
            
            # Parse date
            try:
                date = self._parse_date(str(row['Date']))
            except:
                continue  # Skip rows with invalid dates
            
            # Parse amount
            # Amex: positive = expense, negative = credit/refund
            # Flip all signs: Amex positive → our negative (expense), Amex negative → our positive (income/refund)
            amount = -self._parse_amount(row['Amount'])
            
            # Get category (Amex provides this)
            category = row.get('Category', 'Uncategorized')
            if pd.isna(category):
                category = 'Uncategorized'
            # Amex categories come as "Parent-Child" (e.g. "Travel-Lodging").
            # Keep only the top-level parent to avoid over-granular categories.
            category = str(category).split('-')[0].strip()
            
            # Create transaction
            transaction = Transaction(
                date=date,
                description=row['Description'],
                amount=amount,
                account_name=account_name,
                account_type=self.account_type,
                institution=self.institution,
                category=str(category),
                raw_data=json.dumps(row.to_dict(), default=str),
                notes=f"Card Member: {row['Card Member']}"
            )
            
            transactions.append(transaction)
        
        return transactions
