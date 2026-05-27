# Cashflow Tracker - Mac GUI Application

## 🎉 What You Got

A complete **Mac desktop application** with:
- ✅ **CSV Import** - Drag & drop or browse for files
- ✅ **Transaction Editor** - Edit categories and notes
- ✅ **Rule Manager** - Add/edit/delete categorization rules
- ✅ **Category Summary** - View spending by category
- ✅ **One-click executable** - Double-click to run

---

## 🚀 Quick Start

### Option 1: Run Directly (For Development)

```bash
python cashflow_app.py
```

### Option 2: Build Mac App (For Daily Use)

```bash
# Build the .app
./build_app.sh

# Opens in dist/
open dist/

# Double-click "Cashflow Tracker.app"
```

---

## 📱 App Interface

### Tab 1: 📥 Import
**Import CSV files from your banks**

1. Click "📁 Select CSV Files"
2. Choose one or more CSV files
3. Click "Open"
4. View results in the text area

**Buttons:**
- **Select CSV Files** - Import transactions
- **Auto-Categorize** - Apply categorization rules
- **Classify Types** - Mark as expense/transfer/income

### Tab 2: 💰 Transactions
**View and edit all transactions**

**Features:**
- Filter by text (searches description and category)
- Show 50/100/200/500/All transactions
- Sort by clicking column headers
- Double-click to edit
- Right-click menu (future)

**Columns:**
- ID - Transaction ID
- Date - Transaction date
- Description - Merchant name
- Amount - Dollar amount
- Category - Current category
- Account - Bank account
- Type - expense/income/transfer

**Edit Transaction:**
1. Double-click a row (or select + click "Edit")
2. Change category
3. Add notes
4. Click "Save"

### Tab 3: 📋 Rules
**Manage categorization rules**

**Left Panel: Current Rules**
- View all learned rules
- See keyword count per category
- Delete rules

**Right Panel: Add New Rule**
1. Enter category name
2. Enter keyword
3. Click "Save Rule"

**Example:**
```
Category: Groceries
Keyword: WHOLE

→ All transactions with "WHOLE" in description
  will be categorized as "Groceries"
```

### Tab 4: 🏷️ Categories
**View spending summary**

Shows for each category:
- Number of transactions
- Total amount spent
- Average transaction amount

Sorted by total spending (highest first)

---

## 🎯 Common Workflows

### Import Monthly CSV Files

1. **Download CSVs** from all banks
2. **Open app** (double-click Cashflow Tracker.app)
3. **Go to Import tab**
4. **Click "Select CSV Files"**
5. **Choose all CSVs**
6. **Click "Auto-Categorize"**
7. **Click "Classify Types"**
8. **Switch to Transactions tab** - Review results

### Edit a Transaction

1. **Go to Transactions tab**
2. **Find the transaction** (use filter if needed)
3. **Double-click** the row
4. **Change category** or add notes
5. **Click Save**

### Add a Categorization Rule

1. **Go to Rules tab**
2. **Enter category** (e.g., "Coffee")
3. **Enter keyword** (e.g., "STARBUCKS")
4. **Click "Save Rule"**
5. **Go to Import tab** → Click "Auto-Categorize"
6. All matching transactions updated!

### Review Spending

1. **Go to Categories tab**
2. **View breakdown** by category
3. **Click "Refresh"** to update

---

## 🔧 Building the Mac App

### Prerequisites

```bash
# Install py2app
pip install py2app --break-system-packages
```

### Build Process

```bash
# Run the build script
./build_app.sh
```

**What it does:**
1. Creates setup.py
2. Bundles Python + all dependencies
3. Creates Cashflow Tracker.app in dist/

### Use the App

```bash
# Option 1: Run from dist/
open dist/Cashflow\ Tracker.app

# Option 2: Move to Applications
cp -r dist/Cashflow\ Tracker.app /Applications/

# Then: Open from Launchpad or Applications folder
```

---

## 📂 File Structure

