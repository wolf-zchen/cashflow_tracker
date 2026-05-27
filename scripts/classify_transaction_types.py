#!/usr/bin/env python3
"""
Internal Transfer Classifier

Identifies and marks transactions that are internal transfers
(credit card payments, account transfers, etc.) so they don't
count as spending in charts and analysis.
"""
import sys
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseManager

# Transaction type classification
TRANSFER_PATTERNS = {
    'Credit Card Payment': [
        r'CHASE.*CREDIT.*AUTOPAY',
        r'CHASE.*PAYMENT',
        r'AMERICAN EXPRESS.*PMT',
        r'AMERICAN EXPRESS.*PAYMENT',
        r'AMEX.*PAYMENT',
        r'ONLINE PAYMENT.*THANK YOU',
        r'MOBILE PAYMENT.*THANK YOU',
        r'CREDIT CARD PAYMENT',
        r'CARD PAYMENT',
        r'AUTOPAY',
    ],

    'Account Transfer': [
        r'TRANSFER TO.*CHECKING',
        r'TRANSFER TO.*SAVINGS',
        r'TRANSFER FROM.*CHECKING',
        r'TRANSFER FROM.*SAVINGS',
        r'WITHDRAWAL.*TRANSFER',
        r'DEPOSIT.*TRANSFER',
        r'ZELLE TRANSFER',
        r'VENMO TRANSFER',
    ],

    'Investment Transfer': [
        r'ROBINHOOD.*CREDITS',
        r'ROBINHOOD.*TRANSFER',
        r'VANGUARD.*TRANSFER',
        r'FIDELITY.*TRANSFER',
        r'SCHWAB.*TRANSFER',
        r'ILD529',
        r'529 PLAN',
    ],
}


def add_transaction_type_column(db):
    """Add transaction_type column to database if it doesn't exist"""
    conn = db.get_connection()
    cursor = conn.cursor()

    # Check if column exists
    cursor.execute("PRAGMA table_info(transactions)")
    columns = [col['name'] for col in cursor.fetchall()]

    if 'transaction_type' not in columns:
        print("Adding 'transaction_type' column to database...")
        cursor.execute("ALTER TABLE transactions ADD COLUMN transaction_type TEXT DEFAULT 'expense'")
        conn.commit()
        print("✅ Column added")
    else:
        print("✅ 'transaction_type' column already exists")


def classify_transaction(description: str, amount: float, category: str) -> str:
    """
    Classify transaction type

    Returns:
        'income' - Money coming in
        'expense' - Money going out (actual spending)
        'transfer' - Internal transfer (should not count as spending)
    """
    # Positive amounts are income or credits
    if amount > 0:
        # Check if it's a credit card payment (refund)
        for pattern_list in TRANSFER_PATTERNS.values():
            for pattern in pattern_list:
                if re.search(pattern, description.upper()):
                    return 'transfer'
        return 'income'

    # Negative amounts - check if they're transfers
    description_upper = description.upper()

    for transfer_type, patterns in TRANSFER_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, description_upper):
                return 'transfer'

    # Check category
    if category in ['Credit Card Payment', 'Transfer', 'Investment']:
        return 'transfer'

    # Default: it's an expense
    return 'expense'


def classify_all_transactions(db, dry_run=True):
    """Classify all transactions"""
    conn = db.get_connection()
    cursor = conn.cursor()

    # Get all transactions
    cursor.execute("SELECT id, description, amount, category, transaction_type FROM transactions")
    transactions = cursor.fetchall()

    stats = {
        'total': len(transactions),
        'income': 0,
        'expense': 0,
        'transfer': 0,
        'changed': 0,
    }

    updates = []

    for txn in transactions:
        # Classify
        new_type = classify_transaction(txn['description'], txn['amount'], txn['category'])

        stats[new_type] += 1

        # Check if changed
        if txn['transaction_type'] != new_type:
            updates.append((txn['id'], txn['description'], txn['amount'],
                            txn['transaction_type'], new_type))
            stats['changed'] += 1

    # Show preview
    print("\n" + "=" * 100)
    print("   🏷️  Transaction Type Classification")
    print("=" * 100)

    print(f"\nTotal transactions: {stats['total']}")
    print(f"\nBreakdown:")
    print(f"  Income:    {stats['income']:5} ({stats['income'] / stats['total'] * 100:.1f}%)")
    print(f"  Expense:   {stats['expense']:5} ({stats['expense'] / stats['total'] * 100:.1f}%)")
    print(f"  Transfer:  {stats['transfer']:5} ({stats['transfer'] / stats['total'] * 100:.1f}%)")

    print(f"\nChanges: {stats['changed']} transaction(s) will be reclassified")

    if updates:
        print(f"\n💡 Sample changes (first 20):")
        print(f"\n{'Description':50} {'Amount':>12} {'Old Type':>12} → {'New Type':>12}")
        print("-" * 100)

        for txn_id, desc, amount, old_type, new_type in updates[:20]:
            print(f"{desc[:50]:50} ${amount:>10,.2f} {old_type:>12} → {new_type:>12}")

        if len(updates) > 20:
            print(f"\n... and {len(updates) - 20} more changes")

        if not dry_run:
            # Apply updates
            print(f"\n⚙️  Applying changes...")
            for txn_id, _, _, _, new_type in updates:
                cursor.execute(
                    "UPDATE transactions SET transaction_type = ? WHERE id = ?",
                    (new_type, txn_id)
                )
            conn.commit()
            print(f"✅ Updated {stats['changed']} transactions")
        else:
            print(f"\n💡 This was a DRY RUN - no changes made")
            print(f"   Run with confirm=yes to apply changes")
    else:
        print(f"\n✅ All transactions already correctly classified!")

    return stats


