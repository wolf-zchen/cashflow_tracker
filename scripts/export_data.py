#!/usr/bin/env python3
"""
Data Export Tool

Export your transaction data to CSV, Excel, or JSON formats.
Perfect for backups, sharing, or analysis in other tools.
"""
import sys
from pathlib import Path
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseManager

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def export_to_csv(db, output_path, filters=None):
    """Export transactions to CSV"""
    conn = db.get_connection()

    # Build query
    query = "SELECT * FROM transactions"
    params = []

    if filters:
        where_clauses = []
        if filters.get('start_date'):
            where_clauses.append("date >= ?")
            params.append(filters['start_date'])
        if filters.get('end_date'):
            where_clauses.append("date <= ?")
            params.append(filters['end_date'])
        if filters.get('category'):
            where_clauses.append("category = ?")
            params.append(filters['category'])
        if filters.get('account'):
            where_clauses.append("account_name = ?")
            params.append(filters['account'])

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY date DESC"

    if HAS_PANDAS:
        # Use pandas for better CSV handling
        df = pd.read_sql_query(query, conn, params=params)
        df.to_csv(output_path, index=False)
        return len(df)
    else:
        # Manual CSV export
        import csv
        cursor = conn.cursor()
        cursor.execute(query, params)

        rows = cursor.fetchall()
        if not rows:
            return 0

        with open(output_path, 'w', newline='') as f:
            # Get column names
            columns = [desc[0] for desc in cursor.description]
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()

            for row in rows:
                writer.writerow(dict(row))

        return len(rows)


def export_to_excel(db, output_path, filters=None):
    """Export transactions to Excel with multiple sheets"""
    if not HAS_PANDAS:
        print("❌ pandas and openpyxl required for Excel export")
        print("   Install with: pip install pandas openpyxl")
        return 0

    conn = db.get_connection()

    # Build query for transactions
    query = "SELECT * FROM transactions"
    params = []

    if filters:
        where_clauses = []
        if filters.get('start_date'):
            where_clauses.append("date >= ?")
            params.append(filters['start_date'])
        if filters.get('end_date'):
            where_clauses.append("date <= ?")
            params.append(filters['end_date'])
        if filters.get('category'):
            where_clauses.append("category = ?")
            params.append(filters['category'])
        if filters.get('account'):
            where_clauses.append("account_name = ?")
            params.append(filters['account'])

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY date DESC"

    # Read data
    df_transactions = pd.read_sql_query(query, conn, params=params)

    # Create summary sheets
    df_by_category = pd.read_sql_query("""
        SELECT 
            category,
            COUNT(*) as transaction_count,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_spent,
            AVG(CASE WHEN amount < 0 THEN ABS(amount) ELSE NULL END) as avg_transaction
        FROM transactions
        WHERE amount < 0
        GROUP BY category
        ORDER BY total_spent DESC
    """, conn)

    df_by_month = pd.read_sql_query("""
        SELECT 
            strftime('%Y-%m', date) as month,
            COUNT(*) as transaction_count,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_spent,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_income
        FROM transactions
        GROUP BY month
        ORDER BY month DESC
    """, conn)

    df_by_account = pd.read_sql_query("""
        SELECT 
            account_name,
            COUNT(*) as transaction_count,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_spent
        FROM transactions
        WHERE amount < 0
        GROUP BY account_name
        ORDER BY total_spent DESC
    """, conn)

    # Write to Excel with multiple sheets
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_transactions.to_excel(writer, sheet_name='Transactions', index=False)
        df_by_category.to_excel(writer, sheet_name='By Category', index=False)
        df_by_month.to_excel(writer, sheet_name='By Month', index=False)
        df_by_account.to_excel(writer, sheet_name='By Account', index=False)

    return len(df_transactions)


def export_to_json(db, output_path, filters=None):
    """Export transactions to JSON"""
    conn = db.get_connection()
    cursor = conn.cursor()

    # Build query
    query = "SELECT * FROM transactions"
    params = []

    if filters:
        where_clauses = []
        if filters.get('start_date'):
            where_clauses.append("date >= ?")
            params.append(filters['start_date'])
        if filters.get('end_date'):
            where_clauses.append("date <= ?")
            params.append(filters['end_date'])
        if filters.get('category'):
            where_clauses.append("category = ?")
            params.append(filters['category'])
        if filters.get('account'):
            where_clauses.append("account_name = ?")
            params.append(filters['account'])

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY date DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Convert to list of dicts
    transactions = [dict(row) for row in rows]

    # Write JSON
    with open(output_path, 'w') as f:
        json.dump(transactions, f, indent=2, default=str)

    return len(transactions)


def main():
    print("=" * 100)
    print("   📤 Data Export Tool")
    print("=" * 100)

    db = DatabaseManager()

    # Get export format
    print("\nExport formats:")
    print("  1. CSV (simple, universal)")
    print("  2. Excel (multi-sheet with summaries)")
    print("  3. JSON (for developers)")
    print("  4. All formats")

    format_choice = input("\nChoose format (1-4): ").strip()

    # Get date range
    print("\n" + "-" * 100)
    print("Date range (leave blank for all data):")
    start_date = input("  Start date (YYYY-MM-DD): ").strip() or None
    end_date = input("  End date (YYYY-MM-DD): ").strip() or None

    # Get optional filters
    print("\nOptional filters (leave blank to skip):")
    category = input("  Category: ").strip() or None
    account = input("  Account: ").strip() or None

    filters = {}
    if start_date:
        filters['start_date'] = start_date
    if end_date:
        filters['end_date'] = end_date
    if category:
        filters['category'] = category
    if account:
        filters['account'] = account

    # Create output directory
    output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"transactions_{timestamp}"

    print("\n⚙️  Exporting...")

    results = []

    # Export based on choice
    if format_choice in ['1', '4']:
        # CSV
        csv_path = output_dir / f"{base_name}.csv"
        count = export_to_csv(db, csv_path, filters)
        results.append(('CSV', csv_path, count))

    if format_choice in ['2', '4']:
        # Excel
        if HAS_PANDAS:
            xlsx_path = output_dir / f"{base_name}.xlsx"
            count = export_to_excel(db, xlsx_path, filters)
            results.append(('Excel', xlsx_path, count))
        else:
            print("\n⚠️  Skipping Excel export (pandas not installed)")

    if format_choice in ['3', '4']:
        # JSON
        json_path = output_dir / f"{base_name}.json"
        count = export_to_json(db, json_path, filters)
        results.append(('JSON', json_path, count))

    # Show results
    print("\n" + "=" * 100)
    print("   ✅ Export Complete!")
    print("=" * 100)

    for format_type, path, count in results:
        print(f"\n{format_type}:")
        print(f"  File: {path}")
        print(f"  Transactions: {count:,}")
        print(f"  Size: {path.stat().st_size / 1024:.1f} KB")

    print("\n💡 Files saved in: exports/")
    print()

    db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.\n")
        sys.exit(0)