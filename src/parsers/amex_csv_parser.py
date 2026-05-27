"""
Parser for American Express CSV files (cleaner CSV format).
"""
import pandas as pd
from pathlib import Path
from typing import List
import json

from .base_parser import BaseParser
from ..models import Transaction


class AmexCsvParser(BaseParser):
    """Parser for American Express CSV files"""
    
    EXPECTED_COLUMNS = [
        'Date', 'Description', 'Card Member', 'Account #', 'Amount'
    ]
    
    def __init__(self):
        super().__init__(institution='American Express', account_type='credit_card')

    def get_account_name(self, file_path: Path) -> str:
        import re
        try:
            df = pd.read_csv(file_path, nrows=1)
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
        """Detect if this is an Amex CSV file"""
        try:
            # Check if it's a CSV file
            if file_path.suffix.lower() not in ['.csv']:
                return False
            
            df = pd.read_csv(file_path, nrows=0)
            columns = df.columns.tolist()
            
            # Check if key Amex columns are present
            return all(col in columns for col in self.EXPECTED_COLUMNS)
        except:
            return False
    
    def parse(self, file_path: Path, account_name: str) -> List[Transaction]:
        """Parse Amex CSV file"""
        df = pd.read_csv(file_path)
        transactions = []
        
        for _, row in df.iterrows():
            # Skip if all values are NaN
            if row.isna().all():
                continue
            
            # Skip rows without a date
            if pd.isna(row['Date']):
                continue
            
            # Parse date
            try:
                date = self._parse_date(str(row['Date']))
            except:
                continue  # Skip rows with invalid dates
            
            # Parse amount
            # Amex CSV format:
            # - Positive values (94.01) = expenses → make negative
            # - Negative values (-285.12) = payments/credits → make positive
            amount = self._parse_amount(row['Amount'])
            
            # Simply flip the sign (Amex uses opposite of our convention)
            amount = -amount
            
            # Create transaction
            # Note: Amex CSV doesn't provide category, so all will be Uncategorized initially
            transaction = Transaction(
                date=date,
                description=row['Description'],
                amount=amount,
                account_name=account_name,
                account_type=self.account_type,
                institution=self.institution,
                category='Uncategorized',  # CSV format doesn't include category
                raw_data=json.dumps(row.to_dict(), default=str),
                notes=f"Card Member: {row['Card Member']}" if pd.notna(row['Card Member']) else None
            )
            
            transactions.append(transaction)
        
        return transactions
