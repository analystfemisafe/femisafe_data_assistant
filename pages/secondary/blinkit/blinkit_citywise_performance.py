import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta
from sqlalchemy import text
import textwrap

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine(): return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 🚀 OPTIMIZED DATA LOADER
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def get_blinkit_data():
    engine = get_db_engine()
    if not engine: return pd.DataFrame()

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
                WHERE order_status NOT IN ('Cancelled', 'Returned')
            """)
            df = pd.read_sql(query, conn)
        
        if df.empty: return df
        
        for col in ['net_revenue', 'quantity']:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r'[₹,]', '', regex=True), 
                errors='coerce'
            ).fillna(0)

        df['quantity'] = df['quantity'].astype('int32')
        df['feeder_wh'] = df['feeder_wh'].fillna("Unknown").astype(str).str.title().astype('category')
        df['product'] = df['product'].astype('category')
        df['sku'] = df['sku'].astype('category')
        
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

    df = get_blinkit_data()

    if df.empty:
        st.warning("No data available.")
        return

    latest_date = df['date'].max()
    d1_date = latest_date - timedelta(days=1)
    d7_date = latest_date - timedelta(days=7)

    df_filtered = df[df['date'].isin([d7_date, d1_date, latest_date])]
    
    if df_filtered.empty:
        st.warning(f"No data found for {latest_date}, {d1_date}, or {d7_date}.")
        return

    grouped = df_filtered.groupby(['feeder_wh', 'sku', 'date'], observed=True).agg({
        'net_revenue': 'sum',
        'quantity': 'sum'
    }).reset_index()

    pivot = grouped.pivot_table(
        index=['feeder_wh', 'sku'],
        columns='date',
        values=['net_revenue', 'quantity'],
        fill_value=0
    ).reset_index()

    pivot.columns = [
        f"{i}_{j.strftime('%b%d')}" if j != '' else i
        for i, j in pivot.columns
    ]

    cols_to_keep = ['feeder_wh', 'sku']
    date_suffixes = [d7_date, d1_date, latest_date]
    
    for d in date_suffixes:
        q_col = f'quantity_{d.strftime("%b%d")}'
        r_col = f'net_revenue_{d.strftime("%b%d")}'
        if q_col in pivot.columns: cols_to_keep.append(q_col)
        if r_col in pivot.columns: cols_to_keep.append(r_col)
            
    pivot = pivot[cols_to_keep]

    q_latest = f'quantity_{latest_date.strftime("%b%d")}'
    q_d7 = f'quantity_{d7_date.strftime("%b%d")}'
    r_latest = f'net_revenue_{latest_date.strftime("%b%d")}'
    r_d7 = f'net_revenue_{d7_date.strftime("%b%d")}'

    if q_latest in pivot.columns and q_d7 in pivot.columns:
        pivot['Units Delta'] = pivot[q_latest] - pivot[q_d7]
    else: pivot['Units Delta'] = 0
        
    if r_latest in pivot.columns and r_d7 in pivot.columns:
        pivot['Revenue Delta'] = pivot[r_latest] - pivot[r_d7]
    else: pivot['Revenue Delta'] = 0

    # Subtotals
    subtotal_rows = []
    for feeder, group in pivot.groupby('feeder_wh', observed=True):
        group = group.copy()
        subtotal_dict = {'feeder_wh': [feeder], 'sku': [f"{feeder} Total"]}
        for col in cols_to_keep:
            if col not in ['feeder_wh', 'sku']:
                subtotal_dict[col] = [group[col].sum()]
        subtotal = pd.DataFrame(subtotal_dict)

        if q_latest in subtotal.columns and q_d7 in subtotal.columns:
            subtotal['Units Delta'] = subtotal[q_latest] - subtotal[q_d7]
        else: subtotal['Units Delta'] = 0

        if r_latest in subtotal.columns and r_d7 in subtotal.columns:
            subtotal['Revenue Delta'] = subtotal[r_latest] - subtotal[r_d7]
            prev = subtotal[r_d7].iloc[0]
            curr = subtotal[r_latest].iloc[0]
            subtotal['Growth %'] = 0 if prev == 0 else round(((curr - prev) / prev) * 100, 2)
        else:
            subtotal['Revenue Delta'] = 0
            subtotal['Growth %'] = 0

        group['Growth %'] = ""
        subtotal_rows.append(pd.concat([group, subtotal], ignore_index=True))

    final_df = pd.concat(subtotal_rows, ignore_index=True)

    # Grand Total
    grand_total_dict = {'feeder_wh': ['Grand Total'], 'sku': ['']}
    for col in cols_to_keep:
        if col not in ['feeder_wh', 'sku']:
            grand_total_dict[col] = [pivot[col].sum()]
    grand_total = pd.DataFrame(grand_total_dict)

    if q_latest in grand_total.columns and q_d7 in grand_total.columns:
        grand_total['Units Delta'] = grand_total[q_latest] - grand_total[q_d7]
    else: grand_total['Units Delta'] = 0

    if r_latest in grand_total.columns and r_d7 in grand_total.columns:
        grand_total['Revenue Delta'] = grand_total[r_latest] - grand_total[r_d7]
        prev = grand_total[r_d7].iloc[0]
        curr = grand_total[r_latest].iloc[0]
        grand_total['Growth %'] = 0 if prev == 0 else round(((curr - prev) / prev) * 100, 2)
    else:
        grand_total['Revenue Delta'] = 0
        grand_total['Growth %'] = 0

    final_df = pd.concat([final_df, grand_total], ignore_index=True)

    # Hide duplicate names (except Grand Total)
    final_df['feeder_wh'] = final_df['feeder_wh'].astype(str)
    mask = (final_df['feeder_wh'] == final_df['feeder_wh'].shift()) & (final_df['feeder_wh'] != 'Grand Total')
    final_df.loc[mask, 'feeder_wh'] = ''

    # Clean numbers
    for col in final_df.columns:
        if "quantity" in col:
            final_df[col] = pd.to_numeric(final_df[col], errors='coerce').fillna(0).astype(int)

    # Header Mapping
    date_labels = {
        d7_date.strftime("%b%d"): d7_date.strftime("%B %d"),
        d1_date.strftime("%b%d"): d1_date.strftime("%B %d"),
        latest_date.strftime("%b%d"): latest_date.strftime("%B %d"),
    }

    new_cols = []
    for col in final_df.columns:
        if col == 'feeder_wh': new_cols.append(('Feeder WH', ''))
        elif col == 'sku': new_cols.append(('SKU', ''))
        elif 'quantity_' in col:
            d_part = col.replace('quantity_', '')
            new_cols.append((date_labels.get(d_part, d_part), 'Units'))
        elif 'net_revenue_' in col:
            d_part = col.replace('net_revenue_', '')
            new_cols.append((date_labels.get(d_part, d_part), 'Net Rev'))
        elif col == 'Units Delta': new_cols.append(('Delta', 'Units Delta'))
        elif col == 'Revenue Delta': new_cols.append(('Delta', 'Revenue Delta'))
        elif col == 'Growth %': new_cols.append(('Delta', 'Growth %'))
        else: new_cols.append(('Other', col))

    final_df.columns = pd.MultiIndex.from_tuples(new_cols)

    # ================= 🎨 DARKER TOTAL SHADES =================
    
    def apply_styles(row):
        wh_val = str(row[('Feeder WH', '')])
        sku_val = str(row[('SKU', '')])
        
        # 1. Grand Total: Dark Slate Blue with White Text (High Contrast)
        if wh_val == 'Grand Total':
            return ['background-color: #37474F; color: #ffffff; font-weight: bold; border-top: 2px solid #000;'] * len(row)
        
        # 2. Subtotal: Medium Blue-Grey with Black Text (Distinct from Data)
        elif "Total" in sku_val:
            return ['background-color: #B0BEC5; color: #000000; font-weight: bold; border-top: 1px solid #78909C;'] * len(row)
        
        # 3. Normal Row: White
        else:
            return ['background-color: #ffffff; color: #000;'] * len(row)

    styler = final_df.style.apply(apply_styles, axis=1)
    styler.format(precision=0, na_rep="0")
    styler.set_table_attributes('class="static-table"')

    # CSS for Professional Table
    css = textwrap.dedent("""
    <style>
        .table-container {
            max_height: 650px;
            overflow-y: auto;
            border: 1px solid #ddd;
        }
        .static-table {
            width: 100%;
            border-collapse: collapse;
            font-family: sans-serif;
            font-size: 13px;
        }
        /* HEADER 1 */
        .static-table thead tr:nth-child(1) th {
            position: sticky;
            top: 0;
            background-color: #f8f9fa;
            color: #000;
            font-weight: bold;
            padding: 10px;
            text-align: center;
            border: 1px solid #ccc;
            z-index: 2;
        }
        /* HEADER 2 */
        .static-table thead tr:nth-child(2) th {
            position: sticky;
            top: 40px;
            background-color: #e9ecef;
            color: #333;
            font-size: 12px;
            padding: 6px;
            border: 1px solid #ccc;
            z-index: 2;
        }
        .static-table td {
            padding: 8px;
            border: 1px solid #eee;
            text-align: right;
            color: #000;
        }
        .static-table td:nth-child(1), .static-table td:nth-child(2) {
            text-align: left;
        }
    </style>
    """)
    
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(f'<div class="table-container">{styler.to_html()}</div>', unsafe_allow_html=True)

    # ---------------------------------------------------------
    # Filters & Chart
    # ---------------------------------------------------------
    st.markdown("### 🔍 Filters")
    col1, col2 = st.columns(2)
    all_products = sorted(list(df['product'].unique()))
    all_warehouses = sorted(list(df['feeder_wh'].unique()))
    with col1: selected_product = st.selectbox("Select Product", ["All"] + all_products)
    with col2: selected_warehouse = st.selectbox("Select Warehouse", ["All"] + all_warehouses)

    filtered = df.copy()
    if selected_product != "All": filtered = filtered[filtered['product'] == selected_product]
    if selected_warehouse != "All": filtered = filtered[filtered['feeder_wh'] == selected_warehouse]

    filtered['date'] = filtered['order_date'].dt.date
    start_date = latest_date - timedelta(days=30)
    last_30 = filtered[filtered['date'] >= start_date]
    
    if last_30.empty:
        st.info("No data available for chart.")
        return

    daily_summary = last_30.groupby('date').agg({'quantity': 'sum', 'net_revenue': 'sum'}).reset_index().sort_values('date')

    fig = px.bar(
        daily_summary, x='date', y='quantity',
        hover_data={'net_revenue': True, 'quantity': True},
        labels={'quantity': 'Units Sold', 'date': 'Date'},
        title=f"Sales Trend: {selected_product if selected_product != 'All' else 'All Products'}"
    )
    fig.update_traces(text=daily_summary['quantity'], textposition='outside')
    fig.update_layout(height=450, xaxis_title="Date", yaxis_title="Units Sold", bargap=0.2)
    st.plotly_chart(fig, use_container_width=True)