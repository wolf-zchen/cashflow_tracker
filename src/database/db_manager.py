"""
Database manager for cashflow tracker.
Handles all SQLite operations.
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime


class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, db_path: str = "data/transactions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = None
        self._init_database()
    
    def _init_database(self):
        """Initialize database with schema"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                institution TEXT NOT NULL,
                account_type TEXT NOT NULL,
                last_four TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                account_name TEXT NOT NULL,
                account_type TEXT NOT NULL,
                institution TEXT NOT NULL,
                category TEXT DEFAULT 'Uncategorized',
                transaction_type TEXT,
                raw_data TEXT,
                notes TEXT,
                is_duplicate BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_name) REFERENCES accounts(name)
            )
        """)

        # Migrate existing databases: add missing columns
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'transaction_type' not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN transaction_type TEXT")
        if 'tags' not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN tags TEXT")

        # Create category → CSP bucket mapping table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS category_bucket (
                category TEXT PRIMARY KEY,
                bucket TEXT NOT NULL DEFAULT 'guilt_free'
            )
        """)

        # Populate defaults (INSERT OR IGNORE so user overrides are preserved)
        default_buckets = [
            ('Housing', 'fixed'),
            ('Bills & Utilities', 'fixed'),
            ('Healthcare', 'fixed'),
            ('Transportation', 'fixed'),
            ('Banking Fees', 'fixed'),
            ('Education', 'fixed'),
            ('Investment', 'investment'),
            ('Restaurants', 'guilt_free'),
            ('Groceries', 'guilt_free'),
            ('Shopping', 'guilt_free'),
            ('Entertainment', 'guilt_free'),
            ('Personal Care', 'guilt_free'),
            ('Travel', 'guilt_free'),
            ('Gifts & Donations', 'guilt_free'),
            ('Personal', 'guilt_free'),
            ('Fitness & Wellness', 'guilt_free'),
            ('Credit Card Payment', 'untracked'),
            ('Transfer', 'untracked'),
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO category_bucket (category, bucket) VALUES (?, ?)",
            default_buckets
        )

        # Create import history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                account_name TEXT NOT NULL,
                institution TEXT NOT NULL,
                import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transaction_count INTEGER NOT NULL
            )
        """)
        
        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_date 
            ON transactions(date)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_account 
            ON transactions(account_name)
        """)
        
        conn.commit()
    
    def get_connection(self):
        """Get or create database connection"""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
        return self.connection
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def add_account(self, name: str, institution: str, account_type: str, last_four: str = None):
        """Add or update an account"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO accounts (name, institution, account_type, last_four)
            VALUES (?, ?, ?, ?)
        """, (name, institution, account_type, last_four))
        
        conn.commit()
    
    def add_transactions(self, transactions: List[dict]) -> int:
        """Add multiple transactions, return count of new transactions added"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        added_count = 0
        for txn in transactions:
            # Check for duplicates (same date, amount, description, account)
            cursor.execute("""
                SELECT id FROM transactions 
                WHERE date = ? AND amount = ? AND description = ? AND account_name = ?
            """, (txn['date'], txn['amount'], txn['description'], txn['account_name']))
            
            if cursor.fetchone() is None:
                # Not a duplicate, insert it
                cursor.execute("""
                    INSERT INTO transactions
                    (date, description, amount, account_name, account_type,
                     institution, category, transaction_type, raw_data, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    txn['date'], txn['description'], txn['amount'],
                    txn['account_name'], txn['account_type'], txn['institution'],
                    txn.get('category', 'Uncategorized'),
                    txn.get('transaction_type'),
                    txn.get('raw_data'),
                    txn.get('notes')
                ))
                added_count += 1
        
        conn.commit()
        return added_count
    
    def log_import(self, file_name: str, account_name: str, institution: str, count: int):
        """Log an import operation"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO import_history (file_name, account_name, institution, transaction_count)
            VALUES (?, ?, ?, ?)
        """, (file_name, account_name, institution, count))
        
        conn.commit()
    
    def get_total_spending(self, start_date: str = None, end_date: str = None) -> float:
        """Get total spending (sum of negative amounts)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT SUM(amount) as total FROM transactions WHERE amount < 0"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        return abs(result['total']) if result['total'] else 0.0
    
    def get_spending_by_category(self, start_date: str = None, end_date: str = None):
        """Get spending grouped by category"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT category, SUM(amount) as total, COUNT(*) as count
            FROM transactions 
            WHERE amount < 0
        """
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " GROUP BY category ORDER BY total ASC"
        
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def get_transaction_count(self) -> int:
        """Get total number of transactions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM transactions")
        return cursor.fetchone()['count']
    
    def get_accounts(self):
        """Get all accounts"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts")
        return cursor.fetchall()
