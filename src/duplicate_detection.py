"""
Enhanced Duplicate Detection

Detects and manages duplicate transactions including:
- Exact duplicates
- Credit card payments
- Transfers between accounts
"""
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
import difflib


class DuplicateDetector:
    """Advanced duplicate transaction detection"""

    @staticmethod
    def find_exact_duplicates(db_manager) -> List[Tuple]:
        """
        Find exact duplicate transactions
        (same date, amount, description, account)

        Returns:
            List of (txn_id1, txn_id2, similarity_score) tuples
        """
        conn = db_manager.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT t1.id as id1, t2.id as id2, 
                   t1.date, t1.description, t1.amount, t1.account_name
            FROM transactions t1
            JOIN transactions t2 ON 
                t1.date = t2.date AND
                t1.amount = t2.amount AND
                t1.description = t2.description AND
                t1.account_name = t2.account_name AND
                t1.id < t2.id
            ORDER BY t1.date DESC
        """)

        duplicates = []
        for row in cursor.fetchall():
            duplicates.append({
                'id1': row['id1'],
                'id2': row['id2'],
                'type': 'exact_duplicate',
                'date': row['date'],
                'description': row['description'],
                'amount': row['amount'],
                'account': row['account_name']
            })

        return duplicates

    @staticmethod
    def find_credit_card_payments(db_manager) -> List[Dict]:
        """
        Find credit card payment pairs
        (checking account debit + credit card account credit, same amount, within 3 days)

        Returns:
            List of payment pairs
        """
        conn = db_manager.get_connection()
        cursor = conn.cursor()

        # Find potential CC payments from checking
        cursor.execute("""
            SELECT t1.id as checking_id, t1.date as checking_date, 
                   t1.amount as checking_amount, t1.description as checking_desc,
                   t1.account_name as checking_account,
                   t2.id as cc_id, t2.date as cc_date,
                   t2.amount as cc_amount, t2.description as cc_desc,
                   t2.account_name as cc_account
            FROM transactions t1
            JOIN transactions t2 ON 
                ABS(t1.amount + t2.amount) < 0.01 AND
                ABS(julianday(t1.date) - julianday(t2.date)) <= 3 AND
                t1.account_type = 'checking' AND
                t2.account_type = 'credit_card' AND
                t1.amount < 0 AND
                t2.amount > 0 AND
                t1.id != t2.id
            WHERE (
                t1.description LIKE '%PAYMENT%' OR
                t1.description LIKE '%AUTOPAY%' OR
                t1.description LIKE '%AMERICAN EXPRESS%' OR
                t1.description LIKE '%CHASE%' OR
                t2.description LIKE '%PAYMENT%' OR
                t2.description LIKE '%THANK YOU%'
            )
            ORDER BY t1.date DESC
        """)

        pairs = []
        for row in cursor.fetchall():
            pairs.append({
                'checking_id': row['checking_id'],
                'cc_id': row['cc_id'],
                'type': 'credit_card_payment',
                'date': row['checking_date'],
                'amount': abs(row['checking_amount']),
                'checking_account': row['checking_account'],
                'cc_account': row['cc_account'],
                'description': row['checking_desc']
            })

        return pairs

    @staticmethod
    def find_transfers(db_manager) -> List[Dict]:
        """
        Find transfer pairs between accounts
        (opposite amounts, similar dates, transfer-like descriptions)

        Returns:
            List of transfer pairs
        """
        conn = db_manager.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT t1.id as id1, t1.date as date1, t1.amount as amount1,
                   t1.description as desc1, t1.account_name as account1,
                   t2.id as id2, t2.date as date2, t2.amount as amount2,
                   t2.description as desc2, t2.account_name as account2
            FROM transactions t1
            JOIN transactions t2 ON 
                ABS(t1.amount + t2.amount) < 0.01 AND
                ABS(julianday(t1.date) - julianday(t2.date)) <= 2 AND
                t1.account_name != t2.account_name AND
                t1.id < t2.id
            WHERE (
                t1.description LIKE '%TRANSFER%' OR
                t1.description LIKE '%WITHDRAWAL%' OR
                t1.description LIKE '%DEPOSIT%' OR
                t1.description LIKE '%ZELLE%' OR
                t1.description LIKE '%VENMO%' OR
                t2.description LIKE '%TRANSFER%' OR
                t2.description LIKE '%WITHDRAWAL%' OR
                t2.description LIKE '%DEPOSIT%' OR
                t2.description LIKE '%CREDITS%'
            )
            ORDER BY t1.date DESC
        """)

        transfers = []
        for row in cursor.fetchall():
            transfers.append({
                'id1': row['id1'],
                'id2': row['id2'],
                'type': 'transfer',
                'date1': row['date1'],
                'date2': row['date2'],
                'amount': abs(row['amount1']),
                'account1': row['account1'],
                'account2': row['account2'],
                'desc1': row['desc1'],
                'desc2': row['desc2']
            })

        return transfers

    @staticmethod
    def mark_as_duplicate(db_manager, transaction_id: int):
        """Mark a transaction as duplicate"""
        conn = db_manager.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE transactions SET is_duplicate = 1 WHERE id = ?",
            (transaction_id,)
        )
        conn.commit()

    @staticmethod
    def link_transactions(db_manager, txn_id1: int, txn_id2: int, link_type: str):
        """
        Link two related transactions (for future use)
        Note: This would require a new table for transaction links
        """
        # TODO: Create a transaction_links table
        pass