#!/usr/bin/env python3
"""
Cashflow Tracker - Mac GUI Application

A desktop app for managing your personal finances with:
- CSV import with drag & drop
- Transaction editing
- Category management
- Rule management
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkcalendar import DateEntry, Calendar
from pathlib import Path
import sys
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database import DatabaseManager
from src.parsers import detect_parser
from src.categorization import Categorizer
from src.learned_rules import LearnedRules
from src.category_mapper import CategoryMapper


def _get_data_dir() -> Path:
    """Return a writable data directory.

    When running as a frozen .app bundle (PyInstaller) the bundle directory
    itself is read-only, so we redirect user data to
    ~/Library/Application Support/CashflowTracker.
    When running from source we keep using the local data/ folder so that
    development workflow is unchanged.
    """
    if getattr(sys, 'frozen', False):
        # Running inside a PyInstaller bundle
        app_support = Path.home() / 'Library' / 'Application Support' / 'CashflowTracker'
        app_support.mkdir(parents=True, exist_ok=True)
        return app_support
    # Running from source
    return Path(__file__).parent / 'data'


class CashflowApp:
    """Main application window"""

    def __init__(self, root):
        self.root = root
        self.root.title("Cashflow Tracker")
        self.root.geometry("1200x800")

        # Initialize managers — use a writable data directory
        data_dir = _get_data_dir()
        self.db = DatabaseManager(str(data_dir / 'transactions.db'))
        self.learned_rules = LearnedRules(str(data_dir / 'learned_rules.json'))
        self.category_mapper = CategoryMapper(str(data_dir / 'category_mappings.json'))

        # Learn from existing data on startup
        self.category_mapper.learn_from_database(self.db)

        # Global shared date range vars (all tabs read from these)
        today = datetime.now()
        self.global_from_var = tk.StringVar(value=f"{today.year}-{today.month:02d}-01")
        self.global_to_var   = tk.StringVar(value=today.strftime("%Y-%m-%d"))

        # Alias every tab's date vars to the global ones
        self.dash_date_from_var = self.global_from_var
        self.dash_date_to_var   = self.global_to_var
        self.date_from_var      = self.global_from_var
        self.date_to_var        = self.global_to_var
        self.cat_date_from_var  = self.global_from_var
        self.cat_date_to_var    = self.global_to_var
        self.sp_date_from_var   = self.global_from_var
        self.sp_date_to_var     = self.global_to_var

        # Create UI
        self.create_menu()
        self.create_global_date_bar()
        self.create_status_bar()
        self.create_notebook()

        # Load initial data
        self.refresh_transactions()

    def create_global_date_bar(self):
        """Shared date range bar shown above all tabs."""
        bar = ttk.Frame(self.root, relief='flat', padding=(6, 4))
        bar.pack(fill='x', padx=5, pady=(2, 0))

        ttk.Label(bar, text="Date Range:", font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 6))

        self._date_picker(bar, self.global_from_var, self.refresh_all).pack(side='left', padx=2)
        ttk.Label(bar, text="→").pack(side='left', padx=4)
        self._date_picker(bar, self.global_to_var, self.refresh_all).pack(side='left', padx=2)

        ttk.Separator(bar, orient='vertical').pack(side='left', fill='y', padx=10)

        for label, cmd in [
            ("This Month", self.set_global_this_month),
            ("Last Month", self.set_global_last_month),
            ("This Year",  self.set_global_this_year),
            ("All Time",   self.set_global_all_time),
        ]:
            ttk.Button(bar, text=label, command=cmd, width=10).pack(side='left', padx=2)

    def refresh_all(self):
        """Refresh every data tab after a global date change."""
        try: self.refresh_dashboard()
        except Exception: pass
        try: self.refresh_transactions()
        except Exception: pass
        try: self.refresh_categories()
        except Exception: pass
        try: self.refresh_spending_plan()
        except Exception: pass

    def set_global_this_month(self):
        today = datetime.now()
        self.global_from_var.set(f"{today.year}-{today.month:02d}-01")
        self.global_to_var.set(today.strftime("%Y-%m-%d"))
        self.refresh_all()

    def set_global_last_month(self):
        from datetime import timedelta
        today = datetime.now()
        last_prev  = datetime(today.year, today.month, 1) - timedelta(days=1)
        first_prev = datetime(last_prev.year, last_prev.month, 1)
        self.global_from_var.set(first_prev.strftime("%Y-%m-%d"))
        self.global_to_var.set(last_prev.strftime("%Y-%m-%d"))
        self.refresh_all()

    def set_global_this_year(self):
        today = datetime.now()
        self.global_from_var.set(f"{today.year}-01-01")
        self.global_to_var.set(today.strftime("%Y-%m-%d"))
        self.refresh_all()

    def set_global_all_time(self):
        self.global_from_var.set("")
        self.global_to_var.set("")
        self.refresh_all()

    def _date_picker(self, parent, string_var, on_select=None):
        """Return a frame with a date Entry + calendar button bound to string_var."""
        frame = ttk.Frame(parent)
        ttk.Entry(frame, textvariable=string_var, width=11).pack(side='left')
        ttk.Button(frame, text="📅", width=2,
                   command=lambda: self._pick_date_into(string_var, on_select)).pack(side='left', padx=1)
        return frame

    def _pick_date_into(self, string_var, on_select=None):
        """Open an inline Calendar popup — delegates to module-level helper."""
        _pick_date_popup(self.root, string_var, on_select)

    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import CSV...", command=self.import_csv, accelerator="Cmd+I")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.quit, accelerator="Cmd+Q")

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Auto-Categorize All", command=self.auto_categorize_all)
        tools_menu.add_command(label="Classify Transaction Types", command=self.classify_types)
        tools_menu.add_command(label="Find Duplicates", command=self.find_duplicates)
        tools_menu.add_separator()
        tools_menu.add_command(label="Fix Duplicate Categories", command=self.fix_duplicate_categories)
        tools_menu.add_command(label="Merge Categories...", command=self.merge_categories)
        tools_menu.add_separator()
        tools_menu.add_command(label="Fix Account Names...", command=self.fix_account_names)

        # Attach menu to root window (works on all platforms)
        self.root.config(menu=menubar)

        # For macOS, also bind keyboard shortcuts
        self.root.bind('<Command-i>', lambda e: self.import_csv())
        self.root.bind('<Command-q>', lambda e: self.root.quit())

    def create_notebook(self):
        """Create tabbed interface"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Tab 1: Import
        self.create_import_tab()

        # Tab 2: Dashboard
        self.create_dashboard_tab()

        # Tab 3: Transactions
        self.create_transactions_tab()

        # Tab 4: Rules
        self.create_rules_tab()

        # Tab 5: Categories
        self.create_categories_tab()

        # Tab 6: Spending Plan (Conscious Spending)
        self.create_spending_plan_tab()

        # Tab 7: Settings
        self.create_settings_tab()

    def create_import_tab(self):
        """Create import tab"""
        import_frame = ttk.Frame(self.notebook)
        self.notebook.add(import_frame, text="📥 Import")

        # Title
        ttk.Label(
            import_frame,
            text="Import Transactions",
            font=('Arial', 18, 'bold')
        ).pack(pady=(30, 6))

        ttk.Label(
            import_frame,
            text="Select CSV or Excel files from your bank — we'll handle the rest.",
            font=('Arial', 11),
            foreground='#555'
        ).pack(pady=(0, 18))

        # Primary action
        primary_frame = ttk.Frame(import_frame)
        primary_frame.pack(pady=4)

        big_btn = tk.Button(
            primary_frame,
            text="📁  Select CSV Files to Import",
            command=self.import_csv,
            font=('Arial', 14, 'bold'),
            padx=24,
            pady=12,
            relief='raised',
            cursor='hand2'
        )
        big_btn.pack()

        # Empty-state hint + "Load Demo Data" button — only visible when DB is empty
        self._empty_state_frame = ttk.Frame(import_frame)
        if self._db_is_empty():
            ttk.Label(
                self._empty_state_frame,
                text="👋 First time here? Try the demo data to see the app in action:",
                font=('Arial', 10, 'italic'),
                foreground='#666'
            ).pack(pady=(12, 4))
            ttk.Button(
                self._empty_state_frame,
                text="📊 Load Demo Data",
                command=self.load_demo_data
            ).pack()
            self._empty_state_frame.pack(pady=4)

        # Supported institutions hint
        ttk.Label(
            import_frame,
            text=self._supported_institutions_hint(),
            font=('Arial', 9),
            foreground='#888'
        ).pack(pady=(8, 4))

        # Advanced menu (kept for power users / debugging)
        adv_frame = ttk.Frame(import_frame)
        adv_frame.pack(pady=(6, 10))

        adv_menubtn = ttk.Menubutton(adv_frame, text="⚙ Advanced ▾")
        adv_menu = tk.Menu(adv_menubtn, tearoff=0)
        adv_menubtn['menu'] = adv_menu

        adv_menu.add_command(label="✨ Run All Cleanups Now", command=self.run_all_cleanups_now)
        adv_menu.add_separator()
        adv_menu.add_command(label="🤖 Auto-Categorize…", command=self.auto_categorize_all)
        adv_menu.add_command(label="🏷️ Classify Types", command=self.classify_types)
        adv_menu.add_separator()
        adv_menu.add_command(label="🔀 Merge Categories…", command=self.merge_categories)
        adv_menu.add_command(label="🔧 Fix Duplicate Categories", command=self.fix_duplicate_categories)
        adv_menu.add_command(label="🔍 Find Duplicate Transactions", command=self.find_duplicates)
        adv_menu.add_command(label="📋 View Category Mappings", command=self.view_mappings)
        adv_menu.add_separator()
        adv_menu.add_command(label="💳 Fix CC Payments", command=self.fix_cc_payments)
        adv_menu.add_command(label="💵 Fix ATM Withdrawals", command=self.fix_atm_withdrawals)
        adv_menu.add_command(label="🏦 Merge Accounts…", command=self.merge_accounts)

        adv_menubtn.pack()

        # Results area
        ttk.Label(import_frame, text="Import Results:", font=('Arial', 12, 'bold')).pack(pady=(12, 4))

        self.import_results = scrolledtext.ScrolledText(
            import_frame,
            height=15,
            width=80,
            font=('Courier', 10)
        )
        self.import_results.pack(pady=10, padx=20, fill='both', expand=True)

    def create_dashboard_tab(self):
        """Create dashboard overview tab"""
        outer_frame = ttk.Frame(self.notebook)
        self.notebook.add(outer_frame, text="📊 Dashboard")

        # Scrollable canvas + scrollbar
        scroll_canvas = tk.Canvas(outer_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer_frame, orient='vertical', command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        scroll_canvas.pack(side='left', fill='both', expand=True)

        # Inner frame that holds all dashboard content
        dash_frame = ttk.Frame(scroll_canvas)
        dash_window = scroll_canvas.create_window((0, 0), window=dash_frame, anchor='nw')

        # Resize inner frame width to match canvas
        def _on_canvas_resize(event):
            scroll_canvas.itemconfig(dash_window, width=event.width)
        scroll_canvas.bind('<Configure>', _on_canvas_resize)

        # Update scroll region whenever content changes size
        def _on_frame_resize(event):
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox('all'))
        dash_frame.bind('<Configure>', _on_frame_resize)

        # Mouse-wheel scrolling
        def _on_mousewheel(event):
            scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        scroll_canvas.bind_all('<MouseWheel>', _on_mousewheel)

        # Title
        ttk.Label(
            dash_frame,
            text="Financial Dashboard",
            font=('Arial', 16, 'bold')
        ).pack(pady=10)

        # Browser dashboard button (date range is now in the global bar)
        control_frame = ttk.Frame(dash_frame)
        control_frame.pack(fill='x', padx=20, pady=5)
        ttk.Button(
            control_frame,
            text="🌐 Open in Browser",
            command=self.launch_browser_dashboard,
            width=18
        ).pack(side='left', padx=5)
        ttk.Button(control_frame, text="↺ Refresh", command=self.refresh_dashboard, width=10).pack(side='left', padx=5)

        # Summary metrics frame
        metrics_frame = ttk.LabelFrame(dash_frame, text="Summary Metrics", padding=10)
        metrics_frame.pack(fill='x', padx=20, pady=10)

        # Create 4 metric boxes
        metrics_grid = ttk.Frame(metrics_frame)
        metrics_grid.pack(fill='x')

        # Income metric
        income_box = ttk.Frame(metrics_grid, relief='solid', borderwidth=1)
        income_box.grid(row=0, column=0, padx=10, pady=5, sticky='ew')
        ttk.Label(income_box, text="💰 Income", font=('Arial', 10, 'bold')).pack(pady=5)
        self.income_label = ttk.Label(income_box, text="$0.00", font=('Arial', 18, 'bold'), foreground='green')
        self.income_label.pack(pady=5)

        # Expenses metric
        expense_box = ttk.Frame(metrics_grid, relief='solid', borderwidth=1)
        expense_box.grid(row=0, column=1, padx=10, pady=5, sticky='ew')
        ttk.Label(expense_box, text="💸 Expenses", font=('Arial', 10, 'bold')).pack(pady=5)
        self.expense_label = ttk.Label(expense_box, text="$0.00", font=('Arial', 18, 'bold'), foreground='red')
        self.expense_label.pack(pady=5)

        # Net metric
        net_box = ttk.Frame(metrics_grid, relief='solid', borderwidth=1)
        net_box.grid(row=0, column=2, padx=10, pady=5, sticky='ew')
        ttk.Label(net_box, text="📈 Net", font=('Arial', 10, 'bold')).pack(pady=5)
        self.net_label = ttk.Label(net_box, text="$0.00", font=('Arial', 18, 'bold'))
        self.net_label.pack(pady=5)

        # Transactions metric
        txn_box = ttk.Frame(metrics_grid, relief='solid', borderwidth=1)
        txn_box.grid(row=0, column=3, padx=10, pady=5, sticky='ew')
        ttk.Label(txn_box, text="📝 Transactions", font=('Arial', 10, 'bold')).pack(pady=5)
        self.txn_count_label = ttk.Label(txn_box, text="0", font=('Arial', 18, 'bold'))
        self.txn_count_label.pack(pady=5)

        # Make columns equal width
        for i in range(4):
            metrics_grid.columnconfigure(i, weight=1)

        # Monthly trends chart
        trends_frame = ttk.LabelFrame(dash_frame, text="Monthly Trends", padding=10)
        trends_frame.pack(fill='both', expand=True, padx=20, pady=10)

        self.trends_canvas = tk.Canvas(trends_frame, height=300, bg='white')
        self.trends_canvas.pack(fill='both', expand=True)

        # Category trends over time
        cat_trends_frame = ttk.LabelFrame(dash_frame, text="Expense Trends by Category (Top 5)", padding=10)
        cat_trends_frame.pack(fill='both', expand=True, padx=20, pady=10)

        self.cat_trends_canvas = tk.Canvas(cat_trends_frame, height=250, bg='white')
        self.cat_trends_canvas.pack(fill='both', expand=True)

        # Top categories
        top_cat_frame = ttk.LabelFrame(dash_frame, text="Top 5 Spending Categories", padding=10)
        top_cat_frame.pack(fill='x', padx=20, pady=10)

        self.top_categories_text = tk.Text(top_cat_frame, height=6, font=('Courier', 10))
        self.top_categories_text.pack(fill='x')

        # Initialize with current month
        self.set_dash_this_month()

    def set_dash_this_month(self): self.set_global_this_month()
    def set_dash_this_year(self):  self.set_global_this_year()
    def set_dash_all_time(self):   self.set_global_all_time()

    def launch_browser_dashboard(self):
        """Launch Streamlit dashboard in browser"""
        import subprocess
        import webbrowser
        import time
        from pathlib import Path

        # Check if dashboard.py exists
        dashboard_path = Path("dashboard.py")
        if not dashboard_path.exists():
            messagebox.showerror(
                "Dashboard Not Found",
                "dashboard.py not found in the project directory.\n\n" +
                "Make sure the Streamlit dashboard file exists."
            )
            return

        # Show info dialog
        msg = "Launching Streamlit dashboard in your browser...\n\n"
        msg += "The dashboard will open at: http://localhost:8501\n\n"
        msg += "To stop the dashboard:\n"
        msg += "1. Close the browser tab\n"
        msg += "2. Press Ctrl+C in the terminal (if visible)\n"
        msg += "3. Or restart this app\n\n"
        msg += "Continue?"

        if not messagebox.askyesno("Launch Browser Dashboard", msg):
            return

        try:
            # Launch Streamlit in background
            # Use subprocess.Popen to run in background
            subprocess.Popen(
                ["streamlit", "run", "dashboard.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Wait a moment for server to start
            time.sleep(2)

            # Open browser
            webbrowser.open("http://localhost:8501")

            self.status_var.set("Browser dashboard launched at http://localhost:8501")

        except FileNotFoundError:
            messagebox.showerror(
                "Streamlit Not Found",
                "Streamlit is not installed.\n\n" +
                "Install it with:\n" +
                "pip install streamlit --break-system-packages"
            )
        except Exception as e:
            messagebox.showerror(
                "Launch Error",
                f"Failed to launch dashboard:\n\n{str(e)}"
            )

    def refresh_dashboard(self):
        """Refresh dashboard metrics and charts"""
        date_from = self.dash_date_from_var.get()
        date_to = self.dash_date_to_var.get()

        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Build date filter
        date_filter = ""
        params = []
        if date_from:
            date_filter += " AND date >= ?"
            params.append(date_from)
        if date_to:
            date_filter += " AND date <= ?"
            params.append(date_to)

        # Get summary metrics
        cursor.execute(f"""
            SELECT 
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN amount < 0 AND (transaction_type = 'expense' OR transaction_type IS NULL) 
                    AND category NOT IN ('Credit Card Payment', 'Transfer') THEN ABS(amount) ELSE 0 END) as expenses,
                COUNT(*) as txn_count
            FROM transactions
            WHERE 1=1 {date_filter}
        """, params)

        metrics = cursor.fetchone()
        income = metrics['income'] or 0
        expenses = metrics['expenses'] or 0
        net = income - expenses
        txn_count = metrics['txn_count'] or 0

        # Update metric labels
        self.income_label.config(text=f"${income:,.2f}")
        self.expense_label.config(text=f"${expenses:,.2f}")
        self.net_label.config(text=f"${net:,.2f}")
        self.net_label.config(foreground='green' if net >= 0 else 'red')
        self.txn_count_label.config(text=f"{txn_count:,}")

        # Get monthly trends data
        cursor.execute(f"""
            SELECT 
                strftime('%Y-%m', date) as month,
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN amount < 0 AND (transaction_type = 'expense' OR transaction_type IS NULL)
                    AND category NOT IN ('Credit Card Payment', 'Transfer') THEN ABS(amount) ELSE 0 END) as expenses
            FROM transactions
            WHERE 1=1 {date_filter}
            GROUP BY month
            ORDER BY month
        """, params)

        monthly_data = cursor.fetchall()

        # Draw trends chart
        self.draw_monthly_trends(monthly_data)

        # Get top 5 categories for trends
        cursor.execute(f"""
            SELECT 
                category,
                SUM(ABS(amount)) as total
            FROM transactions
            WHERE amount < 0
              AND (transaction_type = 'expense' OR transaction_type IS NULL)
              AND category NOT IN ('Credit Card Payment', 'Transfer')
              {date_filter}
            GROUP BY category
            ORDER BY total DESC
            LIMIT 5
        """, params)

        top_5_cats = [row['category'] for row in cursor.fetchall()]

        # Get category trends over time for top 5
        if top_5_cats:
            placeholders = ','.join(['?' for _ in top_5_cats])
            trend_params = top_5_cats + params  # category IN (?) placeholders come before date_filter in the SQL

            cursor.execute(f"""
                SELECT 
                    strftime('%Y-%m', date) as month,
                    category,
                    SUM(ABS(amount)) as total
                FROM transactions
                WHERE amount < 0
                  AND (transaction_type = 'expense' OR transaction_type IS NULL)
                  AND category NOT IN ('Credit Card Payment', 'Transfer')
                  AND category IN ({placeholders})
                  {date_filter}
                GROUP BY month, category
                ORDER BY month, total DESC
            """, trend_params)

            category_trends = cursor.fetchall()
        else:
            category_trends = []

        # Draw category trends
        self.draw_category_trends(category_trends, top_5_cats)

        # Get top 5 categories summary
        cursor.execute(f"""
            SELECT 
                category,
                SUM(ABS(amount)) as total,
                COUNT(*) as count
            FROM transactions
            WHERE amount < 0
              AND (transaction_type = 'expense' OR transaction_type IS NULL)
              AND category NOT IN ('Credit Card Payment', 'Transfer')
              {date_filter}
            GROUP BY category
            ORDER BY total DESC
            LIMIT 5
        """, params)

        top_categories = cursor.fetchall()

        # Update top categories text
        self.top_categories_text.delete('1.0', 'end')
        total_top = sum(cat['total'] for cat in top_categories)

        for i, cat in enumerate(top_categories, 1):
            percent = (cat['total'] / total_top * 100) if total_top > 0 else 0
            line = f"{i}. {cat['category']:<25} ${cat['total']:>10,.2f}  ({percent:>5.1f}%)  {cat['count']:>3} txns\n"
            self.top_categories_text.insert('end', line)

    def draw_monthly_trends(self, data):
        """Draw monthly trends chart"""
        self.trends_canvas.delete('all')

        if not data:
            self.trends_canvas.create_text(
                400, 150,
                text="No data for selected period",
                font=('Arial', 12),
                fill='black'
            )
            return

        # Get canvas dimensions
        canvas_width = self.trends_canvas.winfo_width()
        canvas_height = 300

        if canvas_width < 100:
            canvas_width = 800

        # Margins
        margin_left = 80
        margin_right = 40
        margin_top = 40
        margin_bottom = 60

        chart_width = canvas_width - margin_left - margin_right
        chart_height = canvas_height - margin_top - margin_bottom

        # Find max value for scaling
        max_val = max(max(d['income'], d['expenses']) for d in data)
        if max_val == 0:
            max_val = 1

        # Calculate bar width
        bar_width = chart_width / (len(data) * 2.5)
        spacing = bar_width * 0.5

        # Draw axes
        # Y-axis
        self.trends_canvas.create_line(
            margin_left, margin_top,
            margin_left, margin_top + chart_height,
            width=2,
            fill='black'
        )

        # X-axis
        self.trends_canvas.create_line(
            margin_left, margin_top + chart_height,
                         margin_left + chart_width, margin_top + chart_height,
            width=2,
            fill='black'
        )

        # Y-axis labels
        for i in range(5):
            y = margin_top + chart_height - (i * chart_height / 4)
            val = max_val * i / 4

            self.trends_canvas.create_text(
                margin_left - 10,
                y,
                text=f"${val:,.0f}",
                anchor='e',
                font=('Arial', 9),
                fill='black'
            )

            # Grid line
            self.trends_canvas.create_line(
                margin_left, y,
                margin_left + chart_width, y,
                fill='lightgray',
                dash=(2, 2)
            )

        # Draw bars
        x = margin_left + spacing

        for i, month_data in enumerate(data):
            # Income bar (green)
            income_height = (month_data['income'] / max_val) * chart_height if max_val > 0 else 0
            self.trends_canvas.create_rectangle(
                x,
                margin_top + chart_height - income_height,
                x + bar_width,
                margin_top + chart_height,
                fill='#4ECDC4',
                outline=''
            )

            # Expenses bar (red)
            expense_height = (month_data['expenses'] / max_val) * chart_height if max_val > 0 else 0
            self.trends_canvas.create_rectangle(
                x + bar_width + spacing / 2,
                margin_top + chart_height - expense_height,
                x + bar_width * 2 + spacing / 2,
                margin_top + chart_height,
                fill='#FF6B6B',
                outline=''
            )

            # Month label
            from datetime import datetime
            try:
                month_obj = datetime.strptime(month_data['month'], '%Y-%m')
                month_label = month_obj.strftime('%b\n%Y')
            except:
                month_label = month_data['month']

            self.trends_canvas.create_text(
                x + bar_width + spacing / 4,
                margin_top + chart_height + 10,
                text=month_label,
                font=('Arial', 8),
                anchor='n',
                fill='black'
            )

            x += (bar_width * 2) + spacing * 2

        # Legend
        legend_x = margin_left + 20
        legend_y = margin_top - 20

        self.trends_canvas.create_rectangle(
            legend_x, legend_y,
            legend_x + 15, legend_y + 10,
            fill='#4ECDC4',
            outline=''
        )
        self.trends_canvas.create_text(
            legend_x + 20, legend_y + 5,
            text='Income',
            anchor='w',
            font=('Arial', 9),
            fill='black'
        )

        self.trends_canvas.create_rectangle(
            legend_x + 80, legend_y,
            legend_x + 95, legend_y + 10,
            fill='#FF6B6B',
            outline=''
        )
        self.trends_canvas.create_text(
            legend_x + 100, legend_y + 5,
            text='Expenses',
            anchor='w',
            font=('Arial', 9),
            fill='black'
        )

    def draw_category_trends(self, data, categories):
        """Draw category expense trends over time"""
        self.cat_trends_canvas.delete('all')

        if not data or not categories:
            self.cat_trends_canvas.create_text(
                400, 125,
                text="No category data for selected period",
                font=('Arial', 12),
                fill='black'
            )
            return

        # Organize data by month
        months = {}
        for row in data:
            month = row['month']
            if month not in months:
                months[month] = {}
            months[month][row['category']] = row['total']

        if not months:
            return

        # Get canvas dimensions
        canvas_width = self.cat_trends_canvas.winfo_width()
        canvas_height = 250

        if canvas_width < 100:
            canvas_width = 800

        # Margins
        margin_left = 80
        margin_right = 150
        margin_top = 40
        margin_bottom = 40

        chart_width = canvas_width - margin_left - margin_right
        chart_height = canvas_height - margin_top - margin_bottom

        # Sort months
        sorted_months = sorted(months.keys())

        # Find max value
        max_val = max(
            sum(months[m].values()) for m in sorted_months
        )
        if max_val == 0:
            max_val = 1

        # Colors for categories
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8']

        # Draw axes
        self.cat_trends_canvas.create_line(
            margin_left, margin_top,
            margin_left, margin_top + chart_height,
            width=2,
            fill='black'
        )

        self.cat_trends_canvas.create_line(
            margin_left, margin_top + chart_height,
                         margin_left + chart_width, margin_top + chart_height,
            width=2,
            fill='black'
        )

        # Y-axis labels
        for i in range(5):
            y = margin_top + chart_height - (i * chart_height / 4)
            val = max_val * i / 4

            self.cat_trends_canvas.create_text(
                margin_left - 10,
                y,
                text=f"${val:,.0f}",
                anchor='e',
                font=('Arial', 9),
                fill='black'
            )

            # Grid line
            self.cat_trends_canvas.create_line(
                margin_left, y,
                margin_left + chart_width, y,
                fill='lightgray',
                dash=(2, 2)
            )

        # Calculate positions
        x_step = chart_width / (len(sorted_months) - 1) if len(sorted_months) > 1 else chart_width

        # Draw lines for each category
        for cat_idx, category in enumerate(categories):
            color = colors[cat_idx % len(colors)]
            points = []

            for month_idx, month in enumerate(sorted_months):
                amount = months[month].get(category, 0)

                x = margin_left + (month_idx * x_step)
                y = margin_top + chart_height - (amount / max_val * chart_height)

                points.append((x, y))

            # Draw line
            if len(points) > 1:
                for i in range(len(points) - 1):
                    self.cat_trends_canvas.create_line(
                        points[i][0], points[i][1],
                        points[i + 1][0], points[i + 1][1],
                        fill=color,
                        width=2
                    )

            # Draw points
            for x, y in points:
                self.cat_trends_canvas.create_oval(
                    x - 3, y - 3,
                    x + 3, y + 3,
                    fill=color,
                    outline='white'
                )

        # X-axis labels (months)
        from datetime import datetime
        for month_idx, month in enumerate(sorted_months):
            x = margin_left + (month_idx * x_step)

            try:
                month_obj = datetime.strptime(month, '%Y-%m')
                month_label = month_obj.strftime('%b\n%y')
            except:
                month_label = month

            self.cat_trends_canvas.create_text(
                x,
                margin_top + chart_height + 10,
                text=month_label,
                font=('Arial', 8),
                anchor='n',
                fill='black'
            )

        # Legend
        legend_x = canvas_width - margin_right + 10
        legend_y = margin_top

        for cat_idx, category in enumerate(categories):
            color = colors[cat_idx % len(colors)]
            y = legend_y + (cat_idx * 20)

            # Color box
            self.cat_trends_canvas.create_rectangle(
                legend_x, y,
                legend_x + 15, y + 10,
                fill=color,
                outline=''
            )

            # Category name
            cat_name = category[:15] if len(category) > 15 else category
            self.cat_trends_canvas.create_text(
                legend_x + 20, y + 5,
                text=cat_name,
                anchor='w',
                font=('Arial', 8),
                fill='black'
            )

    def create_transactions_tab(self):
        """Create transactions tab"""
        txn_frame = ttk.Frame(self.notebook)
        self.notebook.add(txn_frame, text="💰 Transactions")

        # Top controls — date range is in global bar above notebook
        # Row 1: account filter + search + show limit
        row2 = ttk.Frame(txn_frame)
        row2.pack(fill='x', padx=5, pady=(0, 5))

        ttk.Label(row2, text="Account:").pack(side='left', padx=5)
        self.account_filter_var = tk.StringVar(value="All Accounts")
        self.account_combo = ttk.Combobox(
            row2,
            textvariable=self.account_filter_var,
            values=["All Accounts"],
            width=24,
            state='readonly'
        )
        self.account_combo.pack(side='left', padx=5)
        self.account_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_transactions())

        ttk.Label(row2, text="Filter:").pack(side='left', padx=5)
        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(row2, textvariable=self.filter_var, width=28)
        filter_entry.pack(side='left', padx=5)
        filter_entry.bind('<KeyRelease>', lambda e: self.refresh_transactions())

        ttk.Button(row2, text="Refresh", command=self.refresh_transactions).pack(side='left', padx=5)

        ttk.Label(row2, text="Show:").pack(side='left', padx=5)
        self.limit_var = tk.StringVar(value="All")
        limit_combo = ttk.Combobox(
            row2,
            textvariable=self.limit_var,
            values=["50", "100", "200", "500", "All"],
            width=8
        )
        limit_combo.pack(side='left', padx=5)
        limit_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_transactions())

        # Transactions tree
        tree_frame = ttk.Frame(txn_frame)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        self.txn_tree = ttk.Treeview(
            tree_frame,
            columns=('date', 'description', 'amount', 'category', 'account', 'type'),
            show='tree headings',
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )

        vsb.config(command=self.txn_tree.yview)
        hsb.config(command=self.txn_tree.xview)

        # Layout
        self.txn_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Configure columns
        self.txn_tree.heading('#0', text='ID')
        self.txn_tree.heading('date', text='Date')
        self.txn_tree.heading('description', text='Description')
        self.txn_tree.heading('amount', text='Amount')
        self.txn_tree.heading('category', text='Category')
        self.txn_tree.heading('account', text='Account')
        self.txn_tree.heading('type', text='Type')

        self.txn_tree.column('#0', width=50)
        self.txn_tree.column('date', width=100)
        self.txn_tree.column('description', width=300)
        self.txn_tree.column('amount', width=100)
        self.txn_tree.column('category', width=150)
        self.txn_tree.column('account', width=150)
        self.txn_tree.column('type', width=80)

        # Double-click to edit
        self.txn_tree.bind('<Double-1>', self.edit_transaction)

        # Bottom buttons
        btn_frame = ttk.Frame(txn_frame)
        btn_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(
            btn_frame,
            text="➕ Add Transaction",
            command=self.add_transaction
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="✏️ Edit Selected",
            command=lambda: self.edit_transaction(None)
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="🗑️ Delete Selected",
            command=self.delete_transaction
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="📊 Export CSV",
            command=self.export_transactions_csv
        ).pack(side='right', padx=5)

    def export_transactions_csv(self):
        """Export the current filtered transaction view to a CSV file."""
        import csv
        from datetime import datetime
        from tkinter import filedialog

        date_from = self.date_from_var.get()
        date_to = self.date_to_var.get()
        filter_text = self.filter_var.get()

        query = """SELECT id, date, description, amount, category, account_name,
                          transaction_type, tags, notes
                   FROM transactions WHERE 1=1"""
        params = []
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        if filter_text:
            query += " AND (description LIKE ? OR category LIKE ?)"
            params.extend([f"%{filter_text}%", f"%{filter_text}%"])
        query += " ORDER BY date DESC"

        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        if not rows:
            messagebox.showinfo("No Data", "No transactions match the current filter.")
            return

        default_name = f"transactions_{datetime.now().strftime('%Y%m%d')}.csv"
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_name
        )
        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Date', 'Description', 'Amount', 'Category',
                                 'Account', 'Type', 'Tags', 'Notes'])
                for row in rows:
                    writer.writerow([
                        row['id'], row['date'], row['description'],
                        row['amount'], row['category'], row['account_name'],
                        row['transaction_type'] or '', row['tags'] or '', row['notes'] or ''
                    ])
            messagebox.showinfo("Export Complete",
                                f"Exported {len(rows)} transactions to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")

    def create_rules_tab(self):
        """Create rules management tab"""
        rules_frame = ttk.Frame(self.notebook)
        self.notebook.add(rules_frame, text="📋 Rules")

        # Split into two panes
        paned = ttk.PanedWindow(rules_frame, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=5, pady=5)

        # Left: Rules list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Categorization Rules", font=('Arial', 12, 'bold')).pack(pady=5)

        # Rules tree
        self.rules_tree = ttk.Treeview(
            left_frame,
            columns=('keywords', 'count'),
            show='tree headings'
        )

        self.rules_tree.heading('#0', text='Category')
        self.rules_tree.heading('keywords', text='Keywords')
        self.rules_tree.heading('count', text='Count')

        self.rules_tree.column('#0', width=150)
        self.rules_tree.column('keywords', width=300)
        self.rules_tree.column('count', width=80)

        self.rules_tree.pack(fill='both', expand=True, pady=5)

        # Buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill='x', pady=5)

        ttk.Button(
            btn_frame,
            text="➕ Add Rule",
            command=self.add_rule
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="✏️ Edit Rule",
            command=self.edit_rule
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="🗑️ Delete Rule",
            command=self.delete_rule
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="🔄 Refresh",
            command=self.refresh_rules
        ).pack(side='left', padx=5)

        # Right: Rule details
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        ttk.Label(right_frame, text="Add New Rule", font=('Arial', 12, 'bold')).pack(pady=10)

        # Form
        form_frame = ttk.Frame(right_frame)
        form_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(form_frame, text="Category:").grid(row=0, column=0, sticky='w', pady=5)
        self.rule_category_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.rule_category_var, width=30).grid(row=0, column=1, pady=5)

        ttk.Label(form_frame, text="Keyword:").grid(row=1, column=0, sticky='w', pady=5)
        self.rule_keyword_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.rule_keyword_var, width=30).grid(row=1, column=1, pady=5)

        ttk.Button(
            form_frame,
            text="💾 Save Rule",
            command=self.save_rule
        ).grid(row=2, column=0, columnspan=2, pady=20)

        # Load rules
        self.refresh_rules()

    def create_categories_tab(self):
        """Create categories tab"""
        cat_frame = ttk.Frame(self.notebook)
        self.notebook.add(cat_frame, text="🏷️ Categories")

        # Top controls with date range
        control_frame = ttk.Frame(cat_frame)
        control_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(
            control_frame,
            text="Spending by Category",
            font=('Arial', 14, 'bold')
        ).pack(side='left', padx=10)

        # Date range is in the global bar above the notebook

        # Categories tree
        self.cat_tree = ttk.Treeview(
            cat_frame,
            columns=('count', 'total', 'income', 'net', 'percent'),
            show='tree headings'
        )

        self.cat_tree.heading('#0', text='Category')
        self.cat_tree.heading('count', text='Transactions')
        self.cat_tree.heading('total', text='Expenses')
        self.cat_tree.heading('income', text='Income')
        self.cat_tree.heading('net', text='Net')
        self.cat_tree.heading('percent', text='Percentage')

        self.cat_tree.column('#0', width=200)
        self.cat_tree.column('count', width=120)
        self.cat_tree.column('total', width=120)
        self.cat_tree.column('income', width=120)
        self.cat_tree.column('net', width=120)
        self.cat_tree.column('percent', width=100)

        self.cat_tree.pack(fill='both', expand=True, padx=20, pady=10)

        # Bind double-click to show transactions
        self.cat_tree.bind('<Double-1>', self.show_category_transactions)

        # Bind right-click for context menu
        self.cat_tree.bind('<Button-2>', self.show_category_menu)  # Mac right-click
        self.cat_tree.bind('<Button-3>', self.show_category_menu)  # Windows/Linux right-click

        # Add instruction label
        ttk.Label(
            cat_frame,
            text="💡 Tip: Double-click a category to view ALL transactions (all time)",
            font=('Arial', 9, 'italic'),
            foreground='gray'
        ).pack(pady=5)

        # Chart area
        chart_frame = ttk.LabelFrame(cat_frame, text="Spending Distribution", padding=10)
        chart_frame.pack(fill='x', padx=20, pady=10)

        # Canvas for bar chart
        self.cat_chart_canvas = tk.Canvas(chart_frame, height=200, bg='white')
        self.cat_chart_canvas.pack(fill='both', expand=True)

        # Refresh button
        ttk.Button(
            cat_frame,
            text="🔄 Refresh",
            command=self.refresh_categories
        ).pack(pady=10)

        # Load categories
        self.refresh_categories()

    def create_status_bar(self):
        """Create status bar"""
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")

        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief='sunken',
            anchor='w'
        )
        status_bar.pack(side='bottom', fill='x')

    # Import functions

    @staticmethod
    def _classify_transaction_type(description: str, amount: float, category: str) -> str:
        """Determine transaction type (expense/income/transfer) from description, amount, category."""
        import re

        TRANSFER_PATTERNS = [
            r'CHASE.*CREDIT.*AUTOPAY',
            r'CHASE.*PAYMENT',
            r'AMERICAN EXPRESS.*PMT',
            r'AMEX.*PAYMENT',
            r'PAYMENT.*THANK YOU',
            r'THANK YOU.*MOBILE',
            r'ONLINE PAYMENT.*THANK YOU',
            r'MOBILE PAYMENT.*THANK YOU',
            r'TRANSFER',
            r'ROBINHOOD',
            r'ZELLE',
            r'VENMO',
        ]

        if category in ('Credit Card Payment', 'Transfer', 'Investment'):
            return 'transfer'

        desc_upper = description.upper()
        for pattern in TRANSFER_PATTERNS:
            if re.search(pattern, desc_upper):
                return 'transfer'

        if amount > 0:
            return 'income'

        return 'expense'

    def import_csv(self):
        """Import CSV files"""
        files = filedialog.askopenfilenames(
            title="Select CSV Files",
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*")]
        )

        if not files:
            return

        self.import_results.delete('1.0', 'end')
        self.import_results.insert('end', f"Importing {len(files)} file(s)...\n\n")

        total_imported = 0

        for file_path in files:
            file_path = Path(file_path)
            self.import_results.insert('end', f"Processing: {file_path.name}\n")

            # Detect parser
            parser = detect_parser(file_path)

            if not parser:
                self.import_results.insert('end',
                    "  ❌ Unknown format — could not match any bank parser.\n"
                    "     Try: re-download the CSV from your bank's transaction history page\n"
                    "     (not a statement PDF), and make sure the file extension is .csv or .xlsx.\n"
                    f"     Supported: {self._supported_institutions_hint().replace('Supported: ', '')}\n\n"
                )
                continue

            try:
                # Derive a human-readable account name from the filename
                account_name = parser.get_account_name(file_path)

                # Parse
                transactions = parser.parse(file_path, account_name)

                # Get existing categories for mapping
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL")
                existing_categories = [row['category'] for row in cursor.fetchall()]

                # Convert to dicts and apply category mapping
                txn_dicts = []
                mapped_count = 0

                for txn in transactions:
                    original_category = txn.category
                    mapped_category = self.category_mapper.map_category(
                        txn.category,
                        existing_categories
                    )

                    if mapped_category != original_category:
                        mapped_count += 1

                    txn_type = self._classify_transaction_type(
                        txn.description, txn.amount, mapped_category
                    )
                    txn_dict = {
                        'date': txn.date.strftime('%Y-%m-%d') if hasattr(txn.date, 'strftime') else txn.date,
                        'description': txn.description,
                        'amount': txn.amount,
                        'account_name': txn.account_name,
                        'account_type': txn.account_type,
                        'institution': txn.institution,
                        'category': mapped_category,
                        'transaction_type': txn_type,
                        'notes': txn.notes,
                        'raw_data': txn.raw_data
                    }
                    txn_dicts.append(txn_dict)

                # Import
                result = self.db.add_transactions(txn_dicts)

                if isinstance(result, tuple):
                    imported, duplicates = result
                else:
                    imported = result
                    duplicates = 0

                total_imported += imported

                status_msg = f"  ✅ Imported: {imported}, Duplicates: {duplicates}"
                if mapped_count > 0:
                    status_msg += f", Mapped: {mapped_count}"

                self.import_results.insert('end', status_msg + "\n\n")

            except Exception as e:
                self.import_results.insert('end', f"  ❌ Error: {str(e)}\n\n")

        self.import_results.insert('end', f"\n{'=' * 60}\n")
        self.import_results.insert('end', f"Total imported: {total_imported} transactions\n")

        # ── Auto-cleanup pipeline (silent) ────────────────────────────────
        # Run cleanup even when total_imported == 0 (all duplicates) so that
        # re-importing a file works as a "rerun all fixes" action.
        if True:
            self.import_results.insert('end', "\nRunning auto-cleanup…\n")
            self.import_results.update_idletasks()
            summary = self._run_post_import_cleanup()
            parts = []
            if summary.get('refunds_fixed'):
                parts.append(f"fixed {summary['refunds_fixed']} refund sign(s)")
            if summary.get('categorized'):
                parts.append(f"categorized {summary['categorized']}")
            if summary.get('cc_payments'):
                parts.append(f"fixed {summary['cc_payments']} CC payment(s)")
            if summary.get('atm'):
                parts.append(f"fixed {summary['atm']} ATM withdrawal(s)")
            if summary.get('dup_categories'):
                parts.append(f"merged {summary['dup_categories']} duplicate categor(ies)")
            if summary.get('merged_accounts'):
                parts.append(f"merged {summary['merged_accounts']} duplicate account(s)")
            if parts:
                self.import_results.insert('end', "  ✅ " + ", ".join(parts) + "\n")
            else:
                self.import_results.insert('end', "  ✅ Nothing to clean up\n")

        self.status_var.set(f"Imported {total_imported} transactions")
        self.refresh_transactions()
        try:
            self.refresh_categories()
        except Exception:
            pass

        messagebox.showinfo("Import Complete", f"Imported {total_imported} new transactions")

    def run_all_cleanups_now(self):
        """Run the same auto-cleanup pipeline that fires after an import,
        on the current data. Useful after upgrading the app to retroactively
        apply improved rules to previously-imported transactions."""
        if not messagebox.askyesno(
            "Run All Cleanups",
            "This will scan ALL existing transactions and apply:\n"
            "  • Refund sign fixes (Chase Type='Return' rows)\n"
            "  • Auto-categorize uncategorized rows\n"
            "  • Mark CC payments as transfers\n"
            "  • ATM withdrawals: transfer → expense\n"
            "  • Merge case-variant categories\n"
            "  • Auto-merge same-bank+last-4 duplicate accounts\n\n"
            "Nothing is deleted. Continue?"
        ):
            return
        self.import_results.delete('1.0', 'end')
        self.import_results.insert('end', "Running all cleanups on existing data…\n\n")
        self.import_results.update_idletasks()
        summary = self._run_post_import_cleanup()
        parts = []
        if summary.get('refunds_fixed'):
            parts.append(f"fixed {summary['refunds_fixed']} refund sign(s)")
        if summary.get('categorized'):
            parts.append(f"categorized {summary['categorized']}")
        if summary.get('cc_payments'):
            parts.append(f"fixed {summary['cc_payments']} CC payment(s)")
        if summary.get('atm'):
            parts.append(f"fixed {summary['atm']} ATM withdrawal(s)")
        if summary.get('dup_categories'):
            parts.append(f"merged {summary['dup_categories']} duplicate categor(ies)")
        if summary.get('merged_accounts'):
            parts.append(f"merged {summary['merged_accounts']} duplicate account(s)")
        result_line = ", ".join(parts) if parts else "Nothing needed fixing"
        self.import_results.insert('end', f"✅ {result_line}\n")
        self.refresh_transactions()
        try:
            self.refresh_categories()
        except Exception:
            pass
        messagebox.showinfo("Cleanup Complete", result_line)

    def _db_is_empty(self) -> bool:
        """Return True if the transactions table has zero rows."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as c FROM transactions")
            return (cursor.fetchone()['c'] or 0) == 0
        except Exception:
            return False

    def load_demo_data(self):
        """Import the bundled examples/demo_transactions.csv so new users can explore."""
        from pathlib import Path as _Path
        # When frozen by PyInstaller, bundled data lives at sys._MEIPASS
        base = _Path(getattr(sys, '_MEIPASS', _Path(__file__).parent))
        demo = base / 'examples' / 'demo_transactions.csv'
        if not demo.exists():
            # Fallback to source-tree location
            demo = _Path(__file__).parent / 'examples' / 'demo_transactions.csv'
        if not demo.exists():
            messagebox.showerror("Demo Not Found",
                f"Could not find demo file at:\n{demo}")
            return
        # Reuse the same code path as a regular import by simulating one file
        try:
            parser = detect_parser(demo)
            if not parser:
                messagebox.showerror("Demo Failed", "No parser matched the demo CSV.")
                return
            account_name = parser.get_account_name(demo)
            transactions = parser.parse(demo, account_name)
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL")
            existing = [row['category'] for row in cursor.fetchall()]
            txn_dicts = []
            for txn in transactions:
                mapped = self.category_mapper.map_category(txn.category, existing)
                ttype = self._classify_transaction_type(txn.description, txn.amount, mapped)
                txn_dicts.append({
                    'date': txn.date.strftime('%Y-%m-%d') if hasattr(txn.date, 'strftime') else txn.date,
                    'description': txn.description,
                    'amount': txn.amount,
                    'account_name': txn.account_name,
                    'account_type': txn.account_type,
                    'institution': txn.institution,
                    'category': mapped,
                    'transaction_type': ttype,
                    'notes': txn.notes,
                    'raw_data': txn.raw_data,
                })
            result = self.db.add_transactions(txn_dicts)
            imported = result[0] if isinstance(result, tuple) else result
            self.import_results.delete('1.0', 'end')
            self.import_results.insert('end',
                f"📊 Demo data loaded: {imported} sample transactions across May–April 2026.\n"
                "Switch to Dashboard or Transactions tab to explore.\n"
                "Delete demo rows anytime via Transactions → filter on 'Demo' account.\n"
            )
            # Run auto-cleanup so demo also shows what the pipeline does
            self._run_post_import_cleanup()
            self.refresh_transactions()
            try:
                self.refresh_categories()
            except Exception:
                pass
            # Hide empty-state frame now that there's data
            try:
                self._empty_state_frame.pack_forget()
            except Exception:
                pass
            messagebox.showinfo("Demo Loaded",
                f"Loaded {imported} demo transactions. Explore the Dashboard tab!")
        except Exception as e:
            messagebox.showerror("Demo Failed", f"Error loading demo:\n\n{e}")

    def _supported_institutions_hint(self) -> str:
        """Return a short hint line listing supported parsers."""
        try:
            from pathlib import Path as _Path
            parsers_dir = _Path(__file__).parent / 'src' / 'parsers'
            names = set()
            for f in parsers_dir.glob('*.py'):
                stem = f.stem
                if stem.startswith('_') or stem in ('base', 'detector'):
                    continue
                # bofa_parser → BofA, chase_credit_parser → Chase Credit, etc.
                label = stem.replace('_parser', '').replace('_', ' ').title()
                label = label.replace('Bofa', 'BofA').replace('Amex', 'Amex')
                names.add(label)
            if names:
                return "Supported: " + ", ".join(sorted(names))
        except Exception:
            pass
        return "Supported: Chase, BofA, Amex, Discover, and more"

    def _run_post_import_cleanup(self) -> dict:
        """Run all silent cleanup passes after an import. Returns counts."""
        summary = {
            'categorized': 0,
            'cc_payments': 0,
            'atm': 0,
            'dup_categories': 0,
            'merged_accounts': 0,
            'refunds_fixed': 0,
        }
        # Refund-sign fix FIRST so downstream classification sees correct amounts
        try:
            conn = self.db.get_connection()
            summary['refunds_fixed'] = self._fix_credit_refund_amounts(conn)
            conn.commit()
        except Exception as e:
            self.import_results.insert('end', f"  ⚠ refund fix: {e}\n")
        try:
            summary['categorized'] = self._auto_categorize_uncategorized()
        except Exception as e:
            self.import_results.insert('end', f"  ⚠ categorize: {e}\n")
        try:
            summary['cc_payments'] = self._auto_fix_cc_payments()
        except Exception as e:
            self.import_results.insert('end', f"  ⚠ cc payments: {e}\n")
        try:
            summary['atm'] = self._auto_fix_atm_withdrawals()
        except Exception as e:
            self.import_results.insert('end', f"  ⚠ atm: {e}\n")
        try:
            summary['dup_categories'] = self._auto_fix_duplicate_categories()
        except Exception as e:
            self.import_results.insert('end', f"  ⚠ dup categories: {e}\n")
        try:
            summary['merged_accounts'] = self._auto_merge_duplicate_accounts()
        except Exception as e:
            self.import_results.insert('end', f"  ⚠ merge accounts: {e}\n")
        return summary

    def _auto_categorize_uncategorized(self) -> int:
        """Silently categorize any rows still marked 'Uncategorized'. Returns count."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, description FROM transactions
            WHERE category = 'Uncategorized' OR category IS NULL
        """)
        rows = cursor.fetchall()
        learned_count = 0
        for txn in rows:
            new_cat = self.learned_rules.categorize(txn['description'])
            if new_cat and new_cat != 'Uncategorized':
                cursor.execute(
                    "UPDATE transactions SET category = ? WHERE id = ?",
                    (new_cat, txn['id'])
                )
                learned_count += 1
        conn.commit()
        # Also apply built-in rules
        try:
            stats = Categorizer.categorize_all(self.db, overwrite_existing=False)
            return learned_count + stats.get('updated', 0)
        except Exception:
            return learned_count

    def _auto_fix_cc_payments(self) -> int:
        """Silently mark CC payment transactions as transfers. Returns count fixed."""
        import re
        import json as _json
        CC_PATTERNS = [
            r'payment to .* card',
            r'american express.*pmt',
            r'amex.*pmt',
            r'bk of amer.*pmt',
            r'online pmt.*ckf',
            r'autopay.*payment',
            r'credit card.*payment',
            r'card payment',
            r'payment thank you',          # Chase mobile/online payments
            r'mobile payment.*thank you',
            r'online payment.*thank you',
            r'autopay\s+payment',
            r'\bach\s+payment',
            r'electronic\s+payment',
        ]
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, description, category, transaction_type, raw_data
            FROM transactions
            WHERE transaction_type != 'transfer' OR transaction_type IS NULL
        """)
        candidates = cursor.fetchall()
        to_fix = []
        for txn in candidates:
            matched = False
            if txn['category'] == 'Credit Card Payment':
                to_fix.append(txn['id'])
                matched = True
            elif txn['category'] in ('Uncategorized', None, ''):
                desc = (txn['description'] or '').lower()
                for pat in CC_PATTERNS:
                    if re.search(pat, desc, re.IGNORECASE):
                        to_fix.append(txn['id'])
                        matched = True
                        break
            # Also catch by raw_data Type='Payment' (Chase explicit signal)
            if not matched and txn['raw_data']:
                try:
                    raw = _json.loads(txn['raw_data'])
                    raw_type = str(raw.get('Type', '') or raw.get('type', '')).strip().lower()
                    if raw_type == 'payment':
                        to_fix.append(txn['id'])
                except Exception:
                    pass
        for tid in to_fix:
            cursor.execute("""
                UPDATE transactions
                SET category = 'Credit Card Payment', transaction_type = 'transfer'
                WHERE id = ?
            """, (tid,))
        conn.commit()
        return len(to_fix)

    def _auto_fix_atm_withdrawals(self) -> int:
        """Silently flip ATM withdrawals from transfer→expense. Returns count."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE transactions
            SET transaction_type = 'expense'
            WHERE (description LIKE '%ATM%' OR description LIKE '%WITHDRAWAL%')
              AND transaction_type = 'transfer'
        """)
        count = cursor.rowcount
        conn.commit()
        return count

    def _auto_fix_duplicate_categories(self) -> int:
        """Silently merge categories that differ only in case/whitespace. Returns count of fixes."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM transactions
            WHERE category IS NOT NULL
            GROUP BY LOWER(TRIM(category))
            HAVING COUNT(DISTINCT category) > 1
        """)
        duplicates = cursor.fetchall()
        fixes = 0
        for dup in duplicates:
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM transactions
                WHERE LOWER(TRIM(category)) = LOWER(TRIM(?))
                GROUP BY category
                ORDER BY count DESC
            """, (dup['category'],))
            variations = cursor.fetchall()
            if len(variations) < 2:
                continue
            canonical = variations[0]['category']
            for var in variations[1:]:
                cursor.execute(
                    "UPDATE transactions SET category = ? WHERE category = ?",
                    (canonical, var['category'])
                )
                fixes += 1
        conn.commit()
        return fixes

    def _auto_merge_duplicate_accounts(self) -> int:
        """Silently merge accounts with same bank + same last-4 digits. Returns count merged."""
        import re

        def bank_key(name: str) -> str:
            n = (name or '').lower()
            if 'amex' in n or 'american express' in n:
                return 'amex'
            if 'bofa' in n or 'bank of america' in n:
                return 'bofa'
            if 'chase' in n:
                return 'chase'
            if 'capital one' in n:
                return 'capitalone'
            if 'discover' in n:
                return 'discover'
            if 'citi' in n:
                return 'citi'
            return n

        def last4(name: str):
            m = re.search(r'\*(\d{4})', name or '')
            if m:
                return m.group(1)
            # Fallback: trailing 4 digits in name
            m = re.search(r'(\d{4})(?!.*\d)', name or '')
            return m.group(1) if m else None

        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT account_name FROM transactions ORDER BY account_name")
        accounts = [row['account_name'] for row in cursor.fetchall() if row['account_name']]

        groups: dict = {}
        for acc in accounts:
            l4 = last4(acc)
            if not l4:
                continue
            key = (bank_key(acc), l4)
            groups.setdefault(key, []).append(acc)

        merged = 0
        for key, members in groups.items():
            if len(members) < 2:
                continue
            # Pick the "best" name: prefer one containing '*' (formatted), else longest
            members_sorted = sorted(
                members,
                key=lambda n: (0 if '*' in n else 1, -len(n))
            )
            keep = members_sorted[0]
            for other in members_sorted[1:]:
                cursor.execute(
                    "UPDATE transactions SET account_name = ? WHERE account_name = ?",
                    (keep, other)
                )
                merged += 1
        conn.commit()
        return merged

    def auto_categorize_all(self):
        """Auto-categorize all uncategorized transactions"""
        # Create dialog with three options
        dialog = tk.Toplevel(self.root)
        dialog.title("Auto-Categorize Options")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text="Auto-Categorize Transactions",
            font=('Arial', 14, 'bold')
        ).pack(pady=20)

        ttk.Label(
            dialog,
            text="What would you like to categorize?",
            font=('Arial', 11)
        ).pack(pady=10)

        result = {'choice': None}

        def choose_all():
            result['choice'] = 'all'
            dialog.destroy()

        def choose_uncategorized():
            result['choice'] = 'uncategorized'
            dialog.destroy()

        def choose_recent():
            result['choice'] = 'recent'
            dialog.destroy()

        def cancel():
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)

        ttk.Button(
            btn_frame,
            text="📋 All Transactions\n(Re-categorize everything)",
            command=choose_all,
            width=30
        ).pack(pady=5)

        ttk.Button(
            btn_frame,
            text="❓ Uncategorized Only\n(Only 'Uncategorized')",
            command=choose_uncategorized,
            width=30
        ).pack(pady=5)

        ttk.Button(
            btn_frame,
            text="🆕 Recent Imports\n(Last 30 days - for new transactions)",
            command=choose_recent,
            width=30
        ).pack(pady=5)

        ttk.Button(
            btn_frame,
            text="Cancel",
            command=cancel,
            width=30
        ).pack(pady=10)

        # Wait for dialog
        self.root.wait_window(dialog)

        if not result['choice']:
            return

        self.status_var.set("Auto-categorizing...")

        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Build query based on choice
        if result['choice'] == 'all':
            cursor.execute("SELECT id, description, category FROM transactions")
            overwrite = True
        elif result['choice'] == 'uncategorized':
            cursor.execute("""
                SELECT id, description, category
                FROM transactions
                WHERE category = 'Uncategorized'
            """)
            overwrite = False
        else:  # recent
            from datetime import timedelta
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT id, description, category
                FROM transactions
                WHERE date >= ?
            """, (thirty_days_ago,))
            overwrite = False

        remaining = cursor.fetchall()

        if not remaining:
            messagebox.showinfo("No Transactions", "No transactions found to categorize.")
            return

        # Progress dialog
        prog_win = tk.Toplevel(self.root)
        prog_win.title("Auto-Categorizing...")
        prog_win.geometry("360x110")
        prog_win.resizable(False, False)
        prog_win.transient(self.root)
        prog_win.grab_set()
        ttk.Label(prog_win, text="Categorizing transactions…", font=('Arial', 11)).pack(pady=(16, 6))
        prog_var = tk.DoubleVar()
        prog_bar = ttk.Progressbar(prog_win, variable=prog_var, maximum=len(remaining), length=300)
        prog_bar.pack(padx=30)
        prog_label = ttk.Label(prog_win, text=f"0 / {len(remaining)}", font=('Arial', 9))
        prog_label.pack(pady=4)
        prog_win.update()

        learned_count = 0
        for i, txn in enumerate(remaining, 1):
            new_cat = self.learned_rules.categorize(txn['description'])
            if new_cat != 'Uncategorized' and (overwrite or txn['category'] == 'Uncategorized'):
                cursor.execute(
                    "UPDATE transactions SET category = ? WHERE id = ?",
                    (new_cat, txn['id'])
                )
                learned_count += 1
            prog_var.set(i)
            prog_label.config(text=f"{i} / {len(remaining)}")
            if i % 20 == 0:
                prog_win.update()

        conn.commit()
        prog_win.destroy()

        # Also try built-in rules
        stats = Categorizer.categorize_all(self.db, overwrite_existing=overwrite)
        total = stats['updated'] + learned_count

        # Show results
        choice_text = {
            'all': 'all transactions',
            'uncategorized': 'uncategorized transactions',
            'recent': 'recent transactions (last 30 days)'
        }

        self.status_var.set(f"Categorized {total} transactions")
        self.refresh_transactions()
        self.refresh_categories()

        messagebox.showinfo(
            "Auto-Categorize Complete",
            f"Checked {len(remaining)} {choice_text[result['choice']]}\n\n"
            f"Categorized {total} transactions:\n"
            f"• Learned rules: {learned_count}\n"
            f"• Built-in rules: {stats['updated']}"
        )

    def classify_types(self):
        """Classify transaction types"""
        # Implementation from classify_transaction_types.py
        import re

        TRANSFER_PATTERNS = [
            r'CHASE.*CREDIT.*AUTOPAY',
            r'CHASE.*PAYMENT',
            r'AMERICAN EXPRESS.*PMT',
            r'AMEX.*PAYMENT',
            r'ONLINE PAYMENT.*THANK YOU',
            r'MOBILE PAYMENT.*THANK YOU',
            r'TRANSFER',
            r'ROBINHOOD',
            r'ZELLE',
            r'VENMO',
        ]

        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, description, amount, category
            FROM transactions
            WHERE transaction_type IS NULL
        """)

        transactions = cursor.fetchall()
        classified = 0

        for txn in transactions:
            desc_upper = txn['description'].upper()

            is_transfer = False
            for pattern in TRANSFER_PATTERNS:
                if re.search(pattern, desc_upper):
                    is_transfer = True
                    break

            if txn['category'] in ['Credit Card Payment', 'Transfer', 'Investment']:
                is_transfer = True

            if is_transfer:
                txn_type = 'transfer'
            elif txn['amount'] > 0:
                txn_type = 'income'
            else:
                txn_type = 'expense'

            cursor.execute(
                "UPDATE transactions SET transaction_type = ? WHERE id = ?",
                (txn_type, txn['id'])
            )
            classified += 1

        conn.commit()

        # Fix amounts for credit/refund transactions stored with wrong sign
        fixed = self._fix_credit_refund_amounts(conn)

        conn.commit()

        self.status_var.set(f"Classified {classified} transactions, fixed {fixed} credit/refund amounts")
        self.refresh_transactions()

        messagebox.showinfo("Classification Complete",
                            f"Classified {classified} transactions\nFixed {fixed} credit/refund sign errors")

    def _fix_credit_refund_amounts(self, conn) -> int:
        """Fix transactions stored with wrong sign (refunds as expenses).

        Two passes:
          1. Description-pattern match (REFUND, CREDIT, RETURN, …) — catches
             refunds whose description carries the keyword.
          2. raw_data Type field — catches refunds whose description is just
             the merchant name (e.g. 'PAYPAL *FABLETICSLL') but whose original
             CSV row had Type='Return' / 'Refund' / 'Adjustment'. This is the
             most reliable signal for Chase credit cards.

        Only flips rows where amount < 0 and the row clearly looks like a
        credit on a credit-card account.
        """
        import re
        import json as _json
        cursor = conn.cursor()

        CREDIT_PATTERNS = [
            r'\bCREDIT\b', r'\bREFUND\b', r'\bCASH\s*BACK\b', r'\bCASHBACK\b',
            r'\bREWARD\b', r'\bREBATES?\b', r'\bREVERSAL\b', r'\bRETURN\b',
            r'\bADJUSTMENT\b', r'\bREIMBURSE\b',
        ]
        REFUND_TYPES = {'return', 'refund', 'adjustment', 'reimbursement'}

        cursor.execute("""
            SELECT id, description, amount, account_name, raw_data
            FROM transactions
            WHERE amount < 0
              AND (account_name LIKE '%Chase Credit%'
                   OR account_name LIKE '%Amex%'
                   OR account_name LIKE '%American Express%'
                   OR account_name LIKE '%Capital One%'
                   OR account_name LIKE '%Bank of America%'
                   OR account_name LIKE '%Discover%')
        """)
        rows = cursor.fetchall()

        fixed = 0
        for row in rows:
            should_flip = False

            # Pass 1: description pattern
            desc_upper = (row['description'] or '').upper()
            if any(re.search(p, desc_upper) for p in CREDIT_PATTERNS):
                should_flip = True

            # Pass 2: raw_data Type field
            if not should_flip and row['raw_data']:
                try:
                    raw = _json.loads(row['raw_data'])
                    raw_type = str(raw.get('Type', '') or raw.get('type', '')).strip().lower()
                    if raw_type in REFUND_TYPES:
                        should_flip = True
                except Exception:
                    pass

            if should_flip:
                cursor.execute(
                    "UPDATE transactions SET amount = ?, transaction_type = 'income' WHERE id = ?",
                    (-row['amount'], row['id'])
                )
                fixed += 1

        return fixed

    def find_duplicates(self):
        """Find duplicate transactions"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Method 1: Exact duplicates (same date, description, amount, account)
        cursor.execute("""
            SELECT date, description, amount, account_name, COUNT(*) as count
            FROM transactions
            GROUP BY date, description, amount, account_name
            HAVING count > 1
        """)

        exact_duplicates = cursor.fetchall()

        # Method 2: Likely duplicates (same date, description, amount but different account name)
        # This catches CSV files imported with different account names
        cursor.execute("""
            SELECT date, description, amount, GROUP_CONCAT(DISTINCT account_name) as accounts, COUNT(*) as count
            FROM transactions
            GROUP BY date, description, amount
            HAVING count > 1
        """)

        likely_duplicates = cursor.fetchall()

        if not exact_duplicates and not likely_duplicates:
            messagebox.showinfo("No Duplicates", "No duplicate transactions found!")
            return

        # Show results
        msg = ""

        if exact_duplicates:
            msg += f"Found {len(exact_duplicates)} sets of EXACT duplicates:\n\n"
            for dup in exact_duplicates[:5]:
                msg += f"• {dup['date']} - {dup['description'][:40]} - ${dup['amount']} ({dup['count']} copies)\n"
            if len(exact_duplicates) > 5:
                msg += f"... and {len(exact_duplicates) - 5} more\n"

        if likely_duplicates:
            msg += f"\n\nFound {len(likely_duplicates)} sets of LIKELY duplicates:\n"
            msg += "(Same date/amount/description, different account names)\n\n"
            for dup in likely_duplicates[:5]:
                msg += f"• {dup['date']} - {dup['description'][:40]} - ${dup['amount']} ({dup['count']} copies)\n"
                msg += f"  Accounts: {dup['accounts']}\n"
            if len(likely_duplicates) > 5:
                msg += f"... and {len(likely_duplicates) - 5} more\n"

        msg += "\n\nWould you like to open a tool to review and delete duplicates?"

        if messagebox.askyesno("Duplicates Found", msg):
            DuplicateReviewDialog(self.root, self.db, self.refresh_transactions)

    def fix_duplicate_categories(self):
        """Fix categories that differ only in capitalization"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get all unique categories (case-insensitive grouping)
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM transactions
            WHERE category IS NOT NULL
            GROUP BY LOWER(category)
            HAVING COUNT(DISTINCT category) > 1
        """)

        duplicates = cursor.fetchall()

        if not duplicates:
            messagebox.showinfo("No Duplicates", "No duplicate categories found!")
            return

        # For each duplicate group, find all variations
        fixes = []
        for dup in duplicates:
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM transactions
                WHERE LOWER(category) = LOWER(?)
                GROUP BY category
                ORDER BY count DESC
            """, (dup['category'],))

            variations = cursor.fetchall()

            # Most common variation becomes canonical
            canonical = variations[0]['category']

            for var in variations[1:]:
                fixes.append({
                    'from': var['category'],
                    'to': canonical,
                    'count': var['count']
                })

        if not fixes:
            messagebox.showinfo("No Duplicates", "No duplicate categories found!")
            return

        # Show what will be fixed
        msg = "Found duplicate categories with different capitalization:\n\n"
        for fix in fixes[:10]:
            msg += f"• '{fix['from']}' → '{fix['to']}' ({fix['count']} txns)\n"

        if len(fixes) > 10:
            msg += f"\n... and {len(fixes) - 10} more"

        msg += f"\n\nFix {sum(f['count'] for f in fixes)} transactions?"

        if messagebox.askyesno("Fix Duplicate Categories", msg):
            for fix in fixes:
                cursor.execute(
                    "UPDATE transactions SET category = ? WHERE category = ?",
                    (fix['to'], fix['from'])
                )

            conn.commit()

            self.refresh_transactions()
            self.refresh_categories()

            messagebox.showinfo(
                "Fixed!",
                f"Fixed {len(fixes)} duplicate categories affecting {sum(f['count'] for f in fixes)} transactions"
            )

    def merge_categories(self):
        """Open dialog to merge categories"""
        MergeCategoriesDialog(self.root, self.db, self.refresh_transactions, self.refresh_categories, self.category_mapper)

    def fix_account_names(self):
        """Rename existing file-stem account names to proper bank account names."""
        import re

        PATTERNS = [
            # Chase checking: Chase9707_Activity... → Chase Checking *9707
            (re.compile(r'^[Cc]hase(\d{4})_Activity', re.IGNORECASE),
             lambda m: f"Chase Checking *{m.group(1)}"),
            # Chase credit: Chase4370_... without Activity → Chase Credit *4370
            # (Chase credit files may also have Activity in name, so check both parsers)
            # We'll try checking first, then credit if no match (same regex, different label)
        ]

        def derive_name(old):
            import re
            # Chase checking pattern
            m = re.search(r'[Cc]hase(\d{4})_Activity', old)
            if m:
                return f"Chase Checking *{m.group(1)}"
            # Chase credit pattern (no "Activity" keyword, just Chase + 4 digits)
            m = re.search(r'[Cc]hase(\d{4})', old)
            if m:
                return f"Chase Credit *{m.group(1)}"
            # "activity..." prefix without bank → Discover
            if re.match(r'^activity', old, re.IGNORECASE):
                return "Discover"
            # BofA
            if re.search(r'(bank.?of.?america|bofa|boa)', old, re.IGNORECASE):
                m2 = re.search(r'(\d{4})', old)
                return f"Bank of America *{m2.group(1)}" if m2 else "Bank of America"
            # Amex
            if re.search(r'(amex|american.?express)', old, re.IGNORECASE):
                m2 = re.search(r'(\d+)', old)
                return f"Amex *{m2.group(1)[-5:]}" if m2 else "American Express"
            return None  # No change

        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT account_name FROM transactions ORDER BY account_name")
        old_names = [row['account_name'] for row in cursor.fetchall()]

        updates = {}
        for old in old_names:
            new = derive_name(old)
            if new and new != old:
                updates[old] = new

        if not updates:
            messagebox.showinfo("Fix Account Names", "All account names already look correct.")
            return

        msg = "The following account names will be updated:\n\n"
        for old, new in updates.items():
            msg += f"  {old[:45]}  →  {new}\n"
        msg += f"\n{len(updates)} account name(s) will change."

        if not messagebox.askyesno("Fix Account Names?", msg):
            return

        for old, new in updates.items():
            cursor.execute(
                "UPDATE transactions SET account_name = ? WHERE account_name = ?",
                (new, old)
            )
        conn.commit()

        self.refresh_transactions()
        messagebox.showinfo("Done", f"Updated {len(updates)} account name(s).")

    def merge_accounts(self):
        """Open dialog to merge duplicate/misnamed accounts"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT account_name FROM transactions ORDER BY account_name")
        accounts = [row['account_name'] for row in cursor.fetchall()]
        if not accounts:
            messagebox.showinfo("No Accounts", "No accounts found in the database.")
            return
        MergeAccountsDialog(self.root, self.db, accounts, self.refresh_transactions)

    def view_mappings(self):
        """View current category mappings"""
        mappings = self.category_mapper.get_all_mappings()
        auto_mappings = self.category_mapper.auto_learned_mappings

        msg = "Category Mappings (for future imports):\n\n"

        if mappings:
            msg += "Manual Mappings:\n"
            for from_cat, to_cat in sorted(mappings.items()):
                msg += f"  • '{from_cat}' → '{to_cat}'\n"
            msg += f"\nTotal: {len(mappings)} manual mappings\n"

        if auto_mappings:
            msg += "\nAuto-Learned Mappings:\n"
            for from_cat, to_cat in sorted(list(auto_mappings.items())[:20]):  # Show first 20
                msg += f"  • '{from_cat}' → '{to_cat}'\n"

            if len(auto_mappings) > 20:
                msg += f"\n... and {len(auto_mappings) - 20} more\n"

            msg += f"\nTotal: {len(auto_mappings)} auto-learned mappings\n"

        if not mappings and not auto_mappings:
            msg += "No mappings configured yet.\n\n"
            msg += "Mappings are created when you:\n"
            msg += "  • Merge categories\n"
            msg += "  • Import files (auto-learned)\n"

        messagebox.showinfo("Category Mappings", msg)

    def fix_cc_payments(self):
        """Mark Credit Card Payment transactions as transfers, including uncategorized ones"""
        import re

        CC_PATTERNS = [
            r'payment to .* card',
            r'american express.*pmt',
            r'amex.*pmt',
            r'bk of amer.*pmt',
            r'online pmt.*ckf',
            r'autopay.*payment',
            r'credit card.*payment',
            r'card payment',
        ]

        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, description, category, transaction_type
            FROM transactions
            WHERE transaction_type != 'transfer' OR transaction_type IS NULL
        """)
        candidates = cursor.fetchall()

        to_fix = []
        for txn in candidates:
            if txn['category'] == 'Credit Card Payment':
                to_fix.append(txn)
            elif txn['category'] in ('Uncategorized', None, ''):
                desc = (txn['description'] or '').lower()
                for pat in CC_PATTERNS:
                    if re.search(pat, desc, re.IGNORECASE):
                        to_fix.append(txn)
                        break

        if not to_fix:
            messagebox.showinfo(
                "Already Fixed",
                "No Credit Card Payment transactions need fixing!"
            )
            return

        msg = f"Found {len(to_fix)} Credit Card Payment transaction(s) to fix:\n\n"
        for txn in to_fix[:8]:
            cat_label = f" [{txn['category']}]" if txn['category'] != 'Credit Card Payment' else ""
            msg += f"  • {txn['description'][:50]}{cat_label}\n"
        if len(to_fix) > 8:
            msg += f"  ... and {len(to_fix) - 8} more\n"
        msg += "\nThis will:\n• Set category to 'Credit Card Payment'\n"
        msg += "• Mark as 'transfer' (excluded from spending totals)\n\nContinue?"

        if messagebox.askyesno("Fix CC Payments", msg):
            for txn in to_fix:
                cursor.execute("""
                    UPDATE transactions
                    SET category = 'Credit Card Payment', transaction_type = 'transfer'
                    WHERE id = ?
                """, (txn['id'],))
            conn.commit()

            self.refresh_transactions()
            self.refresh_categories()

            messagebox.showinfo(
                "Fixed!",
                f"Fixed {len(to_fix)} Credit Card Payment transaction(s).\n\n"
                "They will no longer appear in spending totals!"
            )

    def fix_atm_withdrawals(self):
        """Review and fix ATM withdrawals that should be expenses"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Find ATM withdrawals marked as transfers
        cursor.execute("""
            SELECT id, date, description, amount, category, transaction_type
            FROM transactions
            WHERE (description LIKE '%ATM%' OR description LIKE '%WITHDRAWAL%')
              AND transaction_type = 'transfer'
            ORDER BY date DESC
        """)

        atm_txns = cursor.fetchall()

        if not atm_txns:
            messagebox.showinfo(
                "No ATM Withdrawals",
                "No ATM withdrawals marked as transfers found."
            )
            return

        # Show list for user to review
        msg = f"Found {len(atm_txns)} ATM withdrawal(s) marked as transfers:\n\n"

        for txn in atm_txns[:10]:
            msg += f"• {txn['date']} - {txn['description'][:40]} - ${abs(txn['amount']):.2f}\n"

        if len(atm_txns) > 10:
            msg += f"\n... and {len(atm_txns) - 10} more\n"

        msg += "\nATM withdrawals are usually expenses (cash for spending).\n"
        msg += "Only mark as 'transfer' if moving money between your own accounts.\n\n"
        msg += "Change all to 'expense'?"

        if messagebox.askyesno("Fix ATM Withdrawals", msg):
            cursor.execute("""
                UPDATE transactions
                SET transaction_type = 'expense'
                WHERE (description LIKE '%ATM%' OR description LIKE '%WITHDRAWAL%')
                  AND transaction_type = 'transfer'
            """)

            count = cursor.rowcount
            conn.commit()

            self.refresh_transactions()
            self.refresh_categories()

            messagebox.showinfo(
                "Fixed!",
                f"Changed {count} ATM withdrawal(s) to 'expense'.\n\n" +
                "They will now appear in spending totals."
            )
        else:
            messagebox.showinfo(
                "Manual Review",
                "You can manually edit individual transactions:\n\n" +
                "1. Go to Transactions tab\n" +
                "2. Filter for 'ATM' or 'WITHDRAWAL'\n" +
                "3. Double-click each transaction\n" +
                "4. Change Type to 'Expense' or 'Transfer' as needed"
            )

    # Transaction functions

    def set_this_month(self): self.set_global_this_month()
    def set_last_month(self): self.set_global_last_month()
    def set_this_year(self):  self.set_global_this_year()
    def set_all_time(self):   self.set_global_all_time()

    # ─── Spending Plan (Conscious Spending) tab ────────────────────────────────

    def create_spending_plan_tab(self):
        """Create the Conscious Spending Plan tab."""
        from datetime import datetime

        plan_frame = ttk.Frame(self.notebook)
        self.notebook.add(plan_frame, text="💡 Spending Plan")

        # ── Top controls ──────────────────────────────────────────────────────
        ctrl = ttk.Frame(plan_frame)
        ctrl.pack(fill='x', padx=5, pady=5)

        # Date range is in the global bar above the notebook
        ttk.Button(ctrl, text="🔄 Refresh", command=self.refresh_spending_plan).pack(side='left', padx=10)

        # Manual income override
        income_lf = ttk.LabelFrame(ctrl, text="Monthly Take-Home Pay", padding=5)
        income_lf.pack(side='left', padx=5)
        ttk.Label(income_lf, text="$").pack(side='left')
        self.sp_income_var = tk.StringVar(value="")
        ttk.Entry(income_lf, textvariable=self.sp_income_var, width=12).pack(side='left', padx=2)
        ttk.Label(income_lf, text="(leave blank to use detected income)").pack(side='left', padx=5)

        # ── 4 Bucket panels ───────────────────────────────────────────────────
        buckets_frame = ttk.Frame(plan_frame)
        buckets_frame.pack(fill='x', padx=5, pady=5)

        BUCKETS = [
            ("fixed",      "🏠 Fixed Costs",      "50–60%", (0.50, 0.60), "#4A90D9"),
            ("investment", "📈 Investments",       "10%",    (0.10, 0.10), "#27AE60"),
            ("savings",    "🏦 Savings",           "5–10%",  (0.05, 0.10), "#8E44AD"),
            ("guilt_free", "🎉 Guilt-Free Spend",  "20–35%", (0.20, 0.35), "#E67E22"),
        ]

        self.sp_bucket_labels = {}   # bucket_key → dict of label vars
        self.sp_bar_canvases = {}    # bucket_key → Canvas

        for col, (key, title, target_pct, target_range, color) in enumerate(BUCKETS):
            lf = ttk.LabelFrame(buckets_frame, text=title, padding=8)
            lf.grid(row=0, column=col, padx=6, pady=4, sticky='nsew')
            buckets_frame.columnconfigure(col, weight=1)

            ttk.Label(lf, text=f"Target: {target_pct} of income",
                      font=('Arial', 9, 'italic'), foreground='gray').pack()

            amt_var = tk.StringVar(value="$0.00")
            pct_var = tk.StringVar(value="0.0%")
            status_var = tk.StringVar(value="—")

            ttk.Label(lf, textvariable=amt_var, font=('Arial', 18, 'bold')).pack(pady=2)
            ttk.Label(lf, textvariable=pct_var, font=('Arial', 11)).pack()
            ttk.Label(lf, textvariable=status_var, font=('Arial', 10)).pack()

            # Progress bar canvas
            bar = tk.Canvas(lf, height=12, bg='#DDDDDD', highlightthickness=0)
            bar.pack(fill='x', pady=4)

            self.sp_bucket_labels[key] = {
                'amt': amt_var, 'pct': pct_var, 'status': status_var,
                'color': color, 'target_range': target_range
            }
            self.sp_bar_canvases[key] = bar

        # ── Category assignment ───────────────────────────────────────────────
        assign_lf = ttk.LabelFrame(plan_frame, text="Category → Bucket Assignment (right-click to reassign)", padding=5)
        assign_lf.pack(fill='both', expand=True, padx=5, pady=5)

        cols = ('Category', 'Bucket', 'Monthly Avg')
        self.sp_cat_tree = ttk.Treeview(assign_lf, columns=cols, show='headings', height=10)
        for c in cols:
            self.sp_cat_tree.heading(c, text=c)
        self.sp_cat_tree.column('Category', width=200)
        self.sp_cat_tree.column('Bucket', width=140)
        self.sp_cat_tree.column('Monthly Avg', width=110, anchor='e')

        sb = ttk.Scrollbar(assign_lf, orient='vertical', command=self.sp_cat_tree.yview)
        self.sp_cat_tree.configure(yscrollcommand=sb.set)
        self.sp_cat_tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.sp_cat_tree.bind('<Button-2>', self.sp_show_bucket_menu)
        self.sp_cat_tree.bind('<Button-3>', self.sp_show_bucket_menu)

        self.refresh_spending_plan()

    def sp_set_this_month(self): self.set_global_this_month()
    def sp_set_last_month(self): self.set_global_last_month()
    def sp_set_this_year(self):  self.set_global_this_year()
    def sp_set_all_time(self):   self.set_global_all_time()

    # ─── Settings tab ─────────────────────────────────────────────────────────
    def create_settings_tab(self):
        """Create Settings tab: backup, restore, export, info."""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="⚙ Settings")

        ttk.Label(settings_frame, text="Settings", font=('Arial', 18, 'bold')).pack(pady=(20, 10))

        # ── Data safety ──────────────────────────────────────────────────────
        safety_lf = ttk.LabelFrame(settings_frame, text="Data Safety", padding=12)
        safety_lf.pack(fill='x', padx=30, pady=10)

        ttk.Label(safety_lf,
                  text="Your data lives in a single SQLite file. Back it up before upgrades.",
                  font=('Arial', 10), foreground='#555').pack(anchor='w', pady=(0, 8))

        btn_row = ttk.Frame(safety_lf)
        btn_row.pack(anchor='w')
        ttk.Button(btn_row, text="💾 Backup Database…", command=self.backup_database, width=22).pack(side='left', padx=5)
        ttk.Button(btn_row, text="♻ Restore Database…", command=self.restore_database, width=22).pack(side='left', padx=5)

        # ── Export ───────────────────────────────────────────────────────────
        export_lf = ttk.LabelFrame(settings_frame, text="Export", padding=12)
        export_lf.pack(fill='x', padx=30, pady=10)

        ttk.Label(export_lf,
                  text="Export transactions for the current global date range to a CSV file.",
                  font=('Arial', 10), foreground='#555').pack(anchor='w', pady=(0, 8))

        ttk.Button(export_lf, text="📤 Export Transactions to CSV…",
                   command=self.export_transactions_csv, width=32).pack(anchor='w', padx=5)

        # ── About / Info ─────────────────────────────────────────────────────
        info_lf = ttk.LabelFrame(settings_frame, text="About", padding=12)
        info_lf.pack(fill='x', padx=30, pady=10)

        data_dir = _get_data_dir()
        ttk.Label(info_lf, text=f"Data directory: {data_dir}",
                  font=('Courier', 9), foreground='#444').pack(anchor='w')
        ttk.Label(info_lf, text=f"Database: {data_dir / 'transactions.db'}",
                  font=('Courier', 9), foreground='#444').pack(anchor='w')
        ttk.Label(info_lf, text="Cashflow Tracker — local-first personal finance.  MIT License.",
                  font=('Arial', 9, 'italic'), foreground='#777').pack(anchor='w', pady=(8, 0))

    def backup_database(self):
        """Copy the current DB file to a user-chosen location."""
        import shutil
        from datetime import datetime as _dt
        data_dir = _get_data_dir()
        src = data_dir / 'transactions.db'
        if not src.exists():
            messagebox.showerror("No Database", f"No database file found at:\n{src}")
            return
        default_name = f"cashflow_backup_{_dt.now().strftime('%Y%m%d_%H%M%S')}.db"
        dest = filedialog.asksaveasfilename(
            title="Save Backup As",
            defaultextension=".db",
            initialfile=default_name,
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")]
        )
        if not dest:
            return
        try:
            shutil.copy2(src, dest)
            messagebox.showinfo("Backup Complete",
                f"Database backed up to:\n{dest}\n\nKeep this file somewhere safe.")
        except Exception as e:
            messagebox.showerror("Backup Failed", f"Could not back up:\n\n{e}")

    def restore_database(self):
        """Replace the current DB with a chosen backup (creates a safety copy first)."""
        import shutil
        from datetime import datetime as _dt
        src = filedialog.askopenfilename(
            title="Select Backup File to Restore",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")]
        )
        if not src:
            return
        if not messagebox.askyesno(
            "Confirm Restore",
            "This will REPLACE your current database with the selected backup.\n\n"
            "Your current database will be saved as a safety copy first.\n\n"
            "Continue?"
        ):
            return
        data_dir = _get_data_dir()
        current = data_dir / 'transactions.db'
        try:
            if current.exists():
                safety = data_dir / f"transactions_before_restore_{_dt.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(current, safety)
            shutil.copy2(src, current)
            messagebox.showinfo("Restore Complete",
                "Database restored. Please RESTART the app to reload data.")
        except Exception as e:
            messagebox.showerror("Restore Failed", f"Could not restore:\n\n{e}")

    def export_transactions_csv(self):
        """Export transactions in the current global date range to CSV."""
        import csv
        date_from = self.global_from_var.get()
        date_to = self.global_to_var.get()
        dest = filedialog.asksaveasfilename(
            title="Export Transactions",
            defaultextension=".csv",
            initialfile=f"transactions_{date_from}_to_{date_to}.csv",
            filetypes=[("CSV file", "*.csv"), ("All files", "*.*")]
        )
        if not dest:
            return
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, description, amount, account_name, institution,
                   category, transaction_type, notes
            FROM transactions
            WHERE (? = '' OR date >= ?) AND (? = '' OR date <= ?)
            ORDER BY date DESC
        """, (date_from, date_from, date_to, date_to))
        rows = cursor.fetchall()
        try:
            with open(dest, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Description", "Amount", "Account",
                                 "Institution", "Category", "Type", "Notes"])
                for r in rows:
                    writer.writerow([r['date'], r['description'], r['amount'],
                                     r['account_name'], r['institution'],
                                     r['category'], r['transaction_type'], r['notes']])
            messagebox.showinfo("Export Complete",
                f"Exported {len(rows)} transaction(s) to:\n{dest}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not write CSV:\n\n{e}")

    def refresh_spending_plan(self):
        """Recompute bucket totals and redraw the Spending Plan tab."""
        date_from = self.sp_date_from_var.get()
        date_to   = self.sp_date_to_var.get()

        conn   = self.db.get_connection()
        cursor = conn.cursor()

        # ── Determine income ──────────────────────────────────────────────────
        try:
            income = float(self.sp_income_var.get().replace(',', '').replace('$', ''))
        except (ValueError, AttributeError):
            income = 0.0

        if income <= 0:
            q = """SELECT SUM(amount) as total FROM transactions
                   WHERE transaction_type = 'income'"""
            p = []
            if date_from:
                q += " AND date >= ?"
                p.append(date_from)
            if date_to:
                q += " AND date <= ?"
                p.append(date_to)
            cursor.execute(q, p)
            row = cursor.fetchone()
            income = float(row['total'] or 0)

        # ── Spending per category ─────────────────────────────────────────────
        q = """SELECT t.category,
                      COALESCE(cb.bucket, 'guilt_free') as bucket,
                      SUM(ABS(t.amount)) as total
               FROM transactions t
               LEFT JOIN category_bucket cb ON t.category = cb.category
               WHERE t.transaction_type = 'expense'"""
        p = []
        if date_from:
            q += " AND t.date >= ?"
            p.append(date_from)
        if date_to:
            q += " AND t.date <= ?"
            p.append(date_to)
        q += " GROUP BY t.category ORDER BY total DESC"
        cursor.execute(q, p)
        cat_rows = cursor.fetchall()

        bucket_totals = {'fixed': 0.0, 'investment': 0.0, 'savings': 0.0,
                         'guilt_free': 0.0, 'untracked': 0.0}
        cat_buckets = {}
        for r in cat_rows:
            b = r['bucket'] or 'guilt_free'
            bucket_totals[b] = bucket_totals.get(b, 0) + float(r['total'] or 0)
            cat_buckets[r['category']] = (b, float(r['total'] or 0))

        # ── Update bucket panels ──────────────────────────────────────────────
        BUCKET_NAMES = {
            'fixed': 'Fixed Costs', 'investment': 'Investments',
            'savings': 'Savings', 'guilt_free': 'Guilt-Free'
        }
        for key, info in self.sp_bucket_labels.items():
            amt   = bucket_totals.get(key, 0)
            pct   = (amt / income * 100) if income > 0 else 0
            lo, hi = info['target_range']

            info['amt'].set(f"${amt:,.2f}")
            info['pct'].set(f"{pct:.1f}% of income")

            if income <= 0:
                status = "—"
            elif pct / 100 < lo:
                status = f"✅ Under target (target {lo*100:.0f}–{hi*100:.0f}%)"
            elif pct / 100 <= hi:
                status = f"✅ On target ({lo*100:.0f}–{hi*100:.0f}%)"
            else:
                status = f"⚠️ Over target (target {lo*100:.0f}–{hi*100:.0f}%)"
            info['status'].set(status)

            # Draw progress bar
            bar = self.sp_bar_canvases[key]
            bar.update_idletasks()
            w = bar.winfo_width() or 200
            fill_ratio = min(pct / 100 / hi, 1.5) if hi > 0 else 0  # cap at 150%
            fill_w = int(w * fill_ratio / 1.5)
            bar_color = info['color'] if pct / 100 <= hi else '#E74C3C'
            bar.delete('all')
            bar.create_rectangle(0, 0, fill_w, 12, fill=bar_color, outline='')
            # Target marker
            target_x = int(w / 1.5 * 1.0)  # 100% of target
            bar.create_line(target_x, 0, target_x, 12, fill='#333', width=2)

        # ── Populate category assignment tree ─────────────────────────────────
        BUCKET_DISPLAY = {
            'fixed': 'Fixed Costs', 'investment': 'Investments',
            'savings': 'Savings', 'guilt_free': 'Guilt-Free Spend',
            'untracked': 'Untracked'
        }
        for item in self.sp_cat_tree.get_children():
            self.sp_cat_tree.delete(item)

        for cat, (bucket, total) in sorted(cat_buckets.items(),
                                           key=lambda x: x[1][1], reverse=True):
            self.sp_cat_tree.insert('', 'end',
                iid=cat,
                values=(cat, BUCKET_DISPLAY.get(bucket, bucket), f"${total:,.2f}"))

        # Also show categories with bucket assignments but no spending this period
        cursor.execute("SELECT category, bucket FROM category_bucket ORDER BY category")
        for r in cursor.fetchall():
            if r['category'] not in cat_buckets:
                self.sp_cat_tree.insert('', 'end', iid=f"__{r['category']}",
                    values=(r['category'], BUCKET_DISPLAY.get(r['bucket'], r['bucket']), "$0.00"))

    def sp_show_bucket_menu(self, event):
        """Context menu to reassign a category to a different CSP bucket."""
        item = self.sp_cat_tree.identify_row(event.y)
        if not item:
            return
        self.sp_cat_tree.selection_set(item)
        cat_name = self.sp_cat_tree.item(item)['values'][0]

        BUCKET_OPTIONS = [
            ('Fixed Costs',       'fixed'),
            ('Investments',       'investment'),
            ('Savings',           'savings'),
            ('Guilt-Free Spend',  'guilt_free'),
            ('Untracked',         'untracked'),
        ]

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"Assign '{cat_name}' to:", state='disabled')
        menu.add_separator()
        for label, key in BUCKET_OPTIONS:
            menu.add_command(
                label=label,
                command=lambda k=key, c=cat_name: self.sp_assign_bucket(c, k)
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def sp_assign_bucket(self, category, bucket):
        """Save a category → bucket assignment and refresh."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO category_bucket (category, bucket) VALUES (?, ?)",
            (category, bucket)
        )
        conn.commit()
        self.refresh_spending_plan()

    def set_cat_this_month(self): self.set_global_this_month()
    def set_cat_last_month(self): self.set_global_last_month()
    def set_cat_this_year(self):  self.set_global_this_year()
    def set_cat_all_time(self):   self.set_global_all_time()

    def refresh_transactions(self):
        """Refresh transactions list"""
        # Clear tree
        for item in self.txn_tree.get_children():
            self.txn_tree.delete(item)

        # Get filter
        filter_text = self.filter_var.get()
        limit = self.limit_var.get()
        date_from = self.date_from_var.get()
        date_to = self.date_to_var.get()
        account_filter = self.account_filter_var.get()

        # Refresh account dropdown with current DB accounts
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT account_name FROM transactions ORDER BY account_name")
        accounts = ["All Accounts"] + [r['account_name'] for r in cursor.fetchall()]
        self.account_combo['values'] = accounts
        if account_filter not in accounts:
            self.account_filter_var.set("All Accounts")
            account_filter = "All Accounts"

        # Build query
        query = "SELECT id, date, description, amount, category, account_name, transaction_type FROM transactions WHERE 1=1"
        params = []

        # Date range filter
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)

        if date_to:
            query += " AND date <= ?"
            params.append(date_to)

        # Account filter
        if account_filter and account_filter != "All Accounts":
            query += " AND account_name = ?"
            params.append(account_filter)

        # Text filter
        if filter_text:
            query += " AND (description LIKE ? OR category LIKE ?)"
            params.extend([f"%{filter_text}%", f"%{filter_text}%"])

        query += " ORDER BY date DESC"

        if limit != "All":
            query += f" LIMIT {limit}"

        # Execute
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)

        # Populate
        for row in cursor.fetchall():
            self.txn_tree.insert(
                '',
                'end',
                text=str(row['id']),
                values=(
                    row['date'],
                    row['description'][:50],
                    f"${row['amount']:,.2f}",
                    row['category'],
                    row['account_name'],
                    row['transaction_type'] or ''
                )
            )

        count = len(self.txn_tree.get_children())

        # Calculate summary statistics
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Build same query for stats - exclude transfers from expense/income totals
        stats_query = """SELECT
            SUM(CASE WHEN amount < 0 AND (transaction_type = 'expense' OR transaction_type IS NULL) THEN ABS(amount) ELSE 0 END) as expenses,
            SUM(CASE WHEN amount > 0 AND (transaction_type = 'income' OR transaction_type IS NULL) THEN amount ELSE 0 END) as income,
            COUNT(*) as count FROM transactions WHERE 1=1"""
        stats_params = []

        if date_from:
            stats_query += " AND date >= ?"
            stats_params.append(date_from)

        if date_to:
            stats_query += " AND date <= ?"
            stats_params.append(date_to)

        if account_filter and account_filter != "All Accounts":
            stats_query += " AND account_name = ?"
            stats_params.append(account_filter)

        if filter_text:
            stats_query += " AND (description LIKE ? OR category LIKE ?)"
            stats_params.extend([f"%{filter_text}%", f"%{filter_text}%"])

        cursor.execute(stats_query, stats_params)
        stats = cursor.fetchone()

        expenses = stats['expenses'] or 0
        income = stats['income'] or 0
        net = income - expenses

        # Update status with summary
        status = f"Showing {count} transactions"
        if date_from or date_to:
            if date_from and date_to:
                status += f" ({date_from} to {date_to})"
            elif date_from:
                status += f" (from {date_from})"
            elif date_to:
                status += f" (to {date_to})"

        status += f" | Expenses: ${expenses:,.2f} | Income: ${income:,.2f} | Net: ${net:,.2f}"

        self.status_var.set(status)

    def add_transaction(self):
        """Add a new transaction manually"""
        AddTransactionDialog(self.root, self.db, self.refresh_transactions)

    def edit_transaction(self, event):
        """Edit selected transaction"""
        selection = self.txn_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a transaction to edit")
            return

        item = selection[0]
        txn_id = self.txn_tree.item(item)['text']

        # Get transaction details
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE id = ?", (txn_id,))
        txn = cursor.fetchone()

        if not txn:
            return

        # Create edit dialog
        EditTransactionDialog(self.root, self.db, txn, self.refresh_transactions, self.learned_rules, self.refresh_rules)

    def delete_transaction(self):
        """Delete selected transaction"""
        selection = self.txn_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a transaction to delete")
            return

        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this transaction?"):
            return

        item = selection[0]
        txn_id = self.txn_tree.item(item)['text']

        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
        conn.commit()

        self.refresh_transactions()
        self.status_var.set("Transaction deleted")

    # Rules functions

    def refresh_rules(self):
        """Refresh rules list"""
        # Clear tree
        for item in self.rules_tree.get_children():
            self.rules_tree.delete(item)

        # Get learned rules
        rules = self.learned_rules.get_all_rules()

        # Count transactions per rule
        conn = self.db.get_connection()
        cursor = conn.cursor()

        for category, keywords in sorted(rules.items()):
            # Count transactions
            cursor.execute(
                "SELECT COUNT(*) as count FROM transactions WHERE category = ?",
                (category,)
            )
            count = cursor.fetchone()['count']

            self.rules_tree.insert(
                '',
                'end',
                text=category,
                values=(', '.join(keywords[:5]), count)
            )

        self.status_var.set(f"Loaded {len(rules)} rules")

    def add_rule(self):
        """Add a new rule"""
        self.rule_category_var.set("")
        self.rule_keyword_var.set("")

    def edit_rule(self):
        """Edit selected rule"""
        selection = self.rules_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a rule to edit")
            return

        item = selection[0]
        category = self.rules_tree.item(item)['text']

        # Get keywords for this category
        rules = self.learned_rules.get_all_rules()

        if category not in rules:
            messagebox.showwarning("Not Found", f"No rules found for '{category}'")
            return

        # Create callback that refreshes the Rules tab (learned_rules already updated in-place)
        def on_save():
            self.refresh_rules()

        # Open edit dialog
        EditRuleDialog(self.root, self.learned_rules, category, rules[category], on_save)

    def save_rule(self):
        """Save the current rule"""
        category = self.rule_category_var.get().strip()
        keyword = self.rule_keyword_var.get().strip().upper()

        if not category or not keyword:
            messagebox.showwarning("Missing Information", "Please enter both category and keyword")
            return

        self.learned_rules.add_rule(category, keyword)  # CORRECT ORDER: category, keyword

        self.rule_category_var.set("")
        self.rule_keyword_var.set("")

        self.refresh_rules()
        self.status_var.set(f"Added rule: {keyword} → {category}")

        messagebox.showinfo("Rule Added", f"Added rule: {keyword} → {category}")

    def delete_rule(self):
        """Delete selected rule"""
        selection = self.rules_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a rule to delete")
            return

        item = selection[0]
        category = self.rules_tree.item(item)['text']

        if messagebox.askyesno("Confirm Delete", f"Delete all rules for '{category}'?"):
            rules = self.learned_rules.get_all_rules()
            if category in rules:
                keyword_count = len(rules[category])
                # Delete each keyword via the shared instance (handles save to correct path)
                for keyword in list(rules[category]):
                    self.learned_rules.delete_rule(category, keyword)

                self.refresh_rules()
                self.status_var.set(f"Deleted {keyword_count} rule(s) for: {category}")
                messagebox.showinfo("Deleted", f"Deleted {keyword_count} keyword(s) for '{category}'")
            else:
                messagebox.showwarning("Not Found", f"No rules found for '{category}'")

    def show_category_transactions(self, event):
        """Show all transactions for the selected category"""
        selection = self.cat_tree.selection()
        if not selection:
            return

        # Get selected category
        item = selection[0]
        category = self.cat_tree.item(item)['text']

        # Switch to Transactions tab
        self.notebook.select(2)  # Index 2 = Transactions tab

        # Set filter to category (keep the global date range as-is)
        self.filter_var.set(category)

        # Set limit to show more results
        self.limit_var.set("All")

        # Refresh transactions to show filtered results
        self.refresh_transactions()

        date_from = self.global_from_var.get()
        date_to   = self.global_to_var.get()
        period    = f"{date_from} to {date_to}" if date_from or date_to else "all time"
        self.status_var.set(f"Showing {category} transactions ({period})")

    def show_category_menu(self, event):
        """Show context menu for category"""
        # Select the item under cursor
        item = self.cat_tree.identify_row(event.y)
        if item:
            self.cat_tree.selection_set(item)
            category = self.cat_tree.item(item)['text']

            # Get current date range
            date_from = self.cat_date_from_var.get()
            date_to = self.cat_date_to_var.get()

            # Create context menu
            menu = tk.Menu(self.root, tearoff=0)

            # Option 1: All transactions
            menu.add_command(
                label=f"View ALL '{category}' transactions",
                command=lambda: self.show_category_transactions(None)
            )

            # Option 2: Current period only (if date range is set)
            if date_from or date_to:
                period_label = ""
                if date_from and date_to:
                    period_label = f" ({date_from} to {date_to})"
                elif date_from:
                    period_label = f" (from {date_from})"
                elif date_to:
                    period_label = f" (to {date_to})"

                menu.add_command(
                    label=f"View '{category}' for current period{period_label}",
                    command=lambda: self.show_category_transactions_period(category, date_from, date_to)
                )

            menu.add_separator()
            menu.add_command(
                label="Export category to CSV",
                command=lambda: self.export_category(category)
            )

            # Show menu at cursor position
            menu.post(event.x_root, event.y_root)

    def show_category_transactions_period(self, category, date_from, date_to):
        """Show transactions for category within specific date range"""
        # Switch to Transactions tab
        self.notebook.select(2)

        # Set date range
        self.date_from_var.set(date_from or "")
        self.date_to_var.set(date_to or "")

        # Set filter to category
        self.filter_var.set(category)

        # Set limit
        self.limit_var.set("All")

        # Refresh
        self.refresh_transactions()

        # Update status
        period = ""
        if date_from and date_to:
            period = f" ({date_from} to {date_to})"
        elif date_from:
            period = f" (from {date_from})"
        elif date_to:
            period = f" (to {date_to})"

        self.status_var.set(f"Showing '{category}' transactions{period}")

    def export_category(self, category):
        """Export all transactions in a category to CSV"""
        from tkinter import filedialog
        import csv
        from datetime import datetime

        # Get date range
        date_from = self.cat_date_from_var.get()
        date_to = self.cat_date_to_var.get()

        # Build query
        query = "SELECT * FROM transactions WHERE category = ?"
        params = [category]

        if date_from:
            query += " AND date >= ?"
            params.append(date_from)

        if date_to:
            query += " AND date <= ?"
            params.append(date_to)

        query += " ORDER BY date DESC"

        # Get transactions
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        transactions = cursor.fetchall()

        if not transactions:
            messagebox.showinfo("No Data", f"No transactions found in category '{category}'")
            return

        # Ask for save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"{category.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
        )

        if not filename:
            return

        # Write to CSV
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)

                # Header
                writer.writerow(['Date', 'Description', 'Amount', 'Category', 'Account', 'Type', 'Notes'])

                # Data
                for txn in transactions:
                    writer.writerow([
                        txn['date'],
                        txn['description'],
                        txn['amount'],
                        txn['category'],
                        txn['account_name'],
                        txn['transaction_type'] or '',
                        txn['notes'] or ''
                    ])

            messagebox.showinfo(
                "Export Complete",
                f"Exported {len(transactions)} transactions to:\n{filename}"
            )

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export:\n\n{str(e)}")

    # Categories functions

    def refresh_categories(self):
        """Refresh categories list"""
        # Clear tree
        for item in self.cat_tree.get_children():
            self.cat_tree.delete(item)

        # Get date range
        date_from = self.cat_date_from_var.get()
        date_to = self.cat_date_to_var.get()

        # Get stats
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Build query with date filters - get both expenses and income per category
        query = """
            SELECT 
                category,
                COUNT(*) as count,
                SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as expenses,
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as income
            FROM transactions
            WHERE category NOT IN ('Credit Card Payment', 'Transfer')
              AND (transaction_type != 'transfer' OR transaction_type IS NULL)
        """
        params = []

        if date_from:
            query += " AND date >= ?"
            params.append(date_from)

        if date_to:
            query += " AND date <= ?"
            params.append(date_to)

        query += """
            GROUP BY category
            HAVING expenses > 0 OR income > 0
            ORDER BY (expenses - income) DESC
        """

        cursor.execute(query, params)

        results = cursor.fetchall()
        total_net_spending = sum(row['expenses'] - row['income'] for row in results)

        # Store data for chart
        chart_data = []

        for row in results:
            expenses = row['expenses'] or 0
            income = row['income'] or 0
            net = expenses - income

            # Calculate percentage based on net spending
            percentage = (net / total_net_spending * 100) if total_net_spending > 0 else 0

            self.cat_tree.insert(
                '',
                'end',
                text=row['category'],
                values=(
                    row['count'],
                    f"${expenses:,.2f}",
                    f"${income:,.2f}" if income > 0 else "-",
                    f"${net:,.2f}",
                    f"{percentage:.1f}%"
                )
            )

            # Only include in chart if net spending is positive
            if net > 0:
                chart_data.append({
                    'category': row['category'],
                    'total': net,
                    'percent': percentage
                })

        # Draw chart
        self.draw_category_chart(chart_data)

        # Update status with total and date range
        total_expenses = sum(row['expenses'] for row in results)
        total_income = sum(row['income'] for row in results)

        status = f"Total expenses: ${total_expenses:,.2f} | Total income: ${total_income:,.2f} | Net spending: ${total_net_spending:,.2f}"
        if date_from or date_to:
            if date_from and date_to:
                status += f" ({date_from} to {date_to})"
            elif date_from:
                status += f" (from {date_from})"
            elif date_to:
                status += f" (to {date_to})"

        self.status_var.set(status)

    def draw_category_chart(self, data):
        """Draw horizontal bar chart of category spending"""
        # Clear canvas
        self.cat_chart_canvas.delete('all')

        if not data:
            return

        # Get canvas dimensions
        canvas_width = self.cat_chart_canvas.winfo_width()
        canvas_height = 200

        # Use actual width if available, otherwise use default
        if canvas_width < 100:
            canvas_width = 800

        # Show top 10 categories
        top_data = data[:10]

        # Calculate bar dimensions
        bar_height = 15
        bar_spacing = 5
        left_margin = 150
        right_margin = 100
        top_margin = 10

        max_amount = max(d['total'] for d in top_data) if top_data else 1
        chart_width = canvas_width - left_margin - right_margin

        # Colors
        colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
            '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#ABEBC6'
        ]

        y = top_margin

        for i, item in enumerate(top_data):
            # Calculate bar width
            bar_width = (item['total'] / max_amount * chart_width) if max_amount > 0 else 0

            # Color
            color = colors[i % len(colors)]

            # Category label (left)
            self.cat_chart_canvas.create_text(
                left_margin - 10,
                y + bar_height / 2,
                text=item['category'][:20],
                anchor='e',
                font=('Arial', 9),
                fill='black'
            )

            # Bar
            self.cat_chart_canvas.create_rectangle(
                left_margin,
                y,
                left_margin + bar_width,
                y + bar_height,
                fill=color,
                outline=''
            )

            # Amount and percentage (right)
            label = f"${item['total']:,.0f} ({item['percent']:.1f}%)"
            self.cat_chart_canvas.create_text(
                left_margin + bar_width + 5,
                y + bar_height / 2,
                text=label,
                anchor='w',
                font=('Arial', 9, 'bold'),
                fill='black'
            )

            y += bar_height + bar_spacing


