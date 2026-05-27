# Public Release Progress

Tracking work to prepare Cashflow Tracker for public/GitHub sharing.

---

## ✅ Phase 1: Import page cleanup

**What changed:**
- Replaced 10-button grid on Import tab with a single big **📁 Select CSV Files to Import** button + **⚙ Advanced ▾** dropdown.
- Auto-cleanup pipeline runs silently after every successful import.

**Files touched:** [cashflow_app.py](cashflow_app.py)
- `create_import_tab()` — UI redesign (line ~210)
- `import_csv()` — calls `_run_post_import_cleanup()` after import
- New helpers added: `_run_post_import_cleanup`, `_auto_categorize_uncategorized`, `_auto_fix_cc_payments`, `_auto_fix_atm_withdrawals`, `_auto_fix_duplicate_categories`, `_auto_merge_duplicate_accounts`, `_supported_institutions_hint`

**Pipeline steps (all silent, return counts):**
1. Categorize 'Uncategorized' rows via learned + built-in rules (does NOT overwrite existing)
2. Fix CC payments → mark as `transfer`
3. Flip ATM withdrawals `transfer → expense`
4. Merge case/whitespace-variant categories
5. Auto-merge duplicate accounts (high confidence only: same bank + same last-4 digits)

**Manual test:** launch app → click "Select CSV Files" → import → confirm summary line shows in results log; no popups except final "Import Complete".

**To roll back:** the original methods (`fix_cc_payments`, etc.) are unchanged — just remove the call to `_run_post_import_cleanup` in `import_csv` and restore the old UI block.

---

## ✅ Phase 2: Repo hygiene

**What changed:**
- [.gitignore](.gitignore) — expanded to block `data/*.db`, `data/raw/`, `logs/`, `exports/`, learned-rules JSON files
- [LICENSE](LICENSE) — added MIT
- [README.md](README.md) — full rewrite: tagline, supported banks list, quick start, layout, privacy, contributing

**Manual test:** open the repo on GitHub and confirm README renders correctly; `git status` shows `data/` is ignored.

**To roll back:** old `README.md` and `.gitignore` are in git history. `LICENSE` was new — delete if not desired.

---

## ✅ Phase 3: First-run UX

**What changed:**
- **Empty-state hint** on Import tab: when DB has zero transactions, shows a "👋 First time here?" line and a **📊 Load Demo Data** button. Disappears once data exists.
- **Bundled demo CSV**: [examples/demo_transactions.csv](examples/demo_transactions.csv) — 20 synthetic Monarch-format rows across May–April 2026 covering groceries, gas, rent, paychecks, CC payments, ATM withdrawal, etc.
- **Better unknown-format error**: instead of `❌ Unknown format`, now shows the list of supported banks + a tip about re-downloading the CSV.

**Files touched:** [cashflow_app.py](cashflow_app.py)
- `create_import_tab()` — added `_empty_state_frame`
- `load_demo_data()` — new method
- `_db_is_empty()` — new helper
- `import_csv()` — improved error message at "Unknown format" branch

**Manual test:**
1. Delete or move `data/transactions.db` aside
2. Launch app → Import tab should show "Load Demo Data" button
3. Click it → 20 transactions appear in Transactions tab + Dashboard tab populates
4. Try importing a random text file → error now says which banks were tried

**To roll back:** delete `examples/`, remove `_empty_state_frame` block from `create_import_tab`, remove `load_demo_data`/`_db_is_empty` methods.

---

## ✅ Phase 4: Settings tab + backup/restore + export

**What changed:**
- New **⚙ Settings** tab (7th tab in the notebook).
- Three sections:
  - **Data Safety** — "💾 Backup Database…" copies the SQLite file to a user-chosen location with a timestamped default filename. "♻ Restore Database…" replaces current DB after saving a safety copy first.
  - **Export** — "📤 Export Transactions to CSV…" exports rows in the **current global date range** (top of window) to a CSV.
  - **About** — shows the data directory path + license note.

**Files touched:** [cashflow_app.py](cashflow_app.py)
- `create_notebook()` — calls `create_settings_tab()`
- `create_settings_tab()` — new
- `backup_database()`, `restore_database()`, `export_transactions_csv()` — new

**Manual test:**
1. Open Settings tab
2. Backup → save somewhere → confirm `.db` file appears at chosen path
3. Set global date range to e.g. "2026-05-01 to 2026-05-31" → Export Transactions → open CSV, verify only May rows
4. Restore: pick a backup file → confirm restored, then restart app

**Known caveat:** Restore requires app restart to reflect; warning shown in the success dialog.

**To roll back:** remove the `self.create_settings_tab()` call and the four new methods (`create_settings_tab`, `backup_database`, `restore_database`, `export_transactions_csv`).

---

## ✅ Phase 5: Minimal CI + follow-ups doc

**What changed:**
- [.github/workflows/ci.yml](.github/workflows/ci.yml) — GitHub Action: syntax compile + import-time smoke test on Python 3.10/3.11/3.12 (Ubuntu, with Xvfb for Tk).
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to add a bank parser, style notes, and a **Known follow-ups** section that documents the deferred work (most importantly, splitting `cashflow_app.py`).

**Manual test:** push to a GitHub repo → Actions tab → "CI" workflow should pass.

**To roll back:** delete `.github/` and `CONTRIBUTING.md`.

---

