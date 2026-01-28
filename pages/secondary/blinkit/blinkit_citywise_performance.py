import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta
from sqlalchemy import text

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    # Fallback if utils folder missing
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine(): return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 🚀 OPTIMIZED DATA LOADER
# ---------------------------------------------------------
@st.cache_data(ttl=900)  # Cache for 15 minutes
def get_blinkit_data():
    engine = get_db_engine()
    if not engine: return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: 
            # 1. Select ONLY needed columns
            # 2. Filter 'Cancelled' here to reduce download size
            query = text("""
                SELECT 
                    order_date,
                    sku,
                    product,
                    feeder_wh,
                    net_revenue,
                    quantity
                FROM femisafe_blinkit_salesdata
                WHERE order_status NOT IN ('Cancelled', 'Returned')
            """)
            df = pd.read_sql(query, conn)
        
        if df.empty: return df
        
        # =========================================================
        # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
        # =========================================================
        
        # 1. Fast Vectorized Cleaning
        for col in ['net_revenue', 'quantity']:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r'[₹,]', '', regex=True), 
                errors='coerce'
            ).fillna(0)

        # 2. Downcast numeric types
        df['quantity'] = df['quantity'].astype('int32')

        # 3. Use Categories for Text (Instant filtering)
        df['feeder_wh'] = df['feeder_wh'].fillna("Unknown").astype(str).str.title().astype('category')
        df['product'] = df['product'].astype('category')
        df['sku'] = df['sku'].astype('category')
        
        # 4. Fast Date Parsing
        df["order_date"] = pd.to_datetime(df["order_date"], dayfirst=True, errors="coerce")
        df.dropna(subset=['order_date'], inplace=True)
        df["date"] = df["order_date"].dt.date
        
        return df

    except Exception as e:
        st.error(f"⚠️ Database Connection Failed: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# PAGE FUNCTION
# ---------------------------------------------------------

def page():

    st.markdown("### 🏙️ City-wise Sales Report (Optimized)")

    # ===================== Get Blinkit Data =====================
    # Load Data (Instant if cached)
    df = get_blinkit_data()

    if df.empty:
        st.warning("No data available.")
        return

    # Get latest, D-1, and D-7
    latest_date = df['date'].max()
    d1_date = latest_date - timedelta(days=1)
    d7_date = latest_date - timedelta(days=7)

    # Filter only relevant dates
    df_filtered = df[df['date'].isin([d7_date, d1_date, latest_date])]
    
    if df_filtered.empty:
        st.warning(f"No data found for {latest_date}, {d1_date}, or {d7_date}.")
        return

    # Aggregate
    # observed=True speeds up grouping on Categories
    grouped = df_filtered.groupby(['feeder_wh', 'sku', 'date'], observed=True).agg({
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

    # Reorder columns (Check dynamically if columns exist)
    cols_to_keep = ['feeder_wh', 'sku']
    date_suffixes = [d7_date, d1_date, latest_date]
    
    for d in date_suffixes:
        q_col = f'quantity_{d.strftime("%b%d")}'
        r_col = f'net_revenue_{d.strftime("%b%d")}'
        if q_col in pivot.columns: cols_to_keep.append(q_col)
        if r_col in pivot.columns: cols_to_keep.append(r_col)
            
    pivot = pivot[cols_to_keep]

    # Delta columns (Safely)
    q_latest = f'quantity_{latest_date.strftime("%b%d")}'
    q_d7 = f'quantity_{d7_date.strftime("%b%d")}'
    r_latest = f'net_revenue_{latest_date.strftime("%b%d")}'
    r_d7 = f'net_revenue_{d7_date.strftime("%b%d")}'

    # Fast Vectorized Deltas
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
    
    # Iterate through each warehouse group
    for feeder, group in pivot.groupby('feeder_wh', observed=True):
        group = group.copy()
        
        # Build subtotal dictionary
        subtotal_dict = {
            'feeder_wh': [feeder],
            'sku': [f"{feeder} Total"]
        }
        
        # Sum numeric columns
        for col in cols_to_keep:
            if col not in ['feeder_wh', 'sku']:
                subtotal_dict[col] = [group[col].sum()]
                
        subtotal = pd.DataFrame(subtotal_dict)

        # Recalculate Deltas for Subtotal
        if q_latest in subtotal.columns and q_d7 in subtotal.columns:
            subtotal['Units Delta'] = subtotal[q_latest] - subtotal[q_d7]
        else:
            subtotal['Units Delta'] = 0

        if r_latest in subtotal.columns and r_d7 in subtotal.columns:
            subtotal['Revenue Delta'] = subtotal[r_latest] - subtotal[r_d7]
            
            # Growth %
            prev = subtotal[r_d7].iloc[0]
            curr = subtotal[r_latest].iloc[0]
            subtotal['Growth %'] = 0 if prev == 0 else round(((curr - prev) / prev) * 100, 2)
        else:
            subtotal['Revenue Delta'] = 0
            subtotal['Growth %'] = 0

        group['Growth %'] = ""
        subtotal_rows.append(pd.concat([group, subtotal], ignore_index=True))

    final_df = pd.concat(subtotal_rows, ignore_index=True)

    # Convert quantities to int safely
    for col in final_df.columns:
        if "quantity" in col:
            final_df[col] = pd.to_numeric(final_df[col], errors='coerce').fillna(0).astype(int)

    # ================= Multi-level header formatting =================
    date_labels = {
        d7_date.strftime("%b%d"): d7_date.strftime("%B %d"),
        d1_date.strftime("%b%d"): d1_date.strftime("%B %d"),
        latest_date.strftime("%b%d"): latest_date.strftime("%B %d"),
    }

    # Construct MultiIndex
    new_cols = []
    for col in final_df.columns:
        if col == 'feeder_wh':
            new_cols.append(('Feeder WH', ''))
        elif col == 'sku':
            new_cols.append(('SKU', ''))
        elif 'quantity_' in col:
            d_part = col.replace('quantity_', '')
            new_cols.append((date_labels.get(d_part, d_part), 'Units'))
        elif 'net_revenue_' in col:
            d_part = col.replace('net_revenue_', '')
            new_cols.append((date_labels.get(d_part, d_part), 'Net Rev'))
        elif col == 'Units Delta':
            new_cols.append(('Delta', 'Units Delta'))
        elif col == 'Revenue Delta':
            new_cols.append(('Delta', 'Revenue Delta'))
        elif col == 'Growth %':
            new_cols.append(('Delta', 'Growth %'))
        else:
            new_cols.append(('Other', col))

    final_df.columns = pd.MultiIndex.from_tuples(new_cols)

    # ================= 🎨 STYLING: Highlight "Total" Rows =================
    
    def highlight_totals(row):
        """
        Highlights rows where the SKU column contains 'Total'.
        """
        # We access the MultiIndex column for SKU using the tuple ('SKU', '')
        sku_val = str(row[('SKU', '')])
        
        if "Total" in sku_val:
            # ✨ Color: Light Yellow background + Bold Text
            return ['background-color: #ffffcc; font-weight: bold; color: #333333'] * len(row)
        else:
            return [''] * len(row)

    # Apply the style
    styled_df = final_df.style.apply(highlight_totals, axis=1)

    # Render the styled dataframe
    st.dataframe(styled_df, use_container_width=True, height=600)

    # ---------------------------------------------------------
    # FILTERS (Side-by-side — Product + Warehouse)
    # ---------------------------------------------------------

    st.markdown("### 🔍 Filters")

    col1, col2 = st.columns(2)

    # Fast unique values from Categories
    all_products = sorted(list(df['product'].unique()))
    all_warehouses = sorted(list(df['feeder_wh'].unique()))

    with col1:
        selected_product = st.selectbox("Select Product", ["All"] + all_products)

    with col2:
        selected_warehouse = st.selectbox("Select Warehouse", ["All"] + all_warehouses)

    # Apply filters (Fast Category Filtering)
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
    
    if last_30.empty:
        st.info("No data available for chart.")
        return

    daily_summary = last_30.groupby('date').agg({
        'quantity': 'sum',
        'net_revenue': 'sum'
    }).reset_index().sort_values('date')

    # ---------------------------------------------------------
    # BAR CHART
    # ---------------------------------------------------------

    fig = px.bar(
        daily_summary,
        x='date',
        y='quantity',
        hover_data={'net_revenue': True, 'quantity': True},
        labels={'quantity': 'Units Sold', 'date': 'Date'},
        title=f"Sales Trend: {selected_product if selected_product != 'All' else 'All Products'}"
    )

    fig.update_traces(text=daily_summary['quantity'], textposition='outside')

    fig.update_layout(
        height=450,
        xaxis_title="Date",
        yaxis_title="Units Sold",
        bargap=0.2
    )

    st.plotly_chart(fig, use_container_width=True)