def show_transfers(db, limit=50):
    """Show all transactions classified as transfers"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT date, description, amount, category, account_name
        FROM transactions
        WHERE transaction_type = 'transfer'
        ORDER BY date DESC
        LIMIT ?
    """, (limit,))

    transfers = cursor.fetchall()

    if not transfers:
        print("\n📭 No transfers found")
        return

    print("\n" + "=" * 100)
    print(f"   🔄 Internal Transfers (Last {len(transfers)})")
    print("=" * 100)

    print(f"\n{'Date':12} {'Description':40} {'Amount':>12} {'Category':20} {'Account':20}")
    print("-" * 100)

    for txn in transfers:
        print(f"{txn['date']:12} {txn['description'][:40]:40} ${txn['amount']:>10,.2f} "
              f"{txn['category'][:20]:20} {txn['account_name'][:20]:20}")

    # Show total
    total_in = sum(txn['amount'] for txn in transfers if txn['amount'] > 0)
    total_out = sum(abs(txn['amount']) for txn in transfers if txn['amount'] < 0)

    print("-" * 100)
    print(f"Total in:  ${total_in:,.2f}")
    print(f"Total out: ${total_out:,.2f}")
    print(f"Net:       ${total_in - total_out:,.2f}")


def manual_reclassify(db):
    """Manually reclassify specific transactions"""
    print("\n" + "=" * 100)
    print("   ✏️  Manual Reclassification")
    print("=" * 100)

    print("\nSearch for transaction:")
    keyword = input("  Keyword in description: ").strip()

    if not keyword:
        print("❌ Cancelled")
        return

    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, date, description, amount, category, transaction_type
        FROM transactions
        WHERE description LIKE ?
        ORDER BY date DESC
        LIMIT 20
    """, (f'%{keyword}%',))

    results = cursor.fetchall()

    if not results:
        print(f"\n❌ No transactions found with '{keyword}'")
        return

    print(f"\n✅ Found {len(results)} transaction(s):")

    for i, txn in enumerate(results, 1):
        print(f"\n{i}. {txn['date']} | {txn['description'][:50]}")
        print(f"   Amount: ${txn['amount']:,.2f} | Type: {txn['transaction_type']} | Category: {txn['category']}")

    try:
        selection = int(input("\nSelect transaction # (or 0 to cancel): ").strip())

        if selection == 0:
            print("❌ Cancelled")
            return

        if 1 <= selection <= len(results):
            txn = results[selection - 1]

            print(f"\nCurrent type: {txn['transaction_type']}")
            print("\nOptions:")
            print("  1. income")
            print("  2. expense")
            print("  3. transfer")

            type_choice = input("New type (1-3): ").strip()

            type_map = {'1': 'income', '2': 'expense', '3': 'transfer'}
            new_type = type_map.get(type_choice)

            if new_type:
                cursor.execute(
                    "UPDATE transactions SET transaction_type = ? WHERE id = ?",
                    (new_type, txn['id'])
                )
                conn.commit()
                print(f"\n✅ Updated to '{new_type}'")
            else:
                print("❌ Invalid choice")
        else:
            print("❌ Invalid selection")

    except ValueError:
        print("❌ Invalid input")


def main():
    print("=" * 100)
    print("   🏷️  Transaction Type Classifier")
    print("=" * 100)
    print("\nThis tool identifies internal transfers (credit card payments, account transfers)")
    print("so they don't count as spending in charts and analysis.")

    db = DatabaseManager()

    # Add column if needed
    add_transaction_type_column(db)

    while True:
        print("\n" + "-" * 100)
        print("Options:")
        print("  1. Auto-classify all transactions")
        print("  2. Show current transfers")
        print("  3. Manually reclassify transaction")
        print("  4. Exit")

        choice = input("\nChoice (1-4): ").strip()

        if choice == '1':
            # Run dry-run first
            print("\n🔍 Running preview (dry-run)...")
            stats = classify_all_transactions(db, dry_run=True)

            if stats['changed'] > 0:
                print("\n" + "=" * 100)
                response = input("\nApply these changes? (yes/no): ").strip().lower()

                if response == 'yes':
                    classify_all_transactions(db, dry_run=False)
                    print("\n✨ Transaction types updated!")
                else:
                    print("\n❌ Cancelled - no changes made")

        elif choice == '2':
            show_transfers(db)

        elif choice == '3':
            manual_reclassify(db)

        elif choice == '4':
            print("\n👋 Goodbye!")
            break

        else:
            print("❌ Invalid choice")

    db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.\n")
        sys.exit(0)