```
cashflow_tracker/
├── cashflow_app.py          # Main GUI application
├── build_app.sh             # Build script for .app
├── automated_import.py      # CLI automation (still works!)
├── src/                     # Core modules
│   ├── database.py
│   ├── parsers/
│   ├── categorization.py
│   └── learned_rules.py
├── data/
│   ├── transactions.db      # Your database
│   ├── learned_rules.json   # Your rules
│   └── raw/                 # Drop CSVs here (optional)
└── dist/
    └── Cashflow Tracker.app # Mac application
```

---

## 🎨 Customization

### Change App Icon

1. Create icon.icns file (use https://cloudconvert.com/png-to-icns)
2. Place in project root
3. Rebuild app

### Change Colors/Fonts

Edit `cashflow_app.py`:

```python
# Line ~xx - Change title font
font=('Arial', 16, 'bold')  # Change to your preference

# Line ~xx - Change colors
bg='#f0f0f0'  # Background color
fg='#333333'  # Text color
```

### Add More Features

The app is modular! Add new tabs by:

1. Create new `create_NEWTAB_tab()` method
2. Add to `create_notebook()` 
3. Implement functionality

---

## 💡 Tips & Tricks

### Keyboard Shortcuts

- **⌘Q** - Quit app
- **⌘W** - Close window
- **Return** - Edit selected transaction (when focused)

### Fast Filtering

Type in filter box to instantly search:
- Merchant names
- Categories
- Any text in description

### Batch Operations

1. Import multiple CSVs at once
2. Auto-categorize all uncategorized
3. Classify all types with one click

### Data Safety

- Database auto-saves on every change
- Original CSVs not modified
- Duplicate prevention built-in

---

## 🐛 Troubleshooting

### App won't open

**Problem:** "Cannot be opened because the developer cannot be verified"

**Fix:**
```bash
# Remove quarantine flag
xattr -cr dist/Cashflow\ Tracker.app

# Then open normally
```

### Import not working

**Check:**
1. CSV format correct (from supported banks)
2. File permissions (can Python read it?)
3. Check Import Results text area for errors

### Rules not applying

**Check:**
1. Keyword is uppercase
2. Keyword exists in transaction description
3. Click "Auto-Categorize" after adding rules
4. Check Rules tab to verify rule was saved

### Database locked

**Problem:** "Database is locked"

**Fix:**
```bash
# Close all instances of the app
# Make sure no other scripts accessing database
# Restart app
```

---

## 🔄 CLI vs GUI

### Both Work Together!

**GUI App:**
- Visual interface
- Edit transactions easily
- Manage rules visually
- Good for: Daily use, reviewing data

**CLI Scripts:**
- `automated_import.py` - Automation
- `generate_charts.py` - Charts
- `dashboard.py` - Streamlit dashboard
- Good for: Automation, analysis

**Use both:**
- GUI for everyday editing
- CLI for automation & charts
- Same database, same rules!

---

## 📊 Data Export

### From GUI

Currently: Use CLI tools

```bash
python scripts/export_data.py
```

### Future: Add Export to GUI

Request in next update!

---

## ✅ Complete Feature List

### Import & Processing
- ✅ CSV import (Chase, Amex, BofA)
- ✅ Duplicate detection
- ✅ Auto-categorization
- ✅ Transaction type classification

### Transaction Management
- ✅ View all transactions
- ✅ Filter/search
- ✅ Edit categories
- ✅ Add notes
- ✅ Delete transactions

### Rules Management
- ✅ Add learned rules
- ✅ View all rules
- ✅ Delete rules
- ✅ Test rules (auto-categorize)

### Analysis
- ✅ Category summary
- ✅ Transaction counts
- ✅ Spending totals

### Application
- ✅ Mac .app bundle
- ✅ Double-click to run
- ✅ Menu bar
- ✅ Tabbed interface
- ✅ Status bar

---

## 🎊 You're Ready!

### To Use:

**Development:**
```bash
python cashflow_app.py
```

**Production:**
```bash
./build_app.sh
open dist/Cashflow\ Tracker.app
```

**Daily Workflow:**
1. Download CSVs from banks
2. Open Cashflow Tracker.app
3. Import → Auto-Categorize → Classify
4. Review transactions
5. Done!

**Everything in one app!** 🎉