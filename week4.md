# Week 4: Automated Scheduled Imports Guide

## 🎉 What You Got

Week 4 adds **automated monthly imports** - Just download CSVs, everything else happens automatically!

### New Features:
1. **Automated Import Script** - One command to import → categorize → classify → summarize
2. **Monthly Scheduler** - Runs automatically on the 1st of every month
3. **Smart Logging** - Track what was imported and when
4. **Zero manual work** after downloading CSVs

---

## 🚀 Quick Start

### One-Time Setup

```bash
# Run the setup script
./setup_scheduled_import.sh
```

That's it! Your system is now configured to run automatically every month.

---

## 📅 How It Works

### Monthly Workflow (Automated)

```
Day 1 of month, 9:00 AM →
  Script runs automatically →
  Checks data/raw/ for CSVs →
  Imports new transactions →
  Auto-categorizes →
  Classifies types (expense/transfer/income) →
  Generates summary →
  Saves log →
  Done!
```

### Your Workflow (Manual Part)

```
End of month:
  1. Download CSVs from banks (5 min)
  2. Drop in data/raw/ folder
  3. Wait for 1st of next month
  4. Check logs/ to see what was imported
```

**Or run manually anytime:**
```bash
python automated_import.py
```

---

## 🧪 Testing Before Scheduling

### Test the Automated Import

```bash
# Put some test CSVs in data/raw/
cp ~/Downloads/Chase*.csv data/raw/
cp ~/Downloads/activity.csv data/raw/

# Run the automation manually
python automated_import.py
```

**Expected output:**
```
==================================================================
   🤖 Automated Monthly Import Workflow
==================================================================

[2026-02-16 14:30:00] Step 1: Importing new files...
[2026-02-16 14:30:00] Found 3 file(s) to process
[2026-02-16 14:30:01]   Processing: Chase_2025.csv
[2026-02-16 14:30:01]     ✅ Imported 85 new transaction(s), 0 duplicate(s)
[2026-02-16 14:30:02]   Processing: activity.csv
[2026-02-16 14:30:02]     ✅ Imported 42 new transaction(s), 0 duplicate(s)
[2026-02-16 14:30:02] ✅ Import complete: 127 total new transactions

[2026-02-16 14:30:02] Step 2: Auto-categorizing transactions...
[2026-02-16 14:30:03]   Found 127 uncategorized transaction(s)
[2026-02-16 14:30:04]   ✅ Categorized 112 transaction(s)
[2026-02-16 14:30:04]      Built-in rules: 98
[2026-02-16 14:30:04]      Learned rules:  14

[2026-02-16 14:30:04] Step 3: Classifying transaction types...
[2026-02-16 14:30:05]   Found 127 unclassified transaction(s)
[2026-02-16 14:30:05]   ✅ Classified 127 transaction(s)

[2026-02-16 14:30:05] Step 4: Standardizing merchant names...
[2026-02-16 14:30:05]   ⏭️  Skipping (merchant column not added yet)

[2026-02-16 14:30:05] Step 5: Generating summary...

======================================================================
  📊 Current Month Summary (2026-02)
======================================================================
  Total Transactions: 342
  Total Spending:     $8,543.21
  Total Income:       $12,000.00
  Net:                $3,456.79
  Uncategorized:      15
======================================================================

[2026-02-16 14:30:06] 📄 Results saved to: logs/import_20260216_143000.json

✅ Workflow completed successfully in 6.2 seconds

==================================================================
```

---

## 📂 File Structure

```
cashflow_tracker/
├── automated_import.py          # Main automation script
├── setup_scheduled_import.sh    # One-time setup
├── data/
│   └── raw/                     # Drop CSVs here
├── logs/
│   ├── monthly_import.log       # Standard output
│   ├── monthly_import_error.log # Errors (if any)
│   └── import_*.json            # Detailed results
└── ~/Library/LaunchAgents/
    └── com.cashflow.monthly-import.plist  # macOS scheduler
```

---

## 🔧 Scheduler Configuration

### Default Schedule
- **When:** 1st of every month
- **Time:** 9:00 AM
- **What:** Runs `automated_import.py`

### Change the Schedule

Edit the plist file:
```bash
nano ~/Library/LaunchAgents/com.cashflow.monthly-import.plist
```

**Run on different day:**
```xml
<key>Day</key>
<integer>15</integer>  <!-- 15th instead of 1st -->
```

**Run at different time:**
```xml
<key>Hour</key>
<integer>20</integer>   <!-- 8 PM instead of 9 AM -->
<key>Minute</key>
<integer>30</integer>   <!-- 8:30 PM -->
```

**Run weekly (every Monday):**
```xml
<key>Weekday</key>
<integer>1</integer>    <!-- Monday -->
```

