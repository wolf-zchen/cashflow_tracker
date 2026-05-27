"""
Parser for Bank of America credit card CSV files.
"""
import pandas as pd
from pathlib import Path
from typing import List
import json

from .base_parser import BaseParser
from ..models import Transaction


class BofAParser(BaseParser):
    """Parser for Bank of America credit card CSV files"""
    
    EXPECTED_COLUMNS = [
        'Posted Date', 'Reference Number', 'Payee', 'Address', 'Amount'
    ]
    
    def __init__(self):
        super().__init__(institution='Bank of America', account_type='credit_card')

    def get_account_name(self, file_path: Path) -> str:
        import re
        stem = file_path.stem
        # Take the LAST 4-digit group so "February2025_0424" → "0424" not "2025"
        matches = re.findall(r'\d{4}', stem)
        if matches:
            return f"BofA *{matches[-1]}"
        return "BofA"

    def detect(self, file_path: Path) -> bool:
        """Detect if this is a BofA CSV"""
        try:
            df = pd.read_csv(file_path, nrows=0)
            columns = df.columns.tolist()
            return all(col in columns for col in self.EXPECTED_COLUMNS)
        except:
            return False
    
    def parse(self, file_path: Path, account_name: str) -> List[Transaction]:
        """Parse BofA CSV"""
        df = pd.read_csv(file_path)
        transactions = []
        
        for _, row in df.iterrows():
            # Skip if all values are NaN
            if row.isna().all():
                continue
            
            # Parse date
            date = self._parse_date(row['Posted Date'])
            
            # Parse amount (BofA: negative = expense, positive = credit/refund)
            # Already in correct format, no need to normalize
            amount = self._parse_amount(row['Amount'])
            
            # Combine Payee and Address for description
            description = row['Payee']
            if pd.notna(row['Address']) and row['Address'].strip():
                description += f" - {row['Address'].strip()}"
            
            # Create transaction
            transaction = Transaction(
                date=date,
                description=description,
                amount=amount,
                account_name=account_name,
                account_type=self.account_type,
                institution=self.institution,
                category='Uncategorized',  # BofA doesn't provide categories in CSV
                raw_data=json.dumps(row.to_dict()),
                notes=f"Ref: {row['Reference Number']}"
            )
            
            transactions.append(transaction)
        
        return transactions
