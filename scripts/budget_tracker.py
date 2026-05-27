#!/usr/bin/env python3
"""
Budget Tracker

Set budgets for categories and track your progress.
"""
import sys
from pathlib import Path
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseManager


class BudgetManager:
    """Manage category budgets"""

    def __init__(self, budgets_file="data/budgets.json"):
        self.budgets_file = Path(budgets_file)
        self.budgets = self._load_budgets()

    def _load_budgets(self):
        """Load budgets from file"""
        if self.budgets_file.exists():
            with open(self.budgets_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_budgets(self):
        """Save budgets to file"""
        self.budgets_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.budgets_file, 'w') as f:
            json.dump(self.budgets, f, indent=2)

    def set_budget(self, category, monthly_limit):
        """Set monthly budget for a category"""
        self.budgets[category] = float(monthly_limit)
        self._save_budgets()

    def get_budget(self, category):
        """Get budget for a category"""
        return self.budgets.get(category)

    def get_all_budgets(self):
        """Get all budgets"""
        return self.budgets.copy()

    def delete_budget(self, category):
        """Delete budget for a category"""
        if category in self.budgets:
            del self.budgets[category]
            self._save_budgets()
            return True
        return False


def get_current_month_spending(db, category=None):
    """Get spending for current month"""
    conn = db.get_connection()
    cursor = conn.cursor()

    # Current month
    current_month = datetime.now().strftime('%Y-%m')

    if category:
        cursor.execute("""
            SELECT SUM(ABS(amount)) as total
            FROM transactions
            WHERE strftime('%Y-%m', date) = ?
              AND category = ?
              AND amount < 0
        """, (current_month, category))

        result = cursor.fetchone()
        return result['total'] if result['total'] else 0.0
    else:
        cursor.execute("""
            SELECT 
                category,
                SUM(ABS(amount)) as total
            FROM transactions
            WHERE strftime('%Y-%m', date) = ?
              AND amount < 0
            GROUP BY category
        """, (current_month,))

        return {row['category']: row['total'] for row in cursor.fetchall()}


def show_budget_status(db, budget_mgr):
    """Display budget status for all categories"""
    print("\n" + "=" * 100)
    print("   📊 Budget Status - " + datetime.now().strftime('%B %Y'))
    print("=" * 100)

    budgets = budget_mgr.get_all_budgets()

    if not budgets:
        print("\n📭 No budgets set yet!")
        print("   Use option 1 to set budgets\n")
        return

    # Get current month spending
    spending = get_current_month_spending(db)

    print(f"\n{'Category':25} {'Budget':>12} {'Spent':>12} {'Remaining':>12} {'%':>8} {'Status':>10}")
    print("-" * 100)

    total_budget = 0
    total_spent = 0

    for category in sorted(budgets.keys()):
        budget = budgets[category]
        spent = spending.get(category, 0.0)
        remaining = budget - spent
        percent = (spent / budget * 100) if budget > 0 else 0

        total_budget += budget
        total_spent += spent

        # Status
        if percent >= 100:
            status = "🔴 OVER"
        elif percent >= 90:
            status = "🟡 WARNING"
        elif percent >= 75:
            status = "🟠 CAUTION"
        else:
            status = "🟢 OK"

        # Color code remaining
        remaining_str = f"${remaining:,.2f}"
        if remaining < 0:
            remaining_str = f"-${abs(remaining):,.2f}"

        print(f"{category:25} ${budget:>10,.2f} ${spent:>10,.2f} {remaining_str:>12} {percent:>7.1f}% {status:>10}")

    print("-" * 100)
    total_remaining = total_budget - total_spent
    total_percent = (total_spent / total_budget * 100) if total_budget > 0 else 0

    print(
        f"{'TOTAL':25} ${total_budget:>10,.2f} ${total_spent:>10,.2f} ${total_remaining:>10,.2f} {total_percent:>7.1f}%")
    print()


