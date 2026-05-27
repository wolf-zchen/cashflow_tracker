"""
Parser for Chase checking account CSV files.
"""
import pandas as pd
from pathlib import Path
from typing import List
import json

from .base_parser import BaseParser
from ..models import Transaction


class ChaseCheckingParser(BaseParser):
    """Parser for Chase checking account CSV files"""
    
    EXPECTED_COLUMNS = [
        'Details', 'Posting Date', 'Description', 
        'Amount', 'Type', 'Balance', 'Check or Slip #'
    ]
    
    def __init__(self):
        super().__init__(institution='Chase', account_type='checking')
    
    def get_account_name(self, file_path: Path) -> str:
        import re
        stem = file_path.stem
        # Chase checking downloads: Chase9707_Activity20260201_...
        match = re.search(r'[Cc]hase(\d{4})', stem)
        if match:
            return f"Chase Checking *{match.group(1)}"
        # Files named "activity..." without a bank prefix are treated as Discover
        if re.match(r'^activity', stem, re.IGNORECASE):
            return "Discover"
        return f"Chase Checking"

    def detect(self, file_path: Path) -> bool:
        """Detect if this is a Chase checking CSV"""
        try:
            df = pd.read_csv(file_path, nrows=0)
            columns = df.columns.tolist()
            return all(col in columns for col in self.EXPECTED_COLUMNS)
        except:
            return False
    
    def parse(self, file_path: Path, account_name: str) -> List[Transaction]:
        """Parse Chase checking CSV"""
        # Read the CSV with index_col=False to prevent pandas from using first column as index
        df = pd.read_csv(file_path, index_col=False)
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        transactions = []
        
        for _, row in df.iterrows():
            try:
                # Get the required fields
                details = row['Details']
                posting_date = row['Posting Date']
                description = row['Description']
                amount = row['Amount']
                txn_type = row['Type']
                
                # Skip if any required field is missing
                if pd.isna(details) or pd.isna(posting_date) or pd.isna(description) or pd.isna(amount):
                    continue
                
                # Parse date
                date = self._parse_date(str(posting_date))
                
                # Parse amount (already signed correctly: negative = debit, positive = credit)
                amount_val = self._parse_amount(amount)
                
                # Create transaction
                transaction = Transaction(
                    date=date,
                    description=str(description),
                    amount=amount_val,
                    account_name=account_name,
                    account_type=self.account_type,
                    institution=self.institution,
                    category='Uncategorized',  # Chase checking doesn't provide categories
                    raw_data=json.dumps({
                        'details': str(details),
                        'posting_date': str(posting_date),
                        'description': str(description),
                        'amount': float(amount_val),
                        'type': str(txn_type) if pd.notna(txn_type) else '',
                        'balance': str(row['Balance']) if pd.notna(row['Balance']) else ''
                    }),
                    notes=f"{details} - {txn_type}" if pd.notna(txn_type) else str(details)
                )
                
                transactions.append(transaction)
                
            except Exception as e:
                # Skip problematic rows
                continue
        
        return transactions
