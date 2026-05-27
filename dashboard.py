#!/usr/bin/env python3
"""
Interactive Spending Dashboard

Run with: streamlit run dashboard.py
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from src.database import DatabaseManager

try:
    import streamlit as st
    import plotly.express as px
    import plotly.graph_objects as go

    HAS_STREAMLIT = True
except ImportError:
    print("❌ streamlit and plotly required")
    print("   Install with: pip install streamlit plotly")
    sys.exit(1)

# Page config
st.set_page_config(
    page_title="Cashflow Tracker Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def get_db():
    """Get database connection"""
    return DatabaseManager()


@st.cache_data(ttl=60)
def load_transactions():
    """Load all transactions"""
    db = get_db()
    conn = db.get_connection()

    query = "SELECT * FROM transactions ORDER BY date DESC"
    df = pd.read_sql_query(query, conn)
    df['date'] = pd.to_datetime(df['date'])

    return df


@st.cache_data(ttl=60)
def get_summary_stats(df):
    """Calculate summary statistics"""
    # Exclude transfers from spending
    spending_df = df[(df['amount'] < 0) &
                     ((df['transaction_type'] == 'expense') | (df['transaction_type'].isna()))]
    income_df = df[(df['amount'] > 0) &
                   ((df['transaction_type'] == 'income') | (df['transaction_type'].isna()))]

    total_spending = spending_df['amount'].abs().sum()
    total_income = income_df['amount'].sum()
    net = total_income - total_spending

    return {
        'total_spending': total_spending,
        'total_income': total_income,
        'net': net,
        'transaction_count': len(df),
        'avg_transaction': spending_df['amount'].abs().mean()
    }


def main():
    # Title
    st.title("💰 Cashflow Tracker Dashboard")
    st.markdown("---")

    # Load data
    df = load_transactions()

    if df.empty:
        st.warning("📭 No transactions found. Import some data first!")
        return

    # Sidebar filters
    st.sidebar.header("🔍 Filters")

    # Date range
    min_date = df['date'].min().date()
    max_date = df['date'].max().date()

    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # Category filter
    categories = ['All'] + sorted(df[df['category'] != 'Uncategorized']['category'].unique().tolist())
    selected_category = st.sidebar.selectbox("Category", categories)

    # Account filter
    accounts = ['All'] + sorted(df['account_name'].unique().tolist())
    selected_account = st.sidebar.selectbox("Account", accounts)

    # Apply filters
    mask = (df['date'].dt.date >= date_range[0]) & (df['date'].dt.date <= date_range[1])

    if selected_category != 'All':
        mask &= df['category'] == selected_category

    if selected_account != 'All':
        mask &= df['account_name'] == selected_account

    filtered_df = df[mask]

    # Summary metrics
    st.header("📊 Overview")

    stats = get_summary_stats(filtered_df)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Spending",
            f"${stats['total_spending']:,.2f}",
            help="Total amount spent (negative transactions)"
        )

    with col2:
        st.metric(
            "Total Income",
            f"${stats['total_income']:,.2f}",
            help="Total income (positive transactions)"
        )

    with col3:
        st.metric(
            "Net",
            f"${stats['net']:,.2f}",
            delta=f"${stats['net']:,.2f}",
            delta_color="normal" if stats['net'] >= 0 else "inverse",
            help="Income - Spending"
        )

    with col4:
        st.metric(
            "Transactions",
            f"{stats['transaction_count']:,}",
            help="Total number of transactions"
        )

    st.markdown("---")

    # Charts section
    st.header("📈 Visualizations")

    # Row 1: Pie chart and bar chart
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Spending by Category")

        # Category spending - exclude transfers
        spending_mask = (filtered_df['amount'] < 0) & \
                        ((filtered_df['transaction_type'] == 'expense') |
                         (filtered_df['transaction_type'].isna()))

        category_spending = filtered_df[spending_mask].groupby('category')['amount'].apply(
            lambda x: abs(x).sum()
        ).sort_values(ascending=False)

        if not category_spending.empty:
            fig = px.pie(
                values=category_spending.values,
                names=category_spending.index,
                title="Spending Distribution",
                hole=0.3
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No spending data in selected range")

    with col2:
        st.subheader("Top Categories")

        if not category_spending.empty:
            fig = px.bar(
                x=category_spending.head(10).values,
                y=category_spending.head(10).index,
                orientation='h',
                title="Top 10 Categories by Spending",
                labels={'x': 'Amount ($)', 'y': 'Category'}
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available")

    # Row 2: Monthly trend
    st.subheader("Monthly Spending Trend")

    # Group by month
    monthly = filtered_df.copy()
    monthly['month'] = monthly['date'].dt.to_period('M').astype(str)

    # Exclude transfers
    spending_mask = (monthly['amount'] < 0) & \
                    ((monthly['transaction_type'] == 'expense') |
                     (monthly['transaction_type'].isna()))
    income_mask = (monthly['amount'] > 0) & \
                  ((monthly['transaction_type'] == 'income') |
                   (monthly['transaction_type'].isna()))

    monthly_spending = monthly[spending_mask].groupby('month')['amount'].apply(
        lambda x: abs(x).sum()
    )
    monthly_income = monthly[income_mask].groupby('month')['amount'].sum()

    if not monthly_spending.empty or not monthly_income.empty:
        fig = go.Figure()

        if not monthly_spending.empty:
            fig.add_trace(go.Scatter(
                x=monthly_spending.index,
                y=monthly_spending.values,
                name='Spending',
                mode='lines+markers',
                line=dict(color='#e74c3c', width=3),
                marker=dict(size=10)
            ))

        if not monthly_income.empty:
            fig.add_trace(go.Scatter(
                x=monthly_income.index,
                y=monthly_income.values,
                name='Income',
                mode='lines+markers',
                line=dict(color='#27ae60', width=3),
                marker=dict(size=10)
            ))

        fig.update_layout(
            title="Monthly Spending vs Income",
            xaxis_title="Month",
            yaxis_title="Amount ($)",
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No monthly data available")

    # Row 3: Recent transactions
    st.markdown("---")
    st.header("📋 Recent Transactions")

    # Show count selector
    show_count = st.slider("Number of transactions to show", 10, 100, 20)

    # Display transactions
    display_df = filtered_df.head(show_count)[
        ['date', 'description', 'amount', 'category', 'account_name', 'merchant', 'notes']
    ].copy()

    # Format amount
    display_df['amount'] = display_df['amount'].apply(lambda x: f"${x:,.2f}")

    # Format date
    display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'date': 'Date',
            'description': 'Description',
            'amount': 'Amount',
            'category': 'Category',
            'account_name': 'Account',
            'merchant': 'Merchant',
            'notes': 'Notes'
        }
    )

    # Export button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

    with col2:
        st.button("🔄 Refresh Data", on_click=st.cache_data.clear)

    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()