def set_budget_interactive(budget_mgr):
    """Interactively set a budget"""
    print("\n" + "=" * 100)
    print("   Set Budget")
    print("=" * 100)

    category = input("\nCategory name: ").strip()
    if not category:
        print("❌ Cancelled")
        return

    try:
        limit = float(input(f"Monthly budget for '{category}': $").strip())
        if limit <= 0:
            print("❌ Budget must be positive")
            return

        budget_mgr.set_budget(category, limit)
        print(f"\n✅ Budget set: {category} = ${limit:,.2f}/month")

    except ValueError:
        print("❌ Invalid amount")


def delete_budget_interactive(budget_mgr):
    """Interactively delete a budget"""
    budgets = budget_mgr.get_all_budgets()

    if not budgets:
        print("\n📭 No budgets to delete")
        return

    print("\n" + "=" * 100)
    print("   Delete Budget")
    print("=" * 100)

    print("\nCurrent budgets:")
    for i, (category, limit) in enumerate(sorted(budgets.items()), 1):
        print(f"  {i}. {category}: ${limit:,.2f}/month")

    try:
        choice = int(input("\nEnter number to delete (or 0 to cancel): ").strip())

        if choice == 0:
            print("❌ Cancelled")
            return

        if 1 <= choice <= len(budgets):
            category = sorted(budgets.keys())[choice - 1]

            confirm = input(f"Delete budget for '{category}'? (yes/no): ").strip().lower()

            if confirm == 'yes':
                budget_mgr.delete_budget(category)
                print(f"\n✅ Budget deleted for '{category}'")
            else:
                print("❌ Cancelled")
        else:
            print("❌ Invalid choice")

    except ValueError:
        print("❌ Invalid input")


def show_category_detail(db, budget_mgr, category):
    """Show detailed breakdown for a category"""
    print("\n" + "=" * 100)
    print(f"   📋 Category Detail: {category}")
    print("=" * 100)

    budget = budget_mgr.get_budget(category)

    if not budget:
        print(f"\n⚠️  No budget set for '{category}'")
        return

    # Get current month transactions
    conn = db.get_connection()
    cursor = conn.cursor()

    current_month = datetime.now().strftime('%Y-%m')

    cursor.execute("""
        SELECT date, description, amount, account_name, merchant
        FROM transactions
        WHERE strftime('%Y-%m', date) = ?
          AND category = ?
          AND amount < 0
        ORDER BY date DESC
    """, (current_month, category))

    transactions = cursor.fetchall()

    if not transactions:
        print(f"\n📭 No transactions in {category} this month")
        return

    total_spent = sum(abs(txn['amount']) for txn in transactions)
    remaining = budget - total_spent
    percent = (total_spent / budget * 100) if budget > 0 else 0

    print(f"\nBudget:    ${budget:,.2f}")
    print(f"Spent:     ${total_spent:,.2f} ({percent:.1f}%)")
    print(f"Remaining: ${remaining:,.2f}")

    print(f"\n{'Date':12} {'Description':40} {'Amount':>12} {'Merchant':20}")
    print("-" * 100)

    for txn in transactions:
        merchant = txn['merchant'] if txn['merchant'] else ''
        print(f"{txn['date']:12} {txn['description'][:40]:40} ${abs(txn['amount']):>10,.2f} {merchant[:20]:20}")


def main():
    print("=" * 100)
    print("   💰 Budget Tracker")
    print("=" * 100)

    db = DatabaseManager()
    budget_mgr = BudgetManager()

    while True:
        print("\n" + "-" * 100)
        print("Options:")
        print("  1. Set budget for a category")
        print("  2. View budget status")
        print("  3. View category detail")
        print("  4. Delete budget")
        print("  5. Exit")

        choice = input("\nChoice (1-5): ").strip()

        if choice == '1':
            set_budget_interactive(budget_mgr)

        elif choice == '2':
            show_budget_status(db, budget_mgr)

        elif choice == '3':
            category = input("\nCategory name: ").strip()
            if category:
                show_category_detail(db, budget_mgr, category)

        elif choice == '4':
            delete_budget_interactive(budget_mgr)

        elif choice == '5':
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