#!/bin/bash
# Automated cleanup script for Cashflow Tracker

echo "============================================"
echo "  Cashflow Tracker Cleanup"
echo "============================================"
echo ""
echo "This will delete redundant/old files"
echo "Your data and main app will NOT be touched"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Creating backup first..."
cd ..
BACKUP_NAME="cashflow_tracker_backup_$(date +%Y%m%d_%H%M%S)"
cp -r cashflow_tracker_clean "$BACKUP_NAME"
echo "✅ Backup created: $BACKUP_NAME"
echo ""

cd cashflow_tracker_clean

echo "Cleaning up..."

# Delete failed .app bundle attempts
echo "  Removing .app bundle files..."
rm -rf "Cashflow Tracker.app" 2>/dev/null
rm build_app.sh build_simple.sh fix_app.sh test_app.sh run_from_bundle.sh 2>/dev/null

# Delete one-time fix scripts
echo "  Removing one-time scripts..."
rm fix_reversed_rules.py test_import.py 2>/dev/null

# Delete old documentation
echo "  Removing old docs..."
rm WEEK1_COMPLETE.md WEEK3_GUIDE.md WEEK4_SCHEDULED_IMPORTS.md 2>/dev/null
rm PYCHARM_SETUP.md EXECUTABLE_GUIDE.md MAKE_EXECUTABLE.md 2>/dev/null
rm DATA_MODEL.md MERCHANT_EXPORT_GUIDE.md TRANSACTION_TYPES_GUIDE.md 2>/dev/null
rm AMEX_CSV_MIGRATION.md 2>/dev/null

# Delete unused automation files
echo "  Removing unused automation..."
rm automated_import.py com.cashflow.monthly-import.plist 2>/dev/null
rm setup_scheduled_import.sh setup_scheduled_import_v2.sh setup.sh 2>/dev/null

# Delete unused CLI scripts
echo "  Removing unused scripts..."
rm scripts/analyze_merchants.py scripts/cleanup_merchants.py 2>/dev/null
rm scripts/edit_categories.py scripts/find_duplicates.py 2>/dev/null
rm scripts/fix_miscategorized_transfers.py 2>/dev/null
rm scripts/interactive_categorize.py scripts/manage_rules.py 2>/dev/null
rm scripts/quick_summary.py scripts/spending_analysis.py 2>/dev/null
rm scripts/test_keyword_extraction.py 2>/dev/null
rm scripts/view_notes.py scripts/view_uncategorized.py 2>/dev/null

# Delete build artifacts
echo "  Removing build artifacts..."
rm -rf build dist setup.py 2>/dev/null
rm -rf __pycache__ src/__pycache__ 2>/dev/null

# Delete macOS junk
echo "  Removing macOS junk..."
find . -name ".DS_Store" -delete 2>/dev/null

# Delete empty log files
find logs -type f -size 0 -delete 2>/dev/null

echo ""
echo "============================================"
echo "  Cleanup Complete!"
echo "============================================"
echo ""
echo "✅ Deleted: Redundant files and old docs"
echo "✅ Kept: Main app, data, essential scripts"
echo "✅ Backup: ../$BACKUP_NAME"
echo ""
echo "Your app is now cleaner and easier to navigate!"
echo ""