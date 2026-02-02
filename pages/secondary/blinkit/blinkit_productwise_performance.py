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
        
        # --- CLEANING & OPTIMIZATION ---
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

    st.markdown("### 📦 Product-wise Sales Report (Blinkit)")

    # 1. Load Data
    df = get_blinkit_data()
    if df.empty:
        st.warning("No data available.")
        return

    # 2. Date Filtering (Latest, D-1, D-7)
    latest_date = df['date'].max()
    d1_date = latest_date - timedelta(days=1)
    d7_date = latest_date - timedelta(days=7)

    df_filtered = df[df['date'].isin([d7_date, d1_date, latest_date])]
    
    if df_filtered.empty:
        st.warning(f"No data found for {latest_date}.")
        return

    # 3. Aggregate: Group by PRODUCT first, then Feeder WH
    grouped = df_filtered.groupby(['product', 'feeder_wh', 'date'], observed=True).agg({
        'net_revenue': 'sum',
        'quantity': 'sum'
    }).reset_index()

    # 4. Pivot
    pivot = grouped.pivot_table(
        index=['product', 'feeder_wh'],  
        columns='date',
        values=['net_revenue', 'quantity'],
        fill_value=0
    ).reset_index()

    # 5. Flatten Columns
    pivot.columns = [
        f"{i}_{j.strftime('%b%d')}" if j != '' else i
        for i, j in pivot.columns
    ]

    # 6. Reorder Columns
    cols_to_keep = ['product', 'feeder_wh']
    date_suffixes = [d7_date, d1_date, latest_date]
    
    for d in date_suffixes:
        q_col = f'quantity_{d.strftime("%b%d")}'
        r_col = f'net_revenue_{d.strftime("%b%d")}'
        if q_col in pivot.columns: cols_to_keep.append(q_col)
        if r_col in pivot.columns: cols_to_keep.append(r_col)
            
    pivot = pivot[cols_to_keep]

    # 7. Identify Dynamic Column Names for Deltas
    q_latest = f'quantity_{latest_date.strftime("%b%d")}'
    q_d7 = f'quantity_{d7_date.strftime("%b%d")}'
    r_latest = f'net_revenue_{latest_date.strftime("%b%d")}'
    r_d7 = f'net_revenue_{d7_date.strftime("%b%d")}'

    # 8. Subtotal Logic (Iterate by PRODUCT now)
    subtotal_rows = []
    
    for product_name, group in pivot.groupby('product', observed=True):
        if group.empty: continue
        group = group.copy()
        
        # Build subtotal row
        subtotal_dict = {
            'product': [product_name],
            'feeder_wh': ["All Cities Total"] 
        }
        
        # Sum numeric columns
        for col in cols_to_keep:
            if col not in ['product', 'feeder_wh']:
                subtotal_dict[col] = [group[col].sum()]
                
        subtotal = pd.DataFrame(subtotal_dict)

        # Calculate Deltas for Subtotal
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

        # Calculate Deltas for Individual Rows
        if q_latest in group.columns and q_d7 in group.columns:
            group['Units Delta'] = group[q_latest] - group[q_d7]
        else:
            group['Units Delta'] = 0
            
        if r_latest in group.columns and r_d7 in group.columns:
            group['Revenue Delta'] = group[r_latest] - group[r_d7]
        else:
            group['Revenue Delta'] = 0
            
        group['Growth %'] = "" 

        # Append
        subtotal_rows.append(pd.concat([group, subtotal], ignore_index=True))

    final_df = pd.concat(subtotal_rows, ignore_index=True)

    # ---------------------------------------------------------
    # 🧹 CLEANUP: Show Product Name Only Once per Group
    # ---------------------------------------------------------
    # Ensure it is string type
    final_df['product'] = final_df['product'].astype(str)
    
    # Create mask: True if current product name is same as previous AND not "All Cities Total"
    # Note: "All Cities Total" is in 'feeder_wh' column, but we check product grouping here.
    # We want the product name to show on the first row of the group.
    
    # Logic: If 'product' matches previous row's 'product', replace with empty string.
    mask = final_df['product'] == final_df['product'].shift()
    final_df.loc[mask, 'product'] = ''

    # 9. Clean Numeric Types
    for col in final_df.columns:
        if "quantity" in col:
            final_df[col] = pd.to_numeric(final_df[col], errors='coerce').fillna(0).astype(int)

    # 10. Multi-Level Headers
    date_labels = {
        d7_date.strftime("%b%d"): d7_date.strftime("%B %d"),
        d1_date.strftime("%b%d"): d1_date.strftime("%B %d"),
        latest_date.strftime("%b%d"): latest_date.strftime("%B %d"),
    }

    new_cols = []
    for col in final_df.columns:
        if col == 'product':
            new_cols.append(('Product', ''))
        elif col == 'feeder_wh':
            new_cols.append(('City / Warehouse', ''))
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

    # ================= 🎨 STYLING (High Contrast Dark Theme) =================
    
    def apply_styles(row):
        wh_val = str(row[('City / Warehouse', '')])
        
        # 1. Total Rows: Medium Blue-Grey with Black Text (Matches City Report)
        if "Total" in wh_val:
            return ['background-color: #B0BEC5; color: #000000; font-weight: bold; border-top: 1px solid #78909C;'] * len(row)
        
        # 2. Normal Row: White
        else:
            return ['background-color: #ffffff; color: #000;'] * len(row)

    styler = final_df.style.apply(apply_styles, axis=1)
    
    # Format Numbers
    styler.format(precision=0, na_rep="0")
    
    # Add CSS Class
    styler.set_table_attributes('class="static-table"')

    # CSS for Professional Table (Identical to City Report)
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
    # 📊 CHARTS SECTION
    # ---------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📈 Trends")

    col1, col2 = st.columns(2)
    all_products = sorted(list(df['product'].unique()))
    with col1:
        selected_prod_chart = st.selectbox("Select Product to View Trend", all_products)
    
    chart_df = df[df['product'] == selected_prod_chart].copy()
    
    daily_trend = chart_df.groupby('date').agg({
        'quantity': 'sum', 
        'net_revenue': 'sum'
    }).reset_index().sort_values('date')

    fig = px.bar(
        daily_trend, 
        x='date', 
        y='quantity',
        title=f"Daily Sales Trend: {selected_prod_chart}",
        labels={'quantity': 'Units Sold', 'date': 'Date'},
        hover_data=['net_revenue']
    )
    fig.update_traces(text=daily_trend['quantity'], textposition='outside')
    fig.update_layout(height=450, xaxis_title="Date", yaxis_title="Units Sold", bargap=0.2)
    
    st.plotly_chart(fig, use_container_width=True)