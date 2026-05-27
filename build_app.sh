#!/bin/bash
# Build Cashflow Tracker as a macOS .app bundle
# Run from the project root: ./build_app.sh

set -e
cd "$(dirname "$0")"

echo "=== Cashflow Tracker — macOS App Builder ==="
echo ""

# ── 1. Install PyInstaller if missing ────────────────────────────────────────
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# ── 2. Clean previous builds ─────────────────────────────────────────────────
echo "Cleaning previous builds..."
rm -rf build/ dist/

# ── 3. Build ──────────────────────────────────────────────────────────────────
echo "Building app (this takes ~1-2 minutes)..."
pyinstaller CashflowTracker.spec

# ── 4. Fix data directory inside the bundle ───────────────────────────────────
# The app needs a writable data dir for the SQLite database.
# On macOS, the bundle's Resources folder is read-only after signing,
# so we point the app at ~/Library/Application Support/CashflowTracker instead.
echo ""
echo "=== Build complete! ==="
echo ""
echo "Your app is at: dist/Cashflow Tracker.app"
echo ""
echo "To install: drag 'dist/Cashflow Tracker.app' to your Applications folder."
echo ""
echo "NOTE: On first launch macOS may show 'unidentified developer' warning."
echo "To open anyway: right-click the app → Open → Open"
echo "Or run: xattr -cr 'dist/Cashflow Tracker.app'"
