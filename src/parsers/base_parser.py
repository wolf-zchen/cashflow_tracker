"""
Base parser class for all bank CSV/Excel parsers.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List
from datetime import datetime
import json

from ..models import Transaction


class BaseParser(ABC):
    """Abstract base class for bank parsers"""
    
    def __init__(self, institution: str, account_type: str):
        self.institution = institution
        self.account_type = account_type
    
    @abstractmethod
    def parse(self, file_path: Path, account_name: str) -> List[Transaction]:
        """
        Parse a bank CSV/Excel file and return list of transactions.
        
        Args:
            file_path: Path to the CSV/Excel file
            account_name: Name to identify this account (e.g., "Chase CC *6699")
        
        Returns:
            List of Transaction objects
        """
        pass
    
    def get_account_name(self, file_path: Path) -> str:
        """
        Derive a human-readable account name from the file path.
        Subclasses should override this to provide institution-specific logic.
        """
        return file_path.stem

    @abstractmethod
    def detect(self, file_path: Path) -> bool:
        """
        Detect if this parser can handle the given file.
        
        Args:
            file_path: Path to the file to check
        
        Returns:
            True if this parser can handle the file
        """
        pass
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime object"""
        from dateutil import parser
        return parser.parse(date_str)
    
    def _parse_amount(self, amount_str) -> float:
        """Parse amount string to float"""
        if isinstance(amount_str, (int, float)):
            return float(amount_str)
        
        # Remove currency symbols and commas
        amount_str = str(amount_str).replace('$', '').replace(',', '').strip()
        return float(amount_str)
    
    def _normalize_amount(self, amount: float, is_expense: bool = True) -> float:
        """
        Normalize amount to standard format:
        - Negative for expenses
        - Positive for income/credits
        
        Args:
            amount: The amount value
            is_expense: True if this is an expense, False if income
        """
        if is_expense and amount > 0:
            return -amount
        elif not is_expense and amount < 0:
            return abs(amount)
        return amount
