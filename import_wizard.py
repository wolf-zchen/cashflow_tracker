#!/usr/bin/env python3
"""
Smart Import Wizard for Cashflow Tracker

This script automatically detects bank formats and imports transactions.
Usage:
    python import_wizard.py
    
    Then follow the prompts or place CSV/Excel files in data/raw/ folder.
"""
import sys
from pathlib import Path
from tabulate import tabulate

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers import detect_parser, get_parser_info
from src.database import DatabaseManager


def print_header():
    """Print welcome header"""
    print("\n" + "="*60)
    print("   CASHFLOW TRACKER - Smart Import Wizard")
    print("="*60 + "\n")


def scan_for_files(data_dir: Path):
    """Scan data/raw directory for CSV/Excel files"""
    raw_dir = data_dir / 'raw'
    
    # Supported file extensions
    patterns = ['*.csv', '*.CSV', '*.xlsx', '*.xls']
    
    files = []
    for pattern in patterns:
        files.extend(raw_dir.glob(pattern))
    
    return sorted(files)


def get_account_name(file_path: Path, parser_info: dict) -> str:
    """
    Extract or prompt for account name based on filename.
    
    Tries to extract last 4 digits from filename, otherwise prompts user.
    """
    filename = file_path.stem
    
    # Try to extract last 4 digits from filename
    import re
    last_four_match = re.search(r'(\d{4})', filename)
    
    if last_four_match:
        last_four = last_four_match.group(1)
        account_type_short = {
            'credit_card': 'CC',
            'checking': 'Checking',
            'savings': 'Savings'
        }.get(parser_info['account_type'], 'Account')
        
        suggested_name = f"{parser_info['institution']} {account_type_short} *{last_four}"
        
        print(f"\nSuggested account name: {suggested_name}")
        response = input("Press Enter to use this name, or type a custom name: ").strip()
        
        if response:
            return response
        else:
            return suggested_name
    else:
        # Prompt for account name
        print(f"\nFile: {file_path.name}")
        print(f"Institution: {parser_info['institution']}")
        print(f"Account Type: {parser_info['account_type']}")
        account_name = input("Enter account name (e.g., 'Chase CC *1234'): ").strip()
        
        if not account_name:
            # Generate a default name
            account_name = f"{parser_info['institution']} {parser_info['account_type']}"
        
        return account_name


def import_file(file_path: Path, db: DatabaseManager):
    """Import a single file"""
    print(f"\n{'='*60}")
    print(f"Processing: {file_path.name}")
    print('='*60)
    
    # Detect parser
    parser = detect_parser(file_path)
    
    if not parser:
        print(f"❌ Could not detect file format for: {file_path.name}")
        print("   This file will be skipped.\n")
        return False
    
    parser_info = get_parser_info(file_path)
    print(f"✓ Detected: {parser_info['institution']} - {parser_info['account_type']}")
    
    # Get account name
    account_name = get_account_name(file_path, parser_info)
    
    # Add account to database
    # Try to extract last 4 digits
    import re
    last_four_match = re.search(r'(\d{4})', account_name)
    last_four = last_four_match.group(1) if last_four_match else None
    
    db.add_account(
        name=account_name,
        institution=parser_info['institution'],
        account_type=parser_info['account_type'],
        last_four=last_four
    )
    
    # Parse transactions
    print(f"📊 Parsing transactions...")
    try:
        transactions = parser.parse(file_path, account_name)
        
        if not transactions:
            print(f"⚠️  No transactions found in file")
            return False
        
        print(f"✓ Found {len(transactions)} transactions")
        
        # Convert to dict format for database
        transaction_dicts = [t.to_dict() for t in transactions]
        
        # Add to database
        print(f"💾 Importing to database...")
        added_count, duplicate_count = db.add_transactions(transaction_dicts)
        
        # Log the import
        db.log_import(
            file_name=file_path.name,
            account_name=account_name,
            institution=parser_info['institution'],
            count=added_count
        )
        
        print(f"✅ Successfully imported {added_count} new transactions")
        if added_count < len(transactions):
            print(f"   ({len(transactions) - added_count} duplicates skipped)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error parsing file: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def show_summary(db: DatabaseManager):
    """Show summary of imported data"""
    print("\n" + "="*60)
    print("   IMPORT SUMMARY")
    print("="*60 + "\n")
    
    # Total transactions
    total = db.get_transaction_count()
    print(f"Total transactions in database: {total}")
    
    # Accounts
    accounts = db.get_accounts()
    if accounts:
        print(f"\nAccounts ({len(accounts)}):")
        account_data = []
        for acc in accounts:
            account_data.append([
                acc['name'],
                acc['institution'],
                acc['account_type']
            ])
        print(tabulate(account_data, headers=['Account', 'Institution', 'Type'], tablefmt='simple'))
    
    # Ask if user wants to see spending summary
    print("\n" + "-"*60)
    response = input("\nShow spending summary? (y/n): ").strip().lower()
    
    if response == 'y':
        print("\n" + "="*60)
        print("   SPENDING SUMMARY")
        print("="*60 + "\n")
        
        total_spending = db.get_total_spending()
        print(f"Total spending: ${total_spending:,.2f}")
        
        print("\nBy category:")
        categories = db.get_spending_by_category()
        if categories:
            cat_data = []
            for cat in categories:
                cat_data.append([
                    cat['category'],
                    f"${abs(cat['total']):,.2f}",
                    cat['count']
                ])
            print(tabulate(cat_data, headers=['Category', 'Amount', 'Count'], tablefmt='simple'))


def main():
    """Main import wizard"""
    print_header()
    
    # Initialize database
    db = DatabaseManager()
    
    # Get project root directory
    project_dir = Path(__file__).parent
    data_dir = project_dir / 'data'
    raw_dir = data_dir / 'raw'
    
    # Create directories if they don't exist
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Data directory: {raw_dir}")
    print(f"💾 Database: {db.db_path}")
    print()
    
    # Scan for files
    files = scan_for_files(data_dir)
    
    if not files:
        print("⚠️  No CSV or Excel files found in data/raw/")
        print("\nPlease place your bank CSV/Excel files in:")
        print(f"   {raw_dir}")
        print("\nThen run this script again.")
        return
    
    print(f"Found {len(files)} file(s) to import:\n")
    for i, f in enumerate(files, 1):
        print(f"  {i}. {f.name}")
    
    print("\n" + "-"*60)
    response = input("\nProceed with import? (y/n): ").strip().lower()
    
    if response != 'y':
        print("Import cancelled.")
        return
    
    # Import each file
    success_count = 0
    for file_path in files:
        if import_file(file_path, db):
            success_count += 1
    
    # Show summary
    print("\n" + "="*60)
    print(f"✅ Import complete: {success_count}/{len(files)} files imported successfully")
    print("="*60)
    
    # Show data summary
    show_summary(db)
    
    # Close database
    db.close()
    
    print("\n✨ All done! Your transactions are now in the database.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Import cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
