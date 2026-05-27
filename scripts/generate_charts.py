#!/usr/bin/env python3
"""
Chart Generator

Creates beautiful charts and graphs from your transaction data.
Generates PNG files for sharing and embedding in reports.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseManager

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    import numpy as np

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("❌ matplotlib required for charts")
    print("   Install with: pip install matplotlib")
    sys.exit(1)

# Set style
plt.style.use('seaborn-v0_8-darkgrid')


def create_output_dir():
    """Create charts output directory"""
    output_dir = Path("charts")
    output_dir.mkdir(exist_ok=True)
    return output_dir


def spending_by_category_pie(db, output_dir, top_n=10):
    """Create pie chart of spending by category"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            category,
            SUM(ABS(amount)) as total
        FROM transactions
        WHERE amount < 0 
          AND category != 'Uncategorized'
          AND (transaction_type = 'expense' OR transaction_type IS NULL)
        GROUP BY category
        ORDER BY total DESC
        LIMIT ?
    """, (top_n,))

    data = cursor.fetchall()

    if not data:
        print("⚠️  No data for category pie chart")
        return None

    categories = [row['category'] for row in data]
    amounts = [row['total'] for row in data]

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))

    # Create pie chart
    colors = plt.cm.Set3(range(len(categories)))
    wedges, texts, autotexts = ax.pie(
        amounts,
        labels=categories,
        autopct='%1.1f%%',
        colors=colors,
        startangle=90
    )

    # Beautify
    for text in texts:
        text.set_fontsize(10)
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(9)

    ax.set_title(f'Spending by Category (Top {top_n})', fontsize=16, fontweight='bold', pad=20)

    # Add total
    total = sum(amounts)
    plt.text(0, -1.3, f'Total Spending: ${total:,.2f}',
             ha='center', fontsize=12, fontweight='bold')

    # Save
    filename = output_dir / f'spending_by_category_pie_{datetime.now().strftime("%Y%m%d")}.png'
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

    return filename


def spending_by_category_bar(db, output_dir, top_n=15):
    """Create horizontal bar chart of spending by category"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            category,
            SUM(ABS(amount)) as total,
            COUNT(*) as count
        FROM transactions
        WHERE amount < 0 
          AND category != 'Uncategorized'
          AND (transaction_type = 'expense' OR transaction_type IS NULL)
        GROUP BY category
        ORDER BY total DESC
        LIMIT ?
    """, (top_n,))

    data = cursor.fetchall()

    if not data:
        print("⚠️  No data for category bar chart")
        return None

    categories = [row['category'] for row in data]
    amounts = [row['total'] for row in data]
    counts = [row['count'] for row in data]

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))

    # Create horizontal bar chart
    y_pos = np.arange(len(categories))
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(categories)))

    bars = ax.barh(y_pos, amounts, color=colors)

    # Customize
    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories)
    ax.invert_yaxis()  # Top category at top
    ax.set_xlabel('Total Spending ($)', fontsize=12, fontweight='bold')
    ax.set_title(f'Spending by Category (Top {top_n})', fontsize=16, fontweight='bold', pad=20)

    # Add value labels
    for i, (bar, amount, count) in enumerate(zip(bars, amounts, counts)):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height() / 2,
                f' ${amount:,.0f} ({count} txns)',
                ha='left', va='center', fontsize=9, fontweight='bold')

    # Grid
    ax.grid(axis='x', alpha=0.3)

    # Save
    filename = output_dir / f'spending_by_category_bar_{datetime.now().strftime("%Y%m%d")}.png'
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

    return filename


def monthly_spending_trend(db, output_dir, months=12):
    """Create line chart of monthly spending trends"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            strftime('%Y-%m', date) as month,
            SUM(CASE WHEN amount < 0 AND (transaction_type = 'expense' OR transaction_type IS NULL) 
                     THEN ABS(amount) ELSE 0 END) as spending,
            SUM(CASE WHEN amount > 0 AND (transaction_type = 'income' OR transaction_type IS NULL)
                     THEN amount ELSE 0 END) as income
        FROM transactions
        GROUP BY month
        ORDER BY month DESC
        LIMIT ?
    """, (months,))

    data = list(reversed(cursor.fetchall()))  # Oldest first

    if not data:
        print("⚠️  No data for monthly trend chart")
        return None

    months_labels = [row['month'] for row in data]
    spending = [row['spending'] for row in data]
    income = [row['income'] for row in data]

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 7))

    x = np.arange(len(months_labels))

    # Plot lines
    ax.plot(x, spending, marker='o', linewidth=2.5, markersize=8,
            label='Spending', color='#e74c3c', linestyle='-')
    ax.plot(x, income, marker='s', linewidth=2.5, markersize=8,
            label='Income', color='#27ae60', linestyle='-')

    # Fill area under curves
    ax.fill_between(x, spending, alpha=0.2, color='#e74c3c')
    ax.fill_between(x, income, alpha=0.2, color='#27ae60')

    # Customize
    ax.set_xticks(x)
    ax.set_xticklabels(months_labels, rotation=45, ha='right')
    ax.set_ylabel('Amount ($)', fontsize=12, fontweight='bold')
    ax.set_title('Monthly Spending vs Income Trend', fontsize=16, fontweight='bold', pad=20)
    ax.legend(loc='upper left', fontsize=11)
    ax.grid(True, alpha=0.3)

    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Save
    filename = output_dir / f'monthly_trend_{datetime.now().strftime("%Y%m%d")}.png'
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

    return filename


def category_trend_over_time(db, output_dir, categories=None, months=12):
    """Create stacked area chart of category spending over time"""
    conn = db.get_connection()
    cursor = conn.cursor()

    # Get top categories if not specified
    if not categories:
        cursor.execute("""
            SELECT category
            FROM transactions
            WHERE amount < 0 
              AND category != 'Uncategorized'
              AND (transaction_type = 'expense' OR transaction_type IS NULL)
            GROUP BY category
            ORDER BY SUM(ABS(amount)) DESC
            LIMIT 5
        """)
        categories = [row['category'] for row in cursor.fetchall()]

    if not categories:
        print("⚠️  No categories for trend chart")
        return None

    # Get data for each category
    category_data = {}
    all_months = set()

    for category in categories:
        cursor.execute("""
            SELECT 
                strftime('%Y-%m', date) as month,
                SUM(ABS(amount)) as total
            FROM transactions
            WHERE category = ? 
              AND amount < 0
              AND (transaction_type = 'expense' OR transaction_type IS NULL)
            GROUP BY month
            ORDER BY month DESC
            LIMIT ?
        """, (category, months))

        data = {row['month']: row['total'] for row in cursor.fetchall()}
        category_data[category] = data
        all_months.update(data.keys())

    # Sort months
    months_sorted = sorted(all_months)[-months:]

    # Create matrix
    matrix = []
    for category in categories:
        row = [category_data[category].get(month, 0) for month in months_sorted]
        matrix.append(row)

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 7))

    x = np.arange(len(months_sorted))
    colors = plt.cm.Set3(range(len(categories)))

    # Create stacked area chart
    ax.stackplot(x, *matrix, labels=categories, colors=colors, alpha=0.8)

    # Customize
    ax.set_xticks(x)
    ax.set_xticklabels(months_sorted, rotation=45, ha='right')
    ax.set_ylabel('Spending ($)', fontsize=12, fontweight='bold')
    ax.set_title('Category Spending Trends Over Time', fontsize=16, fontweight='bold', pad=20)
    ax.legend(loc='upper left', fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')

    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Save
    filename = output_dir / f'category_trends_{datetime.now().strftime("%Y%m%d")}.png'
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

    return filename


def spending_by_account(db, output_dir):
    """Create bar chart of spending by account"""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            account_name,
            SUM(ABS(amount)) as total,
            COUNT(*) as count
        FROM transactions
        WHERE amount < 0
          AND (transaction_type = 'expense' OR transaction_type IS NULL)
        GROUP BY account_name
        ORDER BY total DESC
    """)

    data = cursor.fetchall()

    if not data:
        print("⚠️  No data for account chart")
        return None

    accounts = [row['account_name'] for row in data]
    amounts = [row['total'] for row in data]
    counts = [row['count'] for row in data]

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))

    # Create bar chart
    colors = plt.cm.Pastel1(range(len(accounts)))
    bars = ax.bar(range(len(accounts)), amounts, color=colors, edgecolor='black', linewidth=1.5)

    # Customize
    ax.set_xticks(range(len(accounts)))
    ax.set_xticklabels(accounts, rotation=45, ha='right')
    ax.set_ylabel('Total Spending ($)', fontsize=12, fontweight='bold')
    ax.set_title('Spending by Account', fontsize=16, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)

    # Add value labels
    for bar, amount, count in zip(bars, amounts, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, height,
                f'${amount:,.0f}\n({count} txns)',
                ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Save
    filename = output_dir / f'spending_by_account_{datetime.now().strftime("%Y%m%d")}.png'
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()

    return filename


def main():
    print("=" * 100)
    print("   📊 Chart Generator")
    print("=" * 100)

    if not HAS_MATPLOTLIB:
        return

    db = DatabaseManager()
    output_dir = create_output_dir()

    print("\nGenerating charts...\n")

    charts_created = []

    # Generate all charts
    print("1/5 Creating spending by category (pie chart)...")
    file1 = spending_by_category_pie(db, output_dir)
    if file1:
        charts_created.append(('Spending by Category (Pie)', file1))

    print("2/5 Creating spending by category (bar chart)...")
    file2 = spending_by_category_bar(db, output_dir)
    if file2:
        charts_created.append(('Spending by Category (Bar)', file2))

    print("3/5 Creating monthly trend chart...")
    file3 = monthly_spending_trend(db, output_dir)
    if file3:
        charts_created.append(('Monthly Spending Trend', file3))

    print("4/5 Creating category trends over time...")
    file4 = category_trend_over_time(db, output_dir)
    if file4:
        charts_created.append(('Category Trends Over Time', file4))

    print("5/5 Creating spending by account...")
    file5 = spending_by_account(db, output_dir)
    if file5:
        charts_created.append(('Spending by Account', file5))

    # Summary
    print("\n" + "=" * 100)
    print("   ✅ Charts Generated!")
    print("=" * 100)

    for chart_name, filepath in charts_created:
        size_kb = filepath.stat().st_size / 1024
        print(f"\n📊 {chart_name}")
        print(f"   File: {filepath}")
        print(f"   Size: {size_kb:.1f} KB")

    print(f"\n💡 All charts saved in: {output_dir}/")
    print("   Open them to view your spending insights!\n")

    db.close()


if __name__ == "__main__":
    main()