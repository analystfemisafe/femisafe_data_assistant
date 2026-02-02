import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import text
import textwrap
from datetime import datetime, timedelta

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 🎨 COLOR LOGIC
# ---------------------------------------------------------
def color_growth(val):
    if pd.isna(val) or val == 0:
        return 'color: #333'
    
    bg = '#d4edda' if val > 0 else '#f8d7da' 
    text_color = '#155724' if val > 0 else '#721c24'
    
    return f'background-color: {bg}; color: {text_color}; font-weight: bold;'

# ---------------------------------------------------------
# 🚀 DATA LOADER
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def get_data():
    engine = get_db_engine()
    if not engine: return pd.DataFrame(), pd.DataFrame()

    try:
        with engine.connect() as conn:
            # 1. Fetch Ad Data
            ad_query = text("SELECT * FROM femisafe_blinkit_addata")
            df_ad = pd.read_sql(ad_query, conn)
            
            # 2. Fetch Sales Data
            sales_query = text("SELECT order_date, product, total_gross_bill_amount FROM femisafe_blinkit_salesdata")
            df_sales = pd.read_sql(sales_query, conn)
            
        return df_ad, df_sales

    except Exception as e:
        st.error(f"⚠️ Error fetching data: {e}")
        return pd.DataFrame(), pd.DataFrame()

