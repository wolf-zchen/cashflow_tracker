"""
Data models for the cashflow tracker.
Defines the unified transaction schema.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    """Unified transaction model for all banks"""
    date: datetime
    description: str
    amount: float  # Negative = expense, Positive = income/credit
    account_name: str
    account_type: str  # 'credit_card', 'checking', 'savings'
    institution: str  # 'Chase', 'Amex', 'Bank of America'
    category: str = 'Uncategorized'
    raw_data: Optional[str] = None
    notes: Optional[str] = None
    
    def to_dict(self):
        """Convert to dictionary for database insertion"""
        return {
            'date': self.date.strftime('%Y-%m-%d'),
            'description': self.description,
            'amount': self.amount,
            'account_name': self.account_name,
            'account_type': self.account_type,
            'institution': self.institution,
            'category': self.category,
            'raw_data': self.raw_data,
            'notes': self.notes
        }


@dataclass
class Account:
    """Account information"""
    name: str
    institution: str
    account_type: str
    last_four: Optional[str] = None