def _pick_date_popup(parent_window, string_var, on_select=None):
    """Standalone calendar popup — usable from any dialog class."""
    top = tk.Toplevel(parent_window)
    top.title("Pick a date")
    top.resizable(False, False)
    top.grab_set()
    cal = Calendar(top, selectmode='day', date_pattern='yyyy-mm-dd',
                   background='darkgreen', foreground='white',
                   headersbackground='#1a6e3c', headersforeground='white',
                   selectbackground='#f0a500', selectforeground='black',
                   normalbackground='#2d2d2d', normalforeground='white',
                   weekendbackground='#2d2d2d', weekendforeground='#aaffaa',
                   othermonthbackground='#1e1e1e', othermonthforeground='#666666')
    try:
        current = string_var.get()
        if current:
            cal.selection_set(current)
    except Exception:
        pass
    cal.pack(padx=10, pady=10)

    def apply(event=None):
        string_var.set(cal.get_date())
        top.destroy()
        if on_select:
            on_select()

    cal.bind("<<CalendarSelected>>", apply)


class AddTransactionDialog:
    """Dialog for adding a new transaction manually"""

    def __init__(self, parent, db, callback):
        self.db = db
        self.callback = callback

        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Transaction")
        self.dialog.geometry("500x500")

        # Title
        ttk.Label(
            self.dialog,
            text="Add New Transaction",
            font=('Arial', 14, 'bold')
        ).pack(pady=20)

        # Form
        form = ttk.Frame(self.dialog)
        form.pack(fill='both', expand=True, padx=20, pady=10)

        row = 0

        # Date (required)
        ttk.Label(form, text="Date: *", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=5)
        self.date_var = tk.StringVar()

        # Default to today
        from datetime import datetime
        self.date_var.set(datetime.now().strftime("%Y-%m-%d"))

        date_entry = ttk.Entry(form, textvariable=self.date_var, width=20)
        date_entry.grid(row=row, column=1, sticky='w', pady=5)
        ttk.Button(form, text="📅", width=3,
                   command=lambda: _pick_date_popup(self.dialog, self.date_var)).grid(row=row, column=2, sticky='w', padx=5)
        row += 1

        # Description (required)
        ttk.Label(form, text="Description: *", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=5)
        self.description_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.description_var, width=30).grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        # Amount (required)
        ttk.Label(form, text="Amount: *", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=5)
        self.amount_var = tk.StringVar()
        amount_frame = ttk.Frame(form)
        amount_frame.grid(row=row, column=1, sticky='w', pady=5)

        ttk.Entry(amount_frame, textvariable=self.amount_var, width=15).pack(side='left')
        ttk.Label(amount_frame, text="(negative for expenses)", font=('Arial', 8)).pack(side='left', padx=5)
        row += 1

        # Category
        ttk.Label(form, text="Category:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=5)

        # Get existing categories
        cursor = db.get_connection().cursor()
        cursor.execute("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL ORDER BY category")
        existing_categories = [r['category'] for r in cursor.fetchall()]

        self.category_var = tk.StringVar(value="Uncategorized")
        self.category_combo = ttk.Combobox(
            form,
            textvariable=self.category_var,
            values=existing_categories,
            width=28
        )
        self.category_combo.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        # Account
        ttk.Label(form, text="Account:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=5)

        # Get existing accounts
        cursor.execute(
            "SELECT DISTINCT account_name FROM transactions WHERE account_name IS NOT NULL ORDER BY account_name")
        existing_accounts = [r['account_name'] for r in cursor.fetchall()]

        # Add "Cash" as default option
        if "Cash" not in existing_accounts:
            existing_accounts.insert(0, "Cash")

        self.account_var = tk.StringVar(value="Cash")
        self.account_combo = ttk.Combobox(
            form,
            textvariable=self.account_var,
            values=existing_accounts,
            width=28
        )
        self.account_combo.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        # Transaction Type
        ttk.Label(form, text="Type:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=5)
        self.type_var = tk.StringVar(value="expense")
        type_frame = ttk.Frame(form)
        type_frame.grid(row=row, column=1, sticky='w', pady=5)

        ttk.Radiobutton(type_frame, text="Expense", variable=self.type_var, value="expense").pack(side='left', padx=5)
        ttk.Radiobutton(type_frame, text="Income", variable=self.type_var, value="income").pack(side='left', padx=5)
        ttk.Radiobutton(type_frame, text="Transfer", variable=self.type_var, value="transfer").pack(side='left', padx=5)
        row += 1

        # Tags
        ttk.Label(form, text="Tags:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=5)
        self.tags_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.tags_var, width=30).grid(row=row, column=1, sticky='w', pady=5)
        ttk.Label(form, text="(comma-separated)", font=('Arial', 8)).grid(row=row, column=2, sticky='w', padx=5)
        row += 1

        # Notes
        ttk.Label(form, text="Notes:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='nw', pady=5)
        self.notes_text = tk.Text(form, height=4, width=30)
        self.notes_text.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        # Required fields note
        ttk.Label(
            form,
            text="* Required fields",
            font=('Arial', 8, 'italic'),
            foreground='gray'
        ).grid(row=row, column=0, columnspan=2, sticky='w', pady=10)

        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="💾 Save", command=self.save, width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="❌ Cancel", command=self.dialog.destroy, width=15).pack(side='left', padx=5)

    def save(self):
        """Save the new transaction"""
        # Validate required fields
        date = self.date_var.get().strip()
        description = self.description_var.get().strip()
        amount_str = self.amount_var.get().strip()

        if not date:
            messagebox.showwarning("Missing Date", "Please enter a date")
            return

        if not description:
            messagebox.showwarning("Missing Description", "Please enter a description")
            return

        if not amount_str:
            messagebox.showwarning("Missing Amount", "Please enter an amount")
            return

        # Validate amount
        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showwarning("Invalid Amount", "Please enter a valid number for amount")
            return

        # Validate date format
        try:
            from datetime import datetime
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Invalid Date", "Please enter date in YYYY-MM-DD format")
            return

        # Get other fields
        category = self.category_var.get().strip() or "Uncategorized"
        account = self.account_var.get().strip() or "Cash"
        txn_type = self.type_var.get()
        tags = self.tags_var.get().strip()
        notes = self.notes_text.get('1.0', 'end').strip()

        # Insert into database
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO transactions
            (date, description, amount, account_name, account_type, institution, category, transaction_type, tags, notes, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date, description, amount, account,
            'Manual', 'Manual Entry',
            category, txn_type, tags or None, notes or None, None
        ))

        conn.commit()

        # Close dialog
        self.dialog.destroy()

        # Refresh transactions list
        self.callback()

        # Show confirmation
        messagebox.showinfo("Transaction Added", f"Added transaction: {description} - ${amount:,.2f}")


class EditTransactionDialog:
    """Dialog for editing a transaction"""

    def __init__(self, parent, db, txn, callback, learned_rules=None, rules_callback=None):
        self.db = db
        self.txn = txn
        self.callback = callback
        self.learned_rules = learned_rules
        self.rules_callback = rules_callback

        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Transaction")
        self.dialog.geometry("500x400")

        # Form
        form = ttk.Frame(self.dialog)
        form.pack(fill='both', expand=True, padx=20, pady=20)

        row = 0

        # Date
        ttk.Label(form, text="Date:").grid(row=row, column=0, sticky='w', pady=5)
        ttk.Label(form, text=txn['date']).grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        # Description
        ttk.Label(form, text="Description:").grid(row=row, column=0, sticky='w', pady=5)
        ttk.Label(form, text=txn['description'][:50]).grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        # Amount
        ttk.Label(form, text="Amount:").grid(row=row, column=0, sticky='w', pady=5)
        ttk.Label(form, text=f"${txn['amount']:,.2f}").grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        # Category (editable with autocomplete)
        ttk.Label(form, text="Category:").grid(row=row, column=0, sticky='w', pady=5)

        # Get existing categories for autocomplete
        cursor = db.get_connection().cursor()
        cursor.execute("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL ORDER BY category")
        existing_categories = [row['category'] for row in cursor.fetchall()]

        self.category_var = tk.StringVar(value=txn['category'])
        self.category_combo = ttk.Combobox(
            form,
            textvariable=self.category_var,
            values=existing_categories,
            width=28
        )
        self.category_combo.grid(row=row, column=1, sticky='w', pady=5)

        # Enable autocomplete - filter as you type
        def on_category_change(event):
            typed = self.category_var.get().lower()
            if typed == '':
                self.category_combo['values'] = existing_categories
            else:
                # Filter categories that start with or contain the typed text
                filtered = [cat for cat in existing_categories
                            if typed in cat.lower()]
                self.category_combo['values'] = filtered

        self.category_combo.bind('<KeyRelease>', on_category_change)
        row += 1

        # Transaction Type (editable)
        ttk.Label(form, text="Type:").grid(row=row, column=0, sticky='w', pady=5)

        type_frame = ttk.Frame(form)
        type_frame.grid(row=row, column=1, sticky='w', pady=5)

        self.type_var = tk.StringVar(value=txn['transaction_type'] or 'expense')

        ttk.Radiobutton(
            type_frame,
            text="Expense",
            variable=self.type_var,
            value="expense"
        ).pack(side='left', padx=5)

        ttk.Radiobutton(
            type_frame,
            text="Income",
            variable=self.type_var,
            value="income"
        ).pack(side='left', padx=5)

        ttk.Radiobutton(
            type_frame,
            text="Transfer",
            variable=self.type_var,
            value="transfer"
        ).pack(side='left', padx=5)

        row += 1

        # Tags (editable)
        ttk.Label(form, text="Tags:").grid(row=row, column=0, sticky='w', pady=5)
        self.tags_var = tk.StringVar(value=txn['tags'] if txn['tags'] else '')
        ttk.Entry(form, textvariable=self.tags_var, width=30).grid(row=row, column=1, sticky='w', pady=5)
        ttk.Label(form, text="(comma-separated)", font=('Arial', 8)).grid(row=row, column=2, sticky='w', padx=5)
        row += 1

        # Notes (editable)
        ttk.Label(form, text="Notes:").grid(row=row, column=0, sticky='nw', pady=5)
        self.notes_text = tk.Text(form, height=4, width=30)
        self.notes_text.grid(row=row, column=1, sticky='w', pady=5)
        if txn['notes']:
            self.notes_text.insert('1.0', txn['notes'])
        row += 1

        # Buttons
        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="💾 Save", command=self.save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="❌ Cancel", command=self.dialog.destroy).pack(side='left', padx=5)

    def save(self):
        """Save changes"""
        new_category = self.category_var.get()
        new_type = self.type_var.get()
        new_tags = self.tags_var.get().strip() or None
        new_notes = self.notes_text.get('1.0', 'end').strip() or None
        old_category = self.txn['category']
        old_type = self.txn['transaction_type']

        # Check if category changed
        category_changed = (new_category != old_category)
        type_changed = (new_type != old_type)

        # Update this transaction
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE transactions SET category = ?, transaction_type = ?, tags = ?, notes = ? WHERE id = ?",
            (new_category, new_type, new_tags, new_notes, self.txn['id'])
        )

        conn.commit()

        # If category changed, offer to learn rule and apply to all
        if category_changed and new_category != 'Uncategorized' and self.learned_rules:
            learned_rules = self.learned_rules

            # Suggest a keyword
            suggested_keyword = learned_rules.suggest_rule(self.txn['description'], new_category)

            if suggested_keyword:
                # Show editable keyword dialog so user can tweak the keyword
                prompt = _LearnRulePrompt(self.dialog, suggested_keyword, new_category)
                self.dialog.wait_window(prompt.dialog)

                if prompt.confirmed and prompt.keyword:
                    final_keyword = prompt.keyword

                    # Count how many other transactions match
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM transactions
                        WHERE description LIKE ? AND category != ? AND id != ?
                    """, (f'%{final_keyword}%', new_category, self.txn['id']))

                    match_count = cursor.fetchone()['count']

                    # Save the rule (CORRECT ORDER: category, keyword)
                    learned_rules.add_rule(new_category, final_keyword)

                    # Apply to all matching transactions
                    if match_count > 0:
                        cursor.execute("""
                            UPDATE transactions
                            SET category = ?
                            WHERE description LIKE ? AND category != ?
                        """, (new_category, f'%{final_keyword}%', new_category))

                        conn.commit()

                        from tkinter import messagebox
                        messagebox.showinfo(
                            "Rule Applied",
                            f"✅ Learned rule: '{final_keyword}' → '{new_category}'\n\n" +
                            f"Updated {match_count + 1} transaction(s) total"
                        )
                    else:
                        from tkinter import messagebox
                        messagebox.showinfo(
                            "Rule Saved",
                            f"✅ Learned rule: '{final_keyword}' → '{new_category}'\n\n" +
                            f"This will apply to future imports"
                        )

        self.dialog.destroy()
        self.callback()
        if self.rules_callback:
            self.rules_callback()


class EditRuleDialog:
    """Dialog for editing a categorization rule"""

    def __init__(self, parent, learned_rules, category, keywords, callback):
        self.learned_rules = learned_rules
        self.category = category
        self.keywords = keywords.copy()
        self.callback = callback

        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Rule: {category}")
        self.dialog.geometry("500x400")

        # Category name (editable)
        ttk.Label(
            self.dialog,
            text="Category:",
            font=('Arial', 10, 'bold')
        ).pack(pady=(20, 5))

        self.category_var = tk.StringVar(value=category)
        ttk.Entry(
            self.dialog,
            textvariable=self.category_var,
            width=40,
            font=('Arial', 12)
        ).pack(pady=5)

        # Keywords list
        ttk.Label(
            self.dialog,
            text="Keywords:",
            font=('Arial', 10, 'bold')
        ).pack(pady=(20, 5))

        # Frame for listbox and scrollbar
        list_frame = ttk.Frame(self.dialog)
        list_frame.pack(fill='both', expand=True, padx=20, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.keywords_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=('Arial', 11)
        )
        self.keywords_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.keywords_listbox.yview)

        # Populate keywords
        for kw in self.keywords:
            self.keywords_listbox.insert('end', kw)

        # Keyword management buttons
        kw_btn_frame = ttk.Frame(self.dialog)
        kw_btn_frame.pack(pady=10)

        ttk.Button(
            kw_btn_frame,
            text="➕ Add Keyword",
            command=self.add_keyword
        ).pack(side='left', padx=5)

        ttk.Button(
            kw_btn_frame,
            text="🗑️ Remove Selected",
            command=self.remove_keyword
        ).pack(side='left', padx=5)

        # Save/Cancel buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=10)

        ttk.Button(
            btn_frame,
            text="💾 Save Changes",
            command=self.save
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="❌ Cancel",
            command=self.dialog.destroy
        ).pack(side='left', padx=5)

    def add_keyword(self):
        """Add a new keyword to the list"""
        from tkinter import simpledialog

        keyword = simpledialog.askstring(
            "Add Keyword",
            "Enter keyword:",
            parent=self.dialog
        )

        if keyword:
            keyword = keyword.strip().upper()
            if keyword and keyword not in self.keywords:
                self.keywords.append(keyword)
                self.keywords_listbox.insert('end', keyword)
            elif keyword in self.keywords:
                messagebox.showwarning("Duplicate", f"Keyword '{keyword}' already exists")

    def remove_keyword(self):
        """Remove selected keyword from the list"""
        selection = self.keywords_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a keyword to remove")
            return

        idx = selection[0]
        keyword = self.keywords_listbox.get(idx)

        if messagebox.askyesno("Confirm", f"Remove keyword '{keyword}'?"):
            self.keywords.remove(keyword)
            self.keywords_listbox.delete(idx)

    def save(self):
        """Save changes to the rule"""
        new_category = self.category_var.get().strip()

        if not new_category:
            messagebox.showwarning("Missing Category", "Please enter a category name")
            return

        if not self.keywords:
            messagebox.showwarning("No Keywords", "Please add at least one keyword")
            return

        # Use the shared LearnedRules instance so the correct file path is used
        rules = self.learned_rules.rules

        # If category name changed, remove old entry
        if new_category != self.category and self.category in rules:
            del rules[self.category]

        # Update with new keywords
        rules[new_category] = self.keywords

        # Persist via the instance (handles path correctly in .app bundle)
        self.learned_rules._save_rules()

        # Close dialog first
        self.dialog.destroy()

        # Then refresh
        self.callback()

        # Show confirmation
        messagebox.showinfo(
            "Saved",
            f"Updated rule for '{new_category}' with {len(self.keywords)} keyword(s)"
        )


class MergeCategoriesDialog:
    """Dialog for merging categories"""

    def __init__(self, parent, db, callback1, callback2, category_mapper=None):
        self.db = db
        self.callback1 = callback1
        self.callback2 = callback2
        self.category_mapper = category_mapper

        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Merge Categories")
        self.dialog.geometry("600x500")

        # Instructions
        ttk.Label(
            self.dialog,
            text="Merge Categories",
            font=('Arial', 14, 'bold')
        ).pack(pady=10)

        ttk.Label(
            self.dialog,
            text="Select categories to merge into a single category",
            font=('Arial', 10)
        ).pack(pady=5)

        # Get all categories
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM transactions
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY category
        """)
        self.categories = cursor.fetchall()

        # Frame for lists
        lists_frame = ttk.Frame(self.dialog)
        lists_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Left: Source categories (to merge)
        left_frame = ttk.Frame(lists_frame)
        left_frame.pack(side='left', fill='both', expand=True, padx=5)

        ttk.Label(left_frame, text="Categories to Merge:", font=('Arial', 10, 'bold')).pack()

        self.source_listbox = tk.Listbox(left_frame, selectmode='multiple', height=15)
        self.source_listbox.pack(fill='both', expand=True, pady=5)

        for cat in self.categories:
            self.source_listbox.insert('end', f"{cat['category']} ({cat['count']})")

        # Right: Target category (merge into)
        right_frame = ttk.Frame(lists_frame)
        right_frame.pack(side='right', fill='both', expand=True, padx=5)

        ttk.Label(right_frame, text="Merge Into:", font=('Arial', 10, 'bold')).pack()

        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(
            right_frame,
            textvariable=self.target_var,
            values=[cat['category'] for cat in self.categories],
            width=30
        )
        self.target_combo.pack(pady=5)

        ttk.Label(right_frame, text="Or enter new category name:").pack(pady=(20, 5))

        # Preview
        self.preview_text = scrolledtext.ScrolledText(right_frame, height=10, width=30)
        self.preview_text.pack(fill='both', expand=True, pady=5)

        # Update preview when selection changes
        self.source_listbox.bind('<<ListboxSelect>>', self.update_preview)

        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="🔀 Merge", command=self.merge).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="❌ Cancel", command=self.dialog.destroy).pack(side='left', padx=5)

    def update_preview(self, event=None):
        """Update merge preview"""
        self.preview_text.delete('1.0', 'end')

        selected = self.source_listbox.curselection()
        if not selected:
            self.preview_text.insert('end', "Select categories to merge...")
            return

        target = self.target_var.get()
        if not target:
            self.preview_text.insert('end', "Enter target category name...")
            return

        self.preview_text.insert('end', f"Will merge:\n\n")

        total_txns = 0
        for idx in selected:
            cat = self.categories[idx]
            self.preview_text.insert('end', f"• {cat['category']} ({cat['count']} txns)\n")
            total_txns += cat['count']

        self.preview_text.insert('end', f"\n→ Into: {target}\n")
        self.preview_text.insert('end', f"\nTotal: {total_txns} transactions")

    def merge(self):
        """Perform the merge"""
        selected = self.source_listbox.curselection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select categories to merge")
            return

        target = self.target_var.get().strip()
        if not target:
            messagebox.showwarning("No Target", "Please enter target category name")
            return

        # Get selected category names
        source_cats = [self.categories[idx]['category'] for idx in selected]

        # Don't merge if target is in source
        if target in source_cats and len(source_cats) == 1:
            messagebox.showwarning("Invalid Merge", "Cannot merge category into itself")
            return

        # Confirm
        total = sum(self.categories[idx]['count'] for idx in selected)
        msg = f"Merge {len(source_cats)} categories into '{target}'?\n\n"
        msg += f"This will update {total} transactions."

        if not messagebox.askyesno("Confirm Merge", msg):
            return

        # Perform merge
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Save mappings for future imports (use shared instance so correct path is used)
        from src.category_mapper import CategoryMapper
        from src.learned_rules import LearnedRules
        mapper = self.category_mapper if self.category_mapper else CategoryMapper()
        learned_rules = LearnedRules()

        for cat in source_cats:
            if cat != target:  # Don't update if already the target
                cursor.execute(
                    "UPDATE transactions SET category = ? WHERE category = ?",
                    (target, cat)
                )
                # Remember this mapping for future imports
                mapper.add_mapping(cat, target)

                # Migrate learned rules from old category to new target
                old_keywords = learned_rules.get_keywords_for_category(cat)
                for keyword in list(old_keywords):
                    learned_rules.add_rule(target, keyword)
                    learned_rules.delete_rule(cat, keyword)

        conn.commit()

        self.dialog.destroy()
        self.callback1()
        self.callback2()

        messagebox.showinfo("Merge Complete", f"Merged {len(source_cats)} categories into '{target}'")


