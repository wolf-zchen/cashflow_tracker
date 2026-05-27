# Example Files

All files in this folder use **synthetic data** — no real bank information. They exist so contributors and curious users can try the import flow without having to wait until they have their own bank exports on hand.

## Quick demo (recommended for first launch)

If the app is empty, the Import tab shows a **📊 Load Demo Data** button that pulls in [`demo_transactions.csv`](demo_transactions.csv) — a Monarch-format file with 20 rows across multiple accounts. Easiest way to see the dashboard populate.

## Per-bank sample CSVs

Each file matches the actual column layout of that bank's CSV export. Drop them onto the **📁 Select CSV Files to Import** button and the app will detect the format automatically.

| File | Bank format | Demonstrates |
|---|---|---|
| [`Chase9707_sample.csv`](Chase9707_sample.csv) | Chase credit card | `Type` column with `Sale` / `Return` / `Payment` / `Fee` rows — exercises the refund-sign fix |
| [`Chase1234_Activity_sample.csv`](Chase1234_Activity_sample.csv) | Chase checking | Direct deposits, ACH debits, ATM withdrawals, Zelle credits |
| [`Amex_sample.csv`](Amex_sample.csv) | American Express CSV | Charges (positive) + payments/refunds (negative) — exercises Amex sign convention |
| [`BOA_0424_sample.csv`](BOA_0424_sample.csv) | Bank of America credit card | Mix of expenses, refunds, BofA payment |
| [`CapitalOne_sample.csv`](CapitalOne_sample.csv) | Capital One | `Transaction Type=Credit/Debit` column |
| [`demo_transactions.csv`](demo_transactions.csv) | Monarch Money export | All accounts in one file, pre-signed amounts |

## What to expect after importing

After importing all five bank files plus the demo:

- ~80 transactions across 6 different accounts
- Dashboard shows ~$5,000 in expenses and ~$4,000 in income for April 2026
- Auto-cleanup pipeline will report something like `fixed N refund sign(s), categorized M, fixed 3 CC payment(s), fixed 1 ATM withdrawal(s)` — verifying every fix is doing its job

## Adding more samples

If you add a new bank parser, please drop a synthetic sample CSV here so others can verify your parser without a real account at that bank. Rules:

- All amounts, account numbers, and merchant names must be fictional
- Keep it short (10–20 rows is plenty)
- Cover the interesting edge cases that motivated your parser (refunds, payments, fees, etc.)
