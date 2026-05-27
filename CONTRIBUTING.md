# Contributing

Thanks for considering a contribution! This is a small personal-finance app — keep PRs focused.

## Setup

```bash
git clone https://github.com/<you>/cashflow_tracker.git
cd cashflow_tracker
pip3 install -r requirements.txt
python3 cashflow_app.py
```

If you don't have any bank CSVs yet, click **📊 Load Demo Data** on the Import tab to populate a sample dataset.

## Adding a bank parser

1. Create `src/parsers/<bank>_parser.py` subclassing `BaseParser`
2. Implement:
   - `detect(file_path) -> bool` — match by inspecting columns / first few rows (not by filename)
   - `parse(file_path, account_name) -> List[Transaction]`
   - `get_account_name(file_path) -> str` — derive a readable account name
3. Register in [`src/parsers/__init__.py`](src/parsers/__init__.py) — note ordering matters; more-specific parsers go first
4. Test with a real (anonymized!) export from that bank

## Known follow-ups

These are intentionally not blocking a v1 release but worth doing later:

- **Split `cashflow_app.py`** (4000+ lines) into `tabs/import_tab.py`, `tabs/dashboard_tab.py`, etc. The class is monolithic right now — the only thing stopping the split is lack of unit tests to catch regressions during the move. Add tests first.
- **Generic CSV column-mapper**: a fallback UI when no parser matches, letting the user pick which columns map to date/amount/description.
- **Drag-and-drop CSVs** onto the Import tab (`tkinterdnd2`).
- **Recurring-transaction detection** in the dashboard (rent, subscriptions).
- **Budget targets per category** with progress bars.
- **Dark mode** via ttk theme switch.

## Style

- No new dependencies without discussion — keep the install footprint small.
- Existing code uses tabs/spaces inconsistently in places; don't reformat unrelated files in your PR.
- Avoid breaking the SQLite schema; if you must, add a migration in `DatabaseManager`.

## Privacy

Never commit a real bank CSV. The `.gitignore` blocks `data/`, but double-check before pushing.
