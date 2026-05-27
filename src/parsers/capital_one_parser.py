"""
Parser for Capital One checking/savings account CSV files.
"""
import pandas as pd
from pathlib import Path
from typing import List
import json

from .base_parser import BaseParser
from ..models import Transaction


class CapitalOneParser(BaseParser):
    """Parser for Capital One account CSV files"""

    EXPECTED_COLUMNS = [
        'Account Number', 'Transaction Description', 'Transaction Date',
        'Transaction Type', 'Transaction Amount', 'Balance'
    ]

    def __init__(self):
        super().__init__(institution='Capital One', account_type='checking')

    def get_account_name(self, file_path: Path) -> str:
        import re
        stem = file_path.stem
        # Filename often contains last 4 digits, e.g. "2026-04-06_360Checking...2516"
        match = re.search(r'(\d{4})$', stem)
        if match:
            return f"Capital One *{match.group(1)}"
        # Fall back to reading first data row for account number
        try:
            df = pd.read_csv(file_path, nrows=1)
            acct = str(df['Account Number'].iloc[0]).strip()
            if acct and acct != 'nan':
                return f"Capital One *{acct[-4:]}"
        except Exception:
            pass
        return "Capital One"

    def detect(self, file_path: Path) -> bool:
        """Detect if this is a Capital One CSV"""
        try:
            df = pd.read_csv(file_path, nrows=0)
            columns = df.columns.tolist()
            return all(col in columns for col in self.EXPECTED_COLUMNS)
        except Exception:
            return False

    def parse(self, file_path: Path, account_name: str) -> List[Transaction]:
        """Parse Capital One CSV"""
        df = pd.read_csv(file_path)
        df = df.dropna(how='all')

        transactions = []

        for _, row in df.iterrows():
            try:
                date = self._parse_date(str(row['Transaction Date']))
                description = str(row['Transaction Description']).strip()

                # Capital One: Transaction Amount is always positive;
                # Transaction Type tells us direction (Credit vs Debit).
                raw_amount = self._parse_amount(row['Transaction Amount'])
                txn_type = str(row['Transaction Type']).strip().lower()
                if txn_type == 'debit':
                    amount = -abs(raw_amount)
                else:
                    amount = abs(raw_amount)

                transaction = Transaction(
                    date=date,
                    description=description,
                    amount=amount,
                    account_name=account_name,
                    account_type=self.account_type,
                    institution=self.institution,
                    category='Uncategorized',
                    raw_data=json.dumps(row.to_dict()),
                    notes=row['Transaction Type'],
                )
                transactions.append(transaction)

            except Exception:
                continue

        return transactions
