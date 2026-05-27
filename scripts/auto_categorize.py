#!/usr/bin/env python3
"""
Auto-Categorize Transactions

Automatically categorizes transactions based on keyword rules.
Uses both built-in rules and your learned rules!
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseManager
from src.categorization import Categorizer
from src.learned_rules import LearnedRules


def show_before_after(db):
    """Show categorization stats before and after"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT category, COUNT(*) as count, SUM(ABS(amount)) as total
        FROM transactions 
        WHERE amount < 0
        GROUP BY category 
        ORDER BY total DESC
        LIMIT 10
    """)
    
    results = cursor.fetchall()
    
    print(f"\n{'Category':30} {'Count':>6} {'Total':>12}")
    print("-" * 50)
    for row in results:
        print(f"{row['category']:30} {row['count']:>6} ${abs(row['total']):>10,.2f}")


def main():
    print("=" * 80)
    print("   🤖 Automatic Categorization Tool")
    print("=" * 80)
    
    db = DatabaseManager()
    learned = LearnedRules()
    
    # Show stats about learned rules
    learned_count = learned.rule_count()
    if learned_count > 0:
        print(f"\n💡 Using {learned_count} learned rule(s) in addition to built-in rules!")
    
    # Check for uncategorized
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM transactions 
        WHERE category = 'Uncategorized'
    """)
    
    uncat_count = cursor.fetchone()['count']
    
    if uncat_count == 0:
        print("\n✅ All transactions are already categorized!")
        print("\nCurrent breakdown:")
        show_before_after(db)
        
        response = input("\nRe-categorize all transactions? (yes/no): ").strip().lower()
        if response != 'yes':
            print("\n👋 Goodbye!")
            return
        overwrite = True
    else:
        print(f"\nFound {uncat_count} uncategorized transaction(s)")
        print("\nOptions:")
        print("  1. Categorize only uncategorized transactions (recommended)")
        print("  2. Re-categorize ALL transactions (overwrites existing)")
        print("  3. Cancel")
        
        choice = input("\nChoice (1-3): ").strip()
        
        if choice == '3':
            print("\n👋 Cancelled")
            return
        elif choice == '2':
            confirm = input("\n⚠️  This will overwrite existing categories. Continue? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("\n👋 Cancelled")
                return
            overwrite = True
        else:
            overwrite = False
    
    # Show before state
    print("\n" + "=" * 80)
    print("   📊 Before Auto-Categorization")
    print("=" * 80)
    show_before_after(db)
    
    # Run auto-categorization
    print("\n⚙️  Running automatic categorization...")
    
    # First try learned rules, then built-in rules
    if overwrite:
        cursor.execute("SELECT id, description, category FROM transactions")
    else:
        cursor.execute("""
            SELECT id, description, category 
            FROM transactions 
            WHERE category = 'Uncategorized' OR category IS NULL
        """)
    
    transactions = cursor.fetchall()
    
    stats = {
        'total_processed': 0,
        'updated': 0,
        'already_categorized': 0,
        'by_category': {},
        'learned_rules_used': 0,
        'builtin_rules_used': 0
    }
    
    for txn in transactions:
        stats['total_processed'] += 1
        
        # Try learned rules first
        new_category = learned.categorize(txn['description'], txn['category'])
        
        if new_category == 'Uncategorized' or new_category == txn['category']:
            # Try built-in rules
            new_category = Categorizer.categorize(txn['description'], txn['category'])
            if new_category != txn['category'] and new_category != 'Uncategorized':
                stats['builtin_rules_used'] += 1
        else:
            stats['learned_rules_used'] += 1
        
        if new_category != txn['category']:
            cursor.execute(
                "UPDATE transactions SET category = ? WHERE id = ?",
                (new_category, txn['id'])
            )
            stats['updated'] += 1
            stats['by_category'][new_category] = stats['by_category'].get(new_category, 0) + 1
        else:
            stats['already_categorized'] += 1
    
    conn.commit()
    
    print(f"\n✅ Auto-categorization complete!")
    print(f"\nResults:")
    print(f"  Processed: {stats['total_processed']}")
    print(f"  Updated:   {stats['updated']}")
    print(f"  Unchanged: {stats['already_categorized']}")
    
    if learned_count > 0:
        print(f"\n💡 Rule usage:")
        print(f"  Learned rules:  {stats['learned_rules_used']}")
        print(f"  Built-in rules: {stats['builtin_rules_used']}")
    
    if stats['by_category']:
        print(f"\nTransactions categorized:")
        for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {category}: {count}")
    
    # Show after state
    print("\n" + "=" * 80)
    print("   📊 After Auto-Categorization")
    print("=" * 80)
    show_before_after(db)
    
    # Check remaining uncategorized
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM transactions 
        WHERE category = 'Uncategorized'
    """)
    
    remaining = cursor.fetchone()['count']
    
    if remaining > 0:
        print(f"\n⚠️  {remaining} transaction(s) still uncategorized")
        print("   These couldn't be automatically categorized.")
        print("   Run 'python scripts/interactive_categorize.py' to categorize them manually.")
        print("   The system will learn as you categorize!")
    else:
        print(f"\n🎉 All transactions are now categorized!")
    
    db.close()
    print("\n✨ Done!\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.\n")
        sys.exit(0)