**After editing, reload:**
```bash
launchctl unload ~/Library/LaunchAgents/com.cashflow.monthly-import.plist
launchctl load ~/Library/LaunchAgents/com.cashflow.monthly-import.plist
```

---

## 📊 Logs and Reports

### Check Last Run

```bash
# View the log
cat logs/monthly_import.log

# View detailed JSON results
cat logs/import_*.json | tail -1 | python -m json.tool
```

### JSON Log Format

```json
{
  "started_at": "2026-02-16T14:30:00",
  "steps": {
    "import": {
      "imported": 127,
      "files": [
        {
          "file": "Chase_2025.csv",
          "imported": 85,
          "duplicates": 0,
          "institution": "Chase"
        }
      ]
    },
    "categorize": {
      "categorized": 112
    },
    "classify": {
      "classified": 127
    },
    "summary": {
      "month": "2026-02",
      "transactions": 342,
      "spending": 8543.21,
      "income": 12000.00,
      "uncategorized": 15
    }
  },
  "completed_at": "2026-02-16T14:30:06",
  "duration_seconds": 6.2,
  "status": "success"
}
```

---

## 🛠️ Management Commands

### Check if Scheduler is Running

```bash
launchctl list | grep cashflow
```

**Output if running:**
```
-    0    com.cashflow.monthly-import
```

### Stop Scheduled Imports

```bash
launchctl unload ~/Library/LaunchAgents/com.cashflow.monthly-import.plist
```

### Start Scheduled Imports

```bash
launchctl load ~/Library/LaunchAgents/com.cashflow.monthly-import.plist
```

### Force Run Now (Test)

```bash
launchctl start com.cashflow.monthly-import
```

### Remove Completely

```bash
launchctl unload ~/Library/LaunchAgents/com.cashflow.monthly-import.plist
rm ~/Library/LaunchAgents/com.cashflow.monthly-import.plist
```

---

## 💡 Monthly Routine

### Your New Workflow

**End of Each Month:**
1. Download CSVs from all 3 banks (5 minutes)
2. Save to `data/raw/` folder
3. Done!

**1st of Next Month (Automatic):**
1. 9:00 AM - Script runs automatically
2. Imports everything
3. Categorizes
4. Classifies
5. Generates summary
6. Saves logs

**Check Results:**
```bash
# Quick view
tail -20 logs/monthly_import.log

# Or open dashboard
streamlit run dashboard.py
```

---

## 🎯 What Gets Automated

### ✅ Fully Automated
- Import CSVs from data/raw/
- Detect file formats automatically
- Deduplicate transactions
- Auto-categorize using built-in + learned rules
- Classify transaction types (expense/transfer/income)
- Generate monthly summary
- Log everything

### ⏭️ Still Manual
- Downloading CSVs from banks (5 min/month)
- Reviewing uncategorized transactions (if any)
- Merchant name cleanup (optional)

---

## 🐛 Troubleshooting

### Script didn't run automatically

**Check scheduler status:**
```bash
launchctl list | grep cashflow
```

**Check logs for errors:**
```bash
cat logs/monthly_import_error.log
```

**Common issues:**
- Python path wrong in plist file
- Project path wrong in plist file
- Permissions issue

**Fix:**
```bash
# Re-run setup
./setup_scheduled_import.sh
```

### No files imported

**Check data/raw/ folder:**
```bash
ls -la data/raw/
```

**Possible causes:**
- No CSV files in data/raw/
- All transactions are duplicates
- Wrong file format

### Categorization not working

**Run manually with verbose output:**
```bash
python automated_import.py
```

**Check learned rules:**
```bash
cat data/learned_rules.json
```

---

## 📧 Email Alerts (Coming Next)

Once you receive email alerts from your banks, we'll add:

1. **Email parser** - Reads transaction emails automatically
2. **Real-time updates** - Adds transactions as emails arrive
3. **Reconciliation** - Monthly CSV import catches any missed emails

**For now:** Scheduled monthly imports keep you 100% accurate!

---

## ✅ Summary

**What you have now:**
- 🤖 Automated import workflow
- 📅 Monthly scheduler (1st of every month, 9 AM)
- 📊 Automatic categorization
- 🏷️ Transaction type classification
- 📄 Detailed logging

**Your monthly effort:**
- Download CSVs: ~5 minutes
- Everything else: **Automatic!**

**Result:** 95% automated cashflow tracking! 🎉

---

## 🎊 Week 4 Complete!

You now have a **fully automated personal finance system**:

### ✅ Complete Feature Set
- Week 1: Import & parsing (3 banks)
- Week 2: Smart categorization with learning
- Week 3: Charts, dashboard, budgets
- Week 4: **Automated monthly imports** ⭐

### 📊 Your Monthly Workflow
1. Download CSVs (5 min)
2. Wait for scheduler
3. Check dashboard
4. Done!

**Next:** When email alerts start arriving, we'll add real-time email parsing for instant updates! 🚀