def process_data(df_ad, df_sales, target_date):
    if df_ad.empty: st.warning("Ad Data is empty from DB"); return pd.DataFrame(), None, None
    if df_sales.empty: st.warning("Sales Data is empty from DB"); return pd.DataFrame(), None, None

    # ---------------------------------------------------------
    # 🧹 CLEANING AD DATA
    # ---------------------------------------------------------
    
    # Force convert dates
    df_ad['date'] = pd.to_datetime(df_ad['date'], dayfirst=True, errors='coerce')

    # Fix Metrics
    if 'estimated_budget_consumed' in df_ad.columns:
        df_ad['estimated_budget_consumed'] = pd.to_numeric(df_ad['estimated_budget_consumed'], errors='coerce').fillna(0)
    else:
        df_ad['estimated_budget_consumed'] = 0

    if 'direct_sales' in df_ad.columns:
        df_ad['direct_sales'] = pd.to_numeric(
            df_ad['direct_sales'].astype(str).str.replace(r'[₹,]', '', regex=True), 
            errors='coerce'
        ).fillna(0)
    else:
        df_ad['direct_sales'] = 0

    # Create Join Key
    if 'product_name' in df_ad.columns:
        df_ad['join_key'] = df_ad['product_name'].astype(str).str.strip().str.lower()
    else:
        df_ad['join_key'] = "unknown"

    # ---------------------------------------------------------
    # 🧹 CLEANING SALES DATA
    # ---------------------------------------------------------
    df_sales['gross_sales'] = pd.to_numeric(df_sales['total_gross_bill_amount'].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)
    
    # Force convert dates
    df_sales['order_date'] = pd.to_datetime(df_sales['order_date'], dayfirst=True, errors='coerce')
    
    if 'product' in df_sales.columns:
        df_sales['join_key'] = df_sales['product'].astype(str).str.strip().str.lower()
    else:
        df_sales['join_key'] = "unknown"

    # ---------------------------------------------------------
    # 📅 FILTERING
    # ---------------------------------------------------------
    curr_date_ts = pd.to_datetime(target_date)
    prev_date_ts = curr_date_ts - pd.Timedelta(days=1)
    
    # Add explicit date_col for grouping (Strings ensure exact matching)
    df_ad['date_col'] = df_ad['date'].dt.date.astype(str)
    df_sales['date_col'] = df_sales['order_date'].dt.date.astype(str)
    
    target_dates_str = [str(curr_date_ts.date()), str(prev_date_ts.date())]

    # Filter
    ad_filt = df_ad[df_ad['date_col'].isin(target_dates_str)].copy()
    sales_filt = df_sales[df_sales['date_col'].isin(target_dates_str)].copy()

    if ad_filt.empty and sales_filt.empty:
        return pd.DataFrame(), curr_date_ts, prev_date_ts

    # ---------------------------------------------------------
    # 🔗 AGGREGATION
    # ---------------------------------------------------------
    
    # Group Ads
    # We use explicit columns now, avoiding the complex groupby key issue
    ad_grp = ad_filt.groupby(['join_key', 'date_col'], as_index=False).agg({
        'estimated_budget_consumed': 'sum', 
        'direct_sales': 'sum',
        'product_name': 'first' 
    })

    # Group Sales
    sales_grp = sales_filt.groupby(['join_key', 'date_col'], as_index=False).agg({
        'gross_sales': 'sum',
        'product': 'first'
    })

    # ---------------------------------------------------------
    # 🔗 MERGE (Fix for KeyError: 'date_col')
    # ---------------------------------------------------------
    
    # Both DataFrames correspond exactly now: ['join_key', 'date_col', metrics...]
    merged = pd.merge(ad_grp, sales_grp, on=['join_key', 'date_col'], how='outer').fillna(0)

    # Coalesce Product Name
    merged['display_name'] = np.where(merged['product_name'] != 0, merged['product_name'], merged['product'])
    
    # ---------------------------------------------------------
    # 🔄 PIVOT
    # ---------------------------------------------------------
    pivot = merged.pivot_table(
        index='display_name', 
        columns='date_col', 
        values=['estimated_budget_consumed', 'direct_sales', 'gross_sales'], 
        aggfunc='sum'
    ).fillna(0)
    
    # Flatten Columns
    pivot.columns = [f"{col[0]}_{col[1]}" for col in pivot.columns]
    
    # Define Lookup Keys
    curr_key = str(curr_date_ts.date())
    prev_key = str(prev_date_ts.date())
    
    def get_col(metric, date_key):
        col_name = f"{metric}_{date_key}"
        return pivot[col_name] if col_name in pivot.columns else 0

    d1_spend = get_col('estimated_budget_consumed', prev_key)
    d1_ad_sales = get_col('direct_sales', prev_key)
    d1_gross_sales = get_col('gross_sales', prev_key)
    
    curr_spend = get_col('estimated_budget_consumed', curr_key)
    curr_ad_sales = get_col('direct_sales', curr_key)
    curr_gross_sales = get_col('gross_sales', curr_key)

    res = pd.DataFrame(index=pivot.index)
    
    # T-1 Stats
    res['D1_Ad_Spend'] = d1_spend
    res['D1_Ad_Sales'] = d1_ad_sales
    res['D1_Gross_Sales'] = d1_gross_sales
    res['D1_Direct_ROAS'] = np.where(d1_spend > 0, d1_ad_sales / d1_spend, 0)
    res['D1_ROAS'] = np.where(d1_spend > 0, d1_gross_sales / d1_spend, 0)

    # Current Stats
    res['Curr_Ad_Spend'] = curr_spend
    res['Curr_Ad_Sales'] = curr_ad_sales
    res['Curr_Gross_Sales'] = curr_gross_sales
    res['Curr_Direct_ROAS'] = np.where(curr_spend > 0, curr_ad_sales / curr_spend, 0)
    res['Curr_ROAS'] = np.where(curr_spend > 0, curr_gross_sales / curr_spend, 0)

    # Growth
    res['Growth_Gross_Sales'] = np.where(d1_gross_sales > 0, ((curr_gross_sales - d1_gross_sales) / d1_gross_sales) * 100, 0)
    res['Growth_Ad_Spend'] = np.where(d1_spend > 0, ((curr_spend - d1_spend) / d1_spend) * 100, 0)

    res = res.sort_values('Curr_Gross_Sales', ascending=False)

    # Grand Total
    if not res.empty:
        total_row = pd.DataFrame(index=['Grand Total'])
        for col in ['D1_Ad_Spend', 'D1_Ad_Sales', 'D1_Gross_Sales', 'Curr_Ad_Spend', 'Curr_Ad_Sales', 'Curr_Gross_Sales']:
            total_row[col] = res[col].sum()
            
        total_row['D1_Direct_ROAS'] = np.where(total_row['D1_Ad_Spend'] > 0, total_row['D1_Ad_Sales'] / total_row['D1_Ad_Spend'], 0)
        total_row['D1_ROAS'] = np.where(total_row['D1_Ad_Spend'] > 0, total_row['D1_Gross_Sales'] / total_row['D1_Ad_Spend'], 0)
        total_row['Curr_Direct_ROAS'] = np.where(total_row['Curr_Ad_Spend'] > 0, total_row['Curr_Ad_Sales'] / total_row['Curr_Ad_Spend'], 0)
        total_row['Curr_ROAS'] = np.where(total_row['Curr_Ad_Spend'] > 0, total_row['Curr_Gross_Sales'] / total_row['Curr_Ad_Spend'], 0)
        
        total_row['Growth_Gross_Sales'] = np.where(total_row['D1_Gross_Sales'] > 0, ((total_row['Curr_Gross_Sales'] - total_row['D1_Gross_Sales']) / total_row['D1_Gross_Sales']) * 100, 0)
        total_row['Growth_Ad_Spend'] = np.where(total_row['D1_Ad_Spend'] > 0, ((total_row['Curr_Ad_Spend'] - total_row['D1_Ad_Spend']) / total_row['D1_Ad_Spend']) * 100, 0)

        final_df = pd.concat([res, total_row])
    else:
        final_df = pd.DataFrame()
    
    return final_df, curr_date_ts, prev_date_ts

