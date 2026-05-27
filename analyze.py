from src.database import DatabaseManager

db = DatabaseManager()

# How many transactions?
print(f"Total transactions: {db.get_transaction_count()}")

# Total spending
total = db.get_total_spending()
print(f"\nTotal spending: ${total:,.2f}")

# Spending by category
print("\nTop spending categories:")
categories = db.get_spending_by_category()
for cat in categories[:10]:
    print(f"  {cat['category']}: ${abs(cat['total']):,.2f} ({cat['count']} transactions)")

# Your accounts
print("\nYour accounts:")
accounts = db.get_accounts()
for acc in accounts:
    print(f"  - {acc['name']} ({acc['institution']})")