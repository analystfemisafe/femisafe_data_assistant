import streamlit as st
import pandas as pd
import psycopg2
from datetime import timedelta

# ---------------------------------------------------------
# Fetch Blinkit Data (COMMON FUNCTION)
# ---------------------------------------------------------

@st.cache_data(ttl=600)
def get_blinkit_data():
    conn = psycopg2.connect(
        dbname="femisafe_test_db",
        user="ayish",
        password="ajtp@511Db",
        host="localhost",
        port="5432"
    )
    query = """
        SELECT 
            order_date,
            sku,
            product,
            feeder_wh,
            net_revenue,
            quantity
        FROM femisafe_blinkit_salesdata;
    """
    df = pd.read_sql(query, conn)
    conn.close()

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["date"] = df["order_date"].dt.date
    return df

# ---------------------------------------------------------
# PAGE FUNCTION
# ---------------------------------------------------------

def page():

    st.markdown("### 🏙️ City-wise Sales Report (Last 7 Days Comparison)")

    # ===================== Get Blinkit Data =====================
    df = get_blinkit_data()
    df['order_date'] = pd.to_datetime(df['order_date'])
    df['date'] = df['order_date'].dt.date

    # Get latest, D-1, and D-7
    latest_date = df['date'].max()
    d1_date = latest_date - pd.Timedelta(days=1)
    d7_date = latest_date - pd.Timedelta(days=7)

    # Filter only relevant dates
    df_filtered = df[df['date'].isin([d7_date, d1_date, latest_date])]

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

    # Reorder columns
    pivot = pivot[['feeder_wh', 'sku',
                f'quantity_{d7_date.strftime("%b%d")}', f'net_revenue_{d7_date.strftime("%b%d")}',
                f'quantity_{d1_date.strftime("%b%d")}', f'net_revenue_{d1_date.strftime("%b%d")}',
                f'quantity_{latest_date.strftime("%b%d")}', f'net_revenue_{latest_date.strftime("%b%d")}']]

    # Delta columns
    pivot['Units Delta'] = pivot[f'quantity_{latest_date.strftime("%b%d")}'] - pivot[f'quantity_{d7_date.strftime("%b%d")}']
    pivot['Revenue Delta'] = pivot[f'net_revenue_{latest_date.strftime("%b%d")}'] - pivot[f'net_revenue_{d7_date.strftime("%b%d")}']

    # ================== Subtotals Per Feeder ==================
    subtotal_rows = []
    for feeder, group in pivot.groupby('feeder_wh', group_keys=False):

        group = group.copy()  # IMPORTANT FIX

        subtotal = pd.DataFrame({
            'feeder_wh': [feeder],
            'sku': [f"{feeder} Total"],
            f'quantity_{d7_date.strftime("%b%d")}': [group[f'quantity_{d7_date.strftime("%b%d")}'].sum()],
            f'net_revenue_{d7_date.strftime("%b%d")}': [group[f'net_revenue_{d7_date.strftime("%b%d")}'].sum()],
            f'quantity_{d1_date.strftime("%b%d")}': [group[f'quantity_{d1_date.strftime("%b%d")}'].sum()],
            f'net_revenue_{d1_date.strftime("%b%d")}': [group[f'net_revenue_{d1_date.strftime("%b%d")}'].sum()],
            f'quantity_{latest_date.strftime("%b%d")}': [group[f'quantity_{latest_date.strftime("%b%d")}'].sum()],
            f'net_revenue_{latest_date.strftime("%b%d")}': [group[f'net_revenue_{latest_date.strftime("%b%d")}'].sum()],
        })

        # FIXED f-string closing
        subtotal['Units Delta'] = ( 
            subtotal[f'quantity_{latest_date.strftime("%b%d")}'] -
            subtotal[f'quantity_{d7_date.strftime("%b%d")}']
        )

        subtotal['Revenue Delta'] = (
            subtotal[f'net_revenue_{latest_date.strftime("%b%d")}'] -
            subtotal[f'net_revenue_{d7_date.strftime("%b%d")}']
        )

        prev = subtotal[f'net_revenue_{d7_date.strftime("%b%d")}'].iloc[0]
        curr = subtotal[f'net_revenue_{latest_date.strftime("%b%d")}'].iloc[0]
        subtotal['Growth %'] = 0 if prev == 0 else round(((curr - prev) / prev) * 100, 2)

        group['Growth %'] = ""
        subtotal_rows.append(pd.concat([group, subtotal], ignore_index=True))

    final_df = pd.concat(subtotal_rows, ignore_index=True)

    # Convert quantities
    for col in final_df.columns:
        if "quantity" in col:
            final_df[col] = final_df[col].astype(int)

    # ================= Multi-level header formatting blinkit citywise=================
    date_labels = {
        d7_date.strftime("%b%d"): d7_date.strftime("%B %d"),
        d1_date.strftime("%b%d"): d1_date.strftime("%B %d"),
        latest_date.strftime("%b%d"): latest_date.strftime("%B %d"),
    }

    multi_columns = pd.MultiIndex.from_tuples([
        ('Feeder WH', ''), 
        ('SKU', ''),
        (date_labels[d7_date.strftime("%b%d")], 'Units'),
        (date_labels[d7_date.strftime("%b%d")], 'Net Rev'),
        (date_labels[d1_date.strftime("%b%d")], 'Units'),
        (date_labels[d1_date.strftime("%b%d")], 'Net Rev'),
        (date_labels[latest_date.strftime("%b%d")], 'Units'),
        (date_labels[latest_date.strftime("%b%d")], 'Net Rev'),
        ('Delta', 'Units Delta'),
        ('Delta', 'Revenue Delta'),
        ('Delta', 'Growth %')
    ])

    final_df.columns = multi_columns

    st.dataframe(final_df, use_container_width=True)

    # ---------------------------------------------------------
    # FILTERS (Side-by-side — Product + Warehouse)
    # ---------------------------------------------------------

    st.markdown("### 🔍 Filters")

    col1, col2 = st.columns(2)

    # FIX: use product column instead of SKU
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
    # LAST 30 DAYS CHART (Fix datetime error)
    # ---------------------------------------------------------

    filtered['date'] = filtered['order_date'].dt.date

    # latest_date is already a datetime.date → SAFE
    start_date = latest_date - pd.Timedelta(days=30)

    # FIX: remove .date()
    last_30 = filtered[filtered['date'] >= start_date]

    daily_summary = last_30.groupby('date').agg({
        'quantity': 'sum',
        'net_revenue': 'sum'
    }).reset_index()

    daily_summary = daily_summary.sort_values('date')



    # ---------------------------------------------------------
    # BAR CHART (Units labels + revenue on hover)
    # ---------------------------------------------------------

    import plotly.express as px

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