# ---------------------------------------------------------
# 📄 MAIN PAGE
# ---------------------------------------------------------
def page():
    st.markdown("### 📢 Blinkit Ad Spend & ROAS Report")

    # 1. Date Picker
    col1, col2 = st.columns([2, 5])
    with col1:
        default_date = datetime.now().date() - timedelta(days=1)
        selected_date = st.date_input("Select Report Date", value=default_date)

    # Load & Process
    df_ad, df_sales = get_data()
    
    # 🔍 TROUBLESHOOTING BOX (SAFE MODE)
    with st.expander("🔍 Debug Raw Data"):
        if not df_ad.empty:
            df_ad['date'] = pd.to_datetime(df_ad['date'], dayfirst=True, errors='coerce')
            check_date = pd.to_datetime(selected_date)
            mask = df_ad['date'].dt.normalize() == check_date
            rows = df_ad[mask]
            st.write(f"Found {len(rows)} Ad rows for {selected_date}")
            if len(rows) > 0:
                st.dataframe(rows.head(3))
            else:
                st.write("First 3 Rows of Raw Ad Data (Check Dates):")
                st.dataframe(df_ad.head(3))
        else:
            st.write("Ad DataFrame is Empty")

    final_df, curr_date, prev_date = process_data(df_ad, df_sales, selected_date)

    if final_df.empty:
        st.warning(f"⚠️ No data match found for **{selected_date}**.")
        return

    # Formatted Dates for Headers
    d1_label = prev_date.strftime('%B %d') 
    curr_label = curr_date.strftime('%B %d') 
    
    st.info(f"📊 Showing comparison: **{curr_label}** (Selected) vs **{d1_label}** (Previous Day)")

    # -----------------------------------------------------
    # 🏗️ BUILD MULTI-INDEX HEADER DATAFRAME
    # -----------------------------------------------------
    
    cols_ordered = [
        'D1_Ad_Spend', 'D1_Ad_Sales', 'D1_Gross_Sales', 'D1_Direct_ROAS', 'D1_ROAS',
        'Curr_Ad_Spend', 'Curr_Ad_Sales', 'Curr_Gross_Sales', 'Curr_Direct_ROAS', 'Curr_ROAS',
        'Growth_Gross_Sales', 'Growth_Ad_Spend'
    ]
    
    display_df = final_df[cols_ordered].copy()
    
    arrays = [
        [d1_label]*5 + [curr_label]*5 + ['Growth %']*2,
        ['Ad Spend', 'Ad Sales', 'Gross Sales', 'Direct ROAS', 'ROAS', 
         'Ad Spend', 'Ad Sales', 'Gross Sales', 'Direct ROAS', 'ROAS',
         'Gross Sales', 'Ad Spend']
    ]
    display_df.columns = pd.MultiIndex.from_arrays(arrays)

    # -----------------------------------------------------
    # 💅 STYLING
    # -----------------------------------------------------
    
    money_subset = [
        (d1_label, 'Ad Spend'), (d1_label, 'Ad Sales'), (d1_label, 'Gross Sales'),
        (curr_label, 'Ad Spend'), (curr_label, 'Ad Sales'), (curr_label, 'Gross Sales')
    ]
    
    float_subset = [
        (d1_label, 'Direct ROAS'), (d1_label, 'ROAS'),
        (curr_label, 'Direct ROAS'), (curr_label, 'ROAS')
    ]
    
    growth_subset = [
        ('Growth %', 'Gross Sales'), ('Growth %', 'Ad Spend')
    ]

    styler = display_df.style\
        .format("{:,.0f}", subset=money_subset)\
        .format("{:,.2f}", subset=float_subset)\
        .format("{:,.2f}%", subset=growth_subset)\
        .applymap(color_growth, subset=growth_subset)\
        .set_table_attributes('class="ad-table"')

    # -----------------------------------------------------
    # 🖌️ CUSTOM CSS (Light Theme)
    # -----------------------------------------------------
    css = textwrap.dedent("""
    <style>
        .ad-table {
            width: 100%;
            border-collapse: collapse;
            font-family: sans-serif;
            font-size: 13px;
            color: #000;
        }
        .ad-table th, .ad-table td {
            border: 1px solid #ccc;
            padding: 8px;
            text-align: right; 
        }
        .ad-table thead tr:nth-child(1) th {
            background-color: #ffffff;
            color: #000;
            text-align: center;
            font-weight: bold;
            font-size: 14px;
            border-bottom: 2px solid #000;
        }
        .ad-table thead tr:nth-child(2) th {
            background-color: #f8f9fa;
            color: #333;
            text-align: center;
            font-size: 12px;
            font-weight: bold;
        }
        .ad-table tbody tr {
            background-color: #ffffff !important;
            color: #000 !important;
        }
        .ad-table tbody tr th {
            text-align: left;
            background-color: #ffffff;
            font-weight: bold;
            color: #000;
            border-right: 2px solid #ccc;
        }
        .ad-table tbody tr:last-child {
            font-weight: bold;
            background-color: #f1f1f1 !important;
            border-top: 2px solid #000;
        }
        .ad-table td, .ad-table th {
            color: inherit;
        }
    </style>cvslnvfsnvm, blfsh
    """)

    st.markdown(css, unsafe_allow_html=True)
    st.markdown(styler.to_html(), unsafe_allow_html=True)