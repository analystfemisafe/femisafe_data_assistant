import os
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta
from sqlalchemy import create_engine, text

# ---------------------------------------------------------
# Database Helper (Universal)
# ---------------------------------------------------------
def get_db_engine():
    try:
        # 1. Try Local Secrets (Laptop)
        db_url = st.secrets["postgres"]["url"]
    except (FileNotFoundError, KeyError):
        # 2. Try Render Environment Variable (Cloud)
        db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        st.error("❌ Database URL not found. Check secrets.toml or Render Environment Variables.")
        return None

    return create_engine(db_url)

# ---------------------------------------------------------
# Fetch Blinkit Data
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def get_blinkit_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    order_date,
                    sku,
                    product,
                    feeder_wh,
                    net_revenue,
                    quantity
                FROM femisafe_blinkit_salesdata
            """)
            df = pd.read_sql(query, conn)
        
        # Process dates
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
        df["date"] = df["order_date"].dt.date
        return df

    except Exception as e:
        st.error(f"⚠️ Database Connection Failed: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# PAGE FUNCTION
# ---------------------------------------------------------

def page():

    st.markdown("### 🏙️ City-wise Sales Report (Last 7 Days Comparison)")

    # ===================== Get Blinkit Data =====================
    df = get_blinkit_data()

    if df.empty:
        st.warning("No data available.")
        return

    df['order_date'] = pd.to_datetime(df['order_date'])
    df['date'] = df['order_date'].dt.date

    # Get latest, D-1, and D-7
    latest_date = df['date'].max()
    d1_date = latest_date - timedelta(days=1)
    d7_date = latest_date - timedelta(days=7)

    # Filter only relevant dates
    df_filtered = df[df['date'].isin([d7_date, d1_date, latest_date])]

    if df_filtered.empty:
        st.warning("No data found for the comparison dates.")
        return

    # Aggregate
    grouped = df_filtered.groupby(['feeder_wh', 'sku', 'date']).agg({
        'net_revenue': 'sum',
        'quantity': 'sum'
    }).reset_index()

    # Pivot
    pivot = grouped.pivot_table(
        index=['feeder_wh', 'sku'],
        columns='date',
        values=['net_revenue', 'quantity'],
        fill_value=0
    ).reset_index()

    # Flatten column names
    pivot.columns = [
        f"{i}_{j.strftime('%b%d')}" if j != '' else i
        for i, j in pivot.columns
    ]

    # Reorder columns (Check if columns exist first to prevent errors)
    expected_cols = [
        'feeder_wh', 'sku',
        f'quantity_{d7_date.strftime("%b%d")}', f'net_revenue_{d7_date.strftime("%b%d")}',
        f'quantity_{d1_date.strftime("%b%d")}', f'net_revenue_{d1_date.strftime("%b%d")}',
        f'quantity_{latest_date.strftime("%b%d")}', f'net_revenue_{latest_date.strftime("%b%d")}'
    ]
    
    # Filter out any missing columns (e.g. if one date has no sales)
    available_cols = [col for col in expected_cols if col in pivot.columns]
    pivot = pivot[available_cols]

    # Delta columns (Ensure columns exist before calculating)
    q_latest = f'quantity_{latest_date.strftime("%b%d")}'
    q_d7 = f'quantity_{d7_date.strftime("%b%d")}'
    r_latest = f'net_revenue_{latest_date.strftime("%b%d")}'
    r_d7 = f'net_revenue_{d7_date.strftime("%b%d")}'

    if q_latest in pivot.columns and q_d7 in pivot.columns:
        pivot['Units Delta'] = pivot[q_latest] - pivot[q_d7]
    else:
        pivot['Units Delta'] = 0

    if r_latest in pivot.columns and r_d7 in pivot.columns:
        pivot['Revenue Delta'] = pivot[r_latest] - pivot[r_d7]
    else:
        pivot['Revenue Delta'] = 0

    # ================== Subtotals Per Feeder ==================
    subtotal_rows = []
    for feeder, group in pivot.groupby('feeder_wh', group_keys=False):

        group = group.copy()  # IMPORTANT FIX

        # Create subtotal dictionary dynamically based on available columns
        subtotal_data = {
            'feeder_wh': [feeder],
            'sku': [f"{feeder} Total"]
        }
        
        # Sum only the quantity/revenue columns that exist
        for col in available_cols:
            if "quantity" in col or "net_revenue" in col:
                subtotal_data[col] = [group[col].sum()]

        subtotal = pd.DataFrame(subtotal_data)

        # Recalculate Deltas for Subtotal
        if q_latest in subtotal.columns and q_d7 in subtotal.columns:
            subtotal['Units Delta'] = subtotal[q_latest] - subtotal[q_d7]
        else:
            subtotal['Units Delta'] = 0

        if r_latest in subtotal.columns and r_d7 in subtotal.columns:
            subtotal['Revenue Delta'] = subtotal[r_latest] - subtotal[r_d7]
        else:
            subtotal['Revenue Delta'] = 0

        # Calculate Growth %
        if r_latest in subtotal.columns and r_d7 in subtotal.columns:
            prev = subtotal[r_d7].iloc[0]
            curr = subtotal[r_latest].iloc[0]
            subtotal['Growth %'] = 0 if prev == 0 else round(((curr - prev) / prev) * 100, 2)
        else:
            subtotal['Growth %'] = 0

        group['Growth %'] = ""
        subtotal_rows.append(pd.concat([group, subtotal], ignore_index=True))

    final_df = pd.concat(subtotal_rows, ignore_index=True)

    # Convert quantities to int (safely)
    for col in final_df.columns:
        if "quantity" in col:
            final_df[col] = pd.to_numeric(final_df[col], errors='coerce').fillna(0).astype(int)

    # ================= Multi-level header formatting =================
    date_labels = {
        d7_date.strftime("%b%d"): d7_date.strftime("%B %d"),
        d1_date.strftime("%b%d"): d1_date.strftime("%B %d"),
        latest_date.strftime("%b%d"): latest_date.strftime("%B %d"),
    }

    # Dynamic multi-index based on available columns
    new_columns = []
    for col in final_df.columns:
        if col == 'feeder_wh':
            new_columns.append(('Feeder WH', ''))
        elif col == 'sku':
            new_columns.append(('SKU', ''))
        elif 'quantity_' in col:
            date_part = col.replace('quantity_', '')
            new_columns.append((date_labels.get(date_part, date_part), 'Units'))
        elif 'net_revenue_' in col:
            date_part = col.replace('net_revenue_', '')
            new_columns.append((date_labels.get(date_part, date_part), 'Net Rev'))
        elif col == 'Units Delta':
            new_columns.append(('Delta', 'Units Delta'))
        elif col == 'Revenue Delta':
            new_columns.append(('Delta', 'Revenue Delta'))
        elif col == 'Growth %':
            new_columns.append(('Delta', 'Growth %'))
        else:
            new_columns.append(('Other', col))

    final_df.columns = pd.MultiIndex.from_tuples(new_columns)

    st.dataframe(final_df, use_container_width=True)

    # ---------------------------------------------------------
    # FILTERS (Side-by-side — Product + Warehouse)
    # ---------------------------------------------------------

    st.markdown("### 🔍 Filters")

    col1, col2 = st.columns(2)

    all_products = sorted(df['product'].dropna().unique())
    all_warehouses = sorted(df['feeder_wh'].dropna().unique())

    with col1:
        selected_product = st.selectbox("Select Product", ["All"] + list(all_products))

    with col2:
        selected_warehouse = st.selectbox("Select Warehouse", ["All"] + list(all_warehouses))

    # Apply filters
    filtered = df.copy()

    if selected_product != "All":
        filtered = filtered[filtered['product'] == selected_product]

    if selected_warehouse != "All":
        filtered = filtered[filtered['feeder_wh'] == selected_warehouse]


    # ---------------------------------------------------------
    # LAST 30 DAYS CHART
    # ---------------------------------------------------------

    filtered['date'] = filtered['order_date'].dt.date

    start_date = latest_date - timedelta(days=30)

    last_30 = filtered[filtered['date'] >= start_date]

    daily_summary = last_30.groupby('date').agg({
        'quantity': 'sum',
        'net_revenue': 'sum'
    }).reset_index()

    daily_summary = daily_summary.sort_values('date')

    # ---------------------------------------------------------
    # BAR CHART (Units labels + revenue on hover)
    # ---------------------------------------------------------

    fig = px.bar(
        daily_summary,
        x='date',
        y='quantity',
        hover_data={'net_revenue': True, 'quantity': True},
        labels={'quantity': 'Units Sold', 'date': 'Date'},
    )

    fig.update_traces(text=daily_summary['quantity'], textposition='outside')

    fig.update_layout(
        height=450,
        xaxis_title="Date",
        yaxis_title="Units Sold",
        bargap=0.2
    )

    st.plotly_chart(fig, use_container_width=True)