class DuplicateReviewDialog:
    """Dialog for reviewing and deleting duplicate transactions"""

    def __init__(self, parent, db, callback):
        self.db = db
        self.callback = callback

        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Review Duplicates")
        self.dialog.geometry("900x600")

        # Title
        ttk.Label(
            self.dialog,
            text="Review Duplicate Transactions",
            font=('Arial', 14, 'bold')
        ).pack(pady=10)

        # Instructions
        ttk.Label(
            self.dialog,
            text="Select duplicates to DELETE (keep one, delete the rest)",
            font=('Arial', 10)
        ).pack(pady=5)

        # Get duplicates
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT date, description, amount, GROUP_CONCAT(id) as ids, GROUP_CONCAT(account_name, ' | ') as accounts, COUNT(*) as count
            FROM transactions
            GROUP BY date, description, amount
            HAVING count > 1
            ORDER BY date DESC
        """)

        self.duplicate_groups = cursor.fetchall()

        # Tree view
        tree_frame = ttk.Frame(self.dialog)
        tree_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        self.dup_tree = ttk.Treeview(
            tree_frame,
            columns=('date', 'description', 'amount', 'count', 'accounts'),
            show='tree headings',
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            selectmode='extended'
        )

        vsb.config(command=self.dup_tree.yview)
        hsb.config(command=self.dup_tree.xview)

        self.dup_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Configure columns
        self.dup_tree.heading('#0', text='Select')
        self.dup_tree.heading('date', text='Date')
        self.dup_tree.heading('description', text='Description')
        self.dup_tree.heading('amount', text='Amount')
        self.dup_tree.heading('count', text='Copies')
        self.dup_tree.heading('accounts', text='Accounts')

        self.dup_tree.column('#0', width=50)
        self.dup_tree.column('date', width=100)
        self.dup_tree.column('description', width=300)
        self.dup_tree.column('amount', width=80)
        self.dup_tree.column('count', width=60)
        self.dup_tree.column('accounts', width=200)

        # Populate with duplicate groups
        for group in self.duplicate_groups:
            # Insert parent (the duplicate group)
            parent_id = self.dup_tree.insert(
                '',
                'end',
                text='',
                values=(
                    group['date'],
                    group['description'][:50],
                    f"${group['amount']}",
                    f"{group['count']} copies",
                    ''
                ),
                tags=('group',)
            )

            # Get all transactions in this group
            ids = group['ids'].split(',')
            for txn_id in ids:
                cursor.execute("SELECT * FROM transactions WHERE id = ?", (txn_id,))
                txn = cursor.fetchone()

                # Insert child (individual transaction)
                self.dup_tree.insert(
                    parent_id,
                    'end',
                    text=txn['id'],
                    values=(
                        txn['date'],
                        txn['description'][:50],
                        f"${txn['amount']}",
                        '',
                        txn['account_name']
                    ),
                    tags=('transaction',)
                )

        # Style
        self.dup_tree.tag_configure('group', background='#E8E8E8')

        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=10)

        ttk.Label(btn_frame, text="For each duplicate group, keep 1 and select the others to delete →").pack(
            side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="🗑️ Delete Selected",
            command=self.delete_selected
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="🔄 Auto-Delete Extras",
            command=self.auto_delete_extras
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="❌ Close",
            command=self.dialog.destroy
        ).pack(side='left', padx=5)

    def delete_selected(self):
        """Delete selected transactions"""
        selected = self.dup_tree.selection()

        if not selected:
            messagebox.showwarning("No Selection", "Please select transactions to delete")
            return

        # Get IDs to delete (only children, not groups)
        ids_to_delete = []
        for item in selected:
            item_id = self.dup_tree.item(item)['text']
            if item_id:  # Only if it has an ID (is a transaction, not a group)
                ids_to_delete.append(item_id)

        if not ids_to_delete:
            messagebox.showwarning("No Transactions", "Please select individual transactions (not groups)")
            return

        msg = f"Delete {len(ids_to_delete)} selected transaction(s)?\n\n"
        msg += "This cannot be undone!"

        if messagebox.askyesno("Confirm Delete", msg):
            conn = self.db.get_connection()
            cursor = conn.cursor()

            for txn_id in ids_to_delete:
                cursor.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))

            conn.commit()

            # Remove from tree
            for item in selected:
                self.dup_tree.delete(item)

            messagebox.showinfo("Deleted", f"Deleted {len(ids_to_delete)} transaction(s)")

            # Refresh parent window
            self.callback()

    def auto_delete_extras(self):
        """Automatically keep first transaction in each group, delete the rest"""
        msg = "Auto-delete duplicates?\n\n"
        msg += "This will:\n"
        msg += "• Keep the FIRST transaction in each duplicate group\n"
        msg += "• Delete all other copies\n\n"
        msg += f"Found {len(self.duplicate_groups)} duplicate groups\n\n"
        msg += "Continue?"

        if not messagebox.askyesno("Auto-Delete", msg):
            return

        conn = self.db.get_connection()
        cursor = conn.cursor()

        total_deleted = 0

        for group in self.duplicate_groups:
            ids = group['ids'].split(',')

            # Keep first, delete rest
            for txn_id in ids[1:]:  # Skip first (index 0)
                cursor.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
                total_deleted += 1

        conn.commit()

        messagebox.showinfo(
            "Complete",
            f"Deleted {total_deleted} duplicate transaction(s)\n\n" +
            f"Kept {len(self.duplicate_groups)} original(s)"
        )

        self.dialog.destroy()
        self.callback()


class _LearnRulePrompt:
    """Small dialog shown after manual category edit so the user can tweak the extracted keyword."""

    def __init__(self, parent, suggested_keyword: str, category: str):
        self.confirmed = False
        self.keyword = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Learn Categorization Rule?")
        self.dialog.geometry("420x200")
        self.dialog.grab_set()
        self.dialog.resizable(False, False)

        pad = dict(padx=16, pady=6)

        ttk.Label(
            self.dialog,
            text=f"Category: {category}",
            font=('Arial', 11, 'bold')
        ).pack(**pad, anchor='w')

        ttk.Label(
            self.dialog,
            text="Keyword (edit if needed):",
            font=('Arial', 10)
        ).pack(padx=16, pady=(8, 2), anchor='w')

        self._kw_var = tk.StringVar(value=suggested_keyword)
        entry = ttk.Entry(self.dialog, textvariable=self._kw_var, width=38, font=('Arial', 11))
        entry.pack(padx=16, pady=2)
        entry.select_range(0, 'end')
        entry.focus_set()

        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=12)

        ttk.Button(btn_frame, text="✅ Learn Rule", command=self._ok, width=16).pack(side='left', padx=6)
        ttk.Button(btn_frame, text="❌ Skip", command=self.dialog.destroy, width=10).pack(side='left', padx=6)

        self.dialog.bind('<Return>', lambda _: self._ok())
        self.dialog.bind('<Escape>', lambda _: self.dialog.destroy())

    def _ok(self):
        kw = self._kw_var.get().strip().upper()
        if not kw:
            messagebox.showwarning("Empty Keyword", "Please enter a keyword.", parent=self.dialog)
            return
        self.keyword = kw
        self.confirmed = True
        self.dialog.destroy()


class MergeAccountsDialog:
    """Dialog for merging duplicate or misnamed account names."""

    def __init__(self, parent, db, accounts: list, callback):
        self.db = db
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Merge Duplicate Accounts")
        self.dialog.geometry("620x560")
        self.dialog.grab_set()

        # ── Auto-detected duplicates section ──────────────────────────────────
        groups = self._detect_duplicates(accounts)

        outer = ttk.Frame(self.dialog)
        outer.pack(fill='both', expand=True, padx=14, pady=10)

        if groups:
            lf = ttk.LabelFrame(outer, text="Auto-Detected Duplicates", padding=8)
            lf.pack(fill='x', pady=(0, 10))

            for (bank, last4), members in groups.items():
                row_frame = ttk.Frame(lf)
                row_frame.pack(fill='x', pady=3)

                accounts_str = "  &  ".join(members)
                ttk.Label(row_frame, text=f"⚠  {accounts_str}", font=('Arial', 10)).pack(side='left')

                # Dropdown to pick canonical name (longer/more descriptive name first)
                canonical_var = tk.StringVar(value=max(members, key=len))
                cb = ttk.Combobox(row_frame, textvariable=canonical_var, values=members, width=28, state='readonly')
                cb.pack(side='right', padx=(6, 0))
                ttk.Label(row_frame, text="Keep:").pack(side='right', padx=4)

                ttk.Button(
                    row_frame, text="Apply",
                    command=lambda m=members, v=canonical_var: self._apply_group(m, v.get())
                ).pack(side='right', padx=4)
        else:
            ttk.Label(outer, text="No duplicate accounts detected automatically.",
                      font=('Arial', 10, 'italic')).pack()

        # ── Manual merge section ──────────────────────────────────────────────
        lf2 = ttk.LabelFrame(outer, text="Manual Merge — select accounts then enter target name", padding=8)
        lf2.pack(fill='both', expand=True)

        list_frame = ttk.Frame(lf2)
        list_frame.pack(fill='both', expand=True)

        sb = ttk.Scrollbar(list_frame)
        sb.pack(side='right', fill='y')

        self.listbox = tk.Listbox(list_frame, selectmode='multiple',
                                  yscrollcommand=sb.set, font=('Arial', 10), height=8)
        self.listbox.pack(side='left', fill='both', expand=True)
        sb.config(command=self.listbox.yview)

        for acc in accounts:
            self.listbox.insert('end', acc)

        target_frame = ttk.Frame(lf2)
        target_frame.pack(fill='x', pady=(6, 0))

        ttk.Label(target_frame, text="Rename all selected to:").pack(side='left')
        self._target_var = tk.StringVar()
        ttk.Entry(target_frame, textvariable=self._target_var, width=30).pack(side='left', padx=6)
        ttk.Button(target_frame, text="Merge Selected", command=self._merge_manual).pack(side='left')

        ttk.Button(outer, text="Close", command=self.dialog.destroy).pack(pady=8)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _detect_duplicates(self, accounts):
        import re

        def bank_key(name):
            n = name.lower()
            if any(x in n for x in ['amex', 'american express']):
                return 'amex'
            if any(x in n for x in ['bofa', 'bof a', 'bank of america']):
                return 'bofa'
            if 'chase' in n:
                return 'chase'
            if 'capital one' in n:
                return 'capitalone'
            if 'discover' in n:
                return 'discover'
            if 'citi' in n:
                return 'citi'
            return n

        def last4(name):
            m = re.search(r'\*(\d+)', name)
            if m:
                return m.group(1)[-4:]
            return None

        groups: dict = {}
        for acc in accounts:
            l4 = last4(acc)
            if l4:
                key = (bank_key(acc), l4)
                groups.setdefault(key, []).append(acc)

        return {k: v for k, v in groups.items() if len(v) > 1}

    def _apply_group(self, members: list, keep: str):
        others = [m for m in members if m != keep]
        if not others:
            messagebox.showinfo("Nothing to do", "All accounts already have that name.", parent=self.dialog)
            return
        msg = "Rename:\n"
        for o in others:
            msg += f"  {o}  →  {keep}\n"
        msg += f"\nAll transactions will be moved to '{keep}'. Continue?"
        if not messagebox.askyesno("Merge Accounts", msg, parent=self.dialog):
            return
        self._do_rename({o: keep for o in others})

    def _merge_manual(self):
        sel = self.listbox.curselection()
        if len(sel) < 2:
            messagebox.showwarning("Select Accounts", "Select at least 2 accounts to merge.", parent=self.dialog)
            return
        target = self._target_var.get().strip()
        if not target:
            messagebox.showwarning("Enter Target", "Please enter the target account name.", parent=self.dialog)
            return
        selected = [self.listbox.get(i) for i in sel]
        sources = [s for s in selected if s != target]
        if not sources:
            messagebox.showinfo("Nothing to do", "All selected accounts already have that name.", parent=self.dialog)
            return
        msg = "Rename:\n"
        for s in sources:
            msg += f"  {s}  →  {target}\n"
        msg += f"\nAll transactions will be moved to '{target}'. Continue?"
        if not messagebox.askyesno("Merge Accounts", msg, parent=self.dialog):
            return
        self._do_rename({s: target for s in sources})

    def _do_rename(self, mapping: dict):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        for old, new in mapping.items():
            cursor.execute(
                "UPDATE transactions SET account_name = ? WHERE account_name = ?",
                (new, old)
            )
        conn.commit()
        messagebox.showinfo("Done", f"Merged {len(mapping)} account name(s) successfully.", parent=self.dialog)
        self.callback()
        # Refresh listbox
        cursor.execute("SELECT DISTINCT account_name FROM transactions ORDER BY account_name")
        accounts = [row['account_name'] for row in cursor.fetchall()]
        self.listbox.delete(0, 'end')
        for acc in accounts:
            self.listbox.insert('end', acc)


def main():
    """Run the application"""
    root = tk.Tk()
    app = CashflowApp(root)

    # Force window to front and keep visible (Mac fix)
    root.lift()
    root.attributes('-topmost', True)
    root.after(100, lambda: root.attributes('-topmost', False))
    root.focus_force()

    root.mainloop()


if __name__ == "__main__":
    main()