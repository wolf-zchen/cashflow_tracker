# Cashflow Tracker

A personal-finance desktop app that turns your bank CSVs into a clean picture of where your money goes. Local-first, no cloud, no signup — your data stays on your machine in a SQLite file.

![Built with Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## What it does

- **One-click import** of CSV/Excel exports from your banks — parsing, categorization, transfer/CC-payment detection, refund-sign correction, and duplicate-account merging all happen automatically
- **Dashboard** with monthly trends, category breakdowns, top spending
- **Conscious-spending plan** based on the 50/10/10/30 framework
- **Settings tab** with one-click backup/restore of your SQLite database and CSV export of any date range
- **Demo data** ships in the box — click "📊 Load Demo Data" on first launch to see the app in action without exposing your real finances
- **Streamlit browser dashboard** for deeper exploration

## Supported institutions

- Chase (checking + credit card)
- American Express (CSV + Excel)
- Bank of America (credit card)
- Capital One
- Discover
- Monarch Money exports

Each bank's parser lives in [`src/parsers/`](src/parsers/) — adding a new one is ~50 lines.

## Quick start

Requires Python 3.10+.

```bash
git clone https://github.com/<you>/cashflow_tracker.git
cd cashflow_tracker
pip3 install -r requirements.txt
python3 cashflow_app.py
```

On first launch you'll see an empty Import tab. Click **📁 Select CSV Files to Import** and pick the transaction exports you downloaded from your bank — the app figures out the format from the file contents, not the filename.

## Build a native Mac app

```bash
./build_app.sh
```

Produces `dist/Cashflow Tracker.app`. When running as a bundled app, user data is written to `~/Library/Application Support/CashflowTracker/` instead of the project directory. On first launch macOS may flag the app as "unidentified developer" — right-click → Open → Open, or run `xattr -cr "dist/Cashflow Tracker.app"`.

## Project layout

```
cashflow_tracker/
├── cashflow_app.py          # Main Tk desktop app
├── dashboard.py             # Streamlit browser dashboard
├── import_wizard.py         # CLI import (legacy, still works)
├── src/
│   ├── parsers/             # One file per bank
│   ├── database/            # SQLite manager
│   ├── categorization.py    # Built-in rules
│   ├── learned_rules.py     # Learned-from-history rules
│   └── duplicate_detection.py
└── data/                    # Local DB + JSON state (gitignored)
```

## Privacy

Your transactions never leave your machine. The database is plain SQLite at `data/transactions.db` (source install) or `~/Library/Application Support/CashflowTracker/transactions.db` (app bundle). `data/` is gitignored — don't commit it.

## Advanced

The Import tab has a **⚙ Advanced ▾** menu containing manual versions of every cleanup step that the auto-import already runs:

- **✨ Run All Cleanups Now** — applies the entire auto-pipeline to all existing transactions in one click. Use this after upgrading the app to retroactively apply improved rules to data you imported under an older version.
- Auto-Categorize (re-run on all rows)
- Classify Types (income/expense/transfer) — also flips refund signs on credit-card accounts
- Merge / Fix Duplicate Categories
- Find Duplicate Transactions
- Fix CC Payments / ATM Withdrawals
- Merge Accounts (manual rules for low-confidence cases)

You almost never need these in normal use; they're there for fixing historical data or debugging a new bank parser.

## What the auto-cleanup pipeline does

Every successful import (or click on **Run All Cleanups Now**) runs these passes silently in order:

1. **Refund-sign fix** — Chase credit-card exports use a `Type` column (`Sale` / `Return` / `Payment` / `Adjustment`) to distinguish refunds from charges. The pipeline flips any row whose `Type` is `Return`/`Refund`/`Adjustment` from negative (expense) to positive (income), so refunds don't double-count against the original charge.
2. **Auto-categorize** uncategorized rows using learned rules + built-in patterns. Existing categories are not overwritten.
3. **CC payments → transfers** — payments between your checking account and credit card are reclassified as transfers (excluded from spending totals).
4. **ATM withdrawals → expenses** — flips ATM rows from transfer to expense.
5. **Merge case/whitespace-variant categories** (e.g. `"groceries"` and `"Groceries"`).
6. **Auto-merge duplicate accounts** when bank + last-4 digits match (e.g. `Chase Credit *9707` and `Chase9707`). Anything ambiguous is left for the manual Merge Accounts dialog.

## Contributing

Adding a new bank parser:

1. Create `src/parsers/<bank>_parser.py` subclassing `BaseParser`
2. Implement `can_parse(file_path)` and `parse(file_path, account_name)`
3. Add it to the registry in `src/parsers/__init__.py`
4. Drop a sample CSV (with fake data!) in `data/raw/` and import it

## License

MIT — see [LICENSE](LICENSE).