## 🐛 Hotfix: Refund-as-expense double-counting

**Bug:** Chase credit-card refunds (e.g. `PAYPAL *FABLETICSLL` returns, `B&N MEMBERSHIP RENEWAL` credit) were stored as **expenses** with negative amounts, double-counting against the original charge.

**Root cause:** The Chase CSV `Type` column (`Sale` / `Return` / `Payment` / `Adjustment`) is the authoritative signal for direction, but [`chase_credit_parser.py`](src/parsers/chase_credit_parser.py) ignored it and just flipped the amount sign. The existing description-based refund detector only matched keywords like `REFUND` / `CREDIT` / `RETURN` — but most real refunds just show the merchant name (`PAYPAL *FABLETICSLL`).

**Fix:**
1. [`src/parsers/chase_credit_parser.py`](src/parsers/chase_credit_parser.py) — `parse()` now reads `row['Type']` and assigns sign accordingly:
   - `Sale` → negative (expense)
   - `Return` / `Refund` / `Adjustment` / `Reimbursement` → positive (income/refund)
   - `Payment` → kept as expense-side for now (gets reclassified as transfer later)
   - `Fee` → negative
   - Unknown → falls back to old sign-flip behavior
2. [`cashflow_app.py`](cashflow_app.py) — `_fix_credit_refund_amounts()` now does a second pass that decodes `raw_data` JSON and flips any row whose `Type` field is `Return` / `Refund` / `Adjustment` / `Reimbursement`. Also includes Discover accounts.
3. The refund fix is now part of the **auto-cleanup pipeline** ([`_run_post_import_cleanup`](cashflow_app.py)) so every import retroactively repairs sign errors. Runs **first** so categorization downstream sees correct amounts.
4. Summary line in results log now reports `fixed N refund sign(s)`.

**Manual test:**
1. Re-import your Chase credit CSV. Results log should say `fixed N refund sign(s)`.
2. Check the rows from your screenshot (`5011`, `5012`, `5016`, the Mar 17 B&N row, the Apr 22 "Payment Thank You-Mobile" row). They should now show **positive** amounts with `transaction_type='income'`.
3. Dashboard → Expenses total should drop by roughly `$165.09 + $89.20 + $92.44 + $27.56 + $40.00` ≈ $414. Income/refund total goes up by the same.
4. If anything still looks wrong, run `⚙ Advanced ▾ → Classify Types` (which calls `_fix_credit_refund_amounts` directly).

**To roll back:** revert the changes in `chase_credit_parser.py` parse() method and `_fix_credit_refund_amounts` in cashflow_app.py.

### Parser audit (no other refund bugs)

Checked every parser for the same class of bug:

| Parser | Sign source | Verdict |
|---|---|---|
| Chase Credit | `Type` column (fixed) | Was buggy, now correct |
| Chase Checking | Pre-signed `Amount` | ✓ |
| Amex CSV | Sign flip; Amex exports refunds as negative | ✓ |
| Amex Excel | Same as Amex CSV | ✓ |
| BofA | Pre-signed `Amount` | ✓ |
| Capital One | `Transaction Type` (Credit/Debit) | ✓ |
| Monarch | Pre-signed `Amount` | ✓ |

### Bonus fix: Chase "Payment Thank You" rows

Apr 22 row `Payment Thank You-Mobile -$40.00` in your screenshot was being stored as an expense — it's a payment from checking → card and should be `transfer`. Two changes:

1. [`_auto_fix_cc_payments`](cashflow_app.py): added patterns `payment thank you`, `mobile payment.*thank you`, `online payment.*thank you`, `ach payment`, `electronic payment`.
2. Same method now also flips any row whose `raw_data` `Type=='Payment'` (Chase's explicit signal), regardless of description.

**Manual test:** after re-import, the Apr 22 `Payment Thank You-Mobile` row should show `transaction_type='transfer'` and category `Credit Card Payment`.

---

## Deferred (documented in [CONTRIBUTING.md](CONTRIBUTING.md))

These were in the original plan but deferred — most because they need foundation work first:

- **Split `cashflow_app.py` into per-tab modules** — risky without tests; add unit tests around DB + parsers first.
- **Generic CSV column-mapper** fallback when no parser matches.
- **Drag-and-drop CSV** onto the Import tab (needs `tkinterdnd2`).
- **Recurring-transaction detection** in Dashboard.
- **Budget targets per category** with progress bars.
- **Dark mode** via ttk theme switch.

---

## Testing checklist for you

Run through these to verify everything before you share publicly:

- [ ] Phase 1: import a fresh CSV → no popups, single summary line in results log
- [ ] Phase 1: `⚙ Advanced ▾` menu opens, every old tool still works
- [ ] Phase 2: README renders on GitHub; `data/` not committed
- [ ] Phase 3: delete DB → empty-state shows demo button → click loads 20 rows
- [ ] Phase 3: import a non-bank text file → error names supported banks
- [ ] Phase 4: backup → file lands in chosen location
- [ ] Phase 4: export CSV → contents match the global date filter
- [ ] Phase 4: restore from backup → safety copy created, restart works
- [ ] Phase 5: GitHub Action passes on push

## Quick rollback to "everything before"

```bash
git diff HEAD~N --stat   # see all changed files
git checkout HEAD~N -- cashflow_app.py   # revert just the app file
```

(Adjust `N` to the commit before this batch.)
