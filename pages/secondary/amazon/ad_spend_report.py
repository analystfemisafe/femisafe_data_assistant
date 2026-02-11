import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import textwrap
from datetime import timedelta, datetime
from sqlalchemy import text

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

def color_growth(val):
    if pd.isna(val) or val == 0: return 'color: #333'
    bg = '#d4edda' if val > 0 else '#f8d7da' 
    text_color = '#155724' if val > 0 else '#721c24'
    return f'background-color: {bg}; color: {text_color}; font-weight: bold;'

# ---------------------------------------------------------
# 🚀 SMART DATA LOADER (Prevents Crashes & Saves Data)
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_amazon_data():
    engine = get_db_engine()
    if not engine: return pd.DataFrame(), pd.DataFrame()

    try:
        with engine.connect() as conn:
            # 1. Fetch Sales
            sales = pd.read_sql(text("SELECT date, product, net_revenue FROM femisafe_amazon_salesdata"), conn)
            
            # 2. Fetch Ads (Smart Column Detection)
            # Check available columns first without downloading data
            cols = pd.read_sql(text("SELECT * FROM femisafe_amazon_addata LIMIT 1"), conn).columns.tolist()
            cols_lower = {c.lower().strip(): c for c in cols}

            # Map to correct names
            c_date = next((orig for low, orig in cols_lower.items() if 'date' in low), 'date')
            c_prod = next((orig for low, orig in cols_lower.items() if 'product' in low), 'product')
            c_spend = next((orig for low, orig in cols_lower.items() if 'spend' in low or 'cost' in low), None)
            
            # Find tricky sales column
            c_sales = next((orig for low, orig in cols_lower.items() if '7 day' in low and 'sales' in low), None)
            if not c_sales:
                c_sales = next((orig for low, orig in cols_lower.items() if 'ordered' in low and 'sales' in low), None)

            # Build Safe Query
            query_parts = [f'"{c_date}" as date', f'"{c_prod}" as product']
            query_parts.append(f'"{c_spend}" as spend_inr' if c_spend else '0 as spend_inr')
            query_parts.append(f'"{c_sales}" as ad_sales' if c_sales else '0 as ad_sales')
            
            ads = pd.read_sql(text(f"SELECT {', '.join(query_parts)} FROM femisafe_amazon_addata"), conn)

        # Cleaning
        if not sales.empty:
            sales['net_revenue'] = pd.to_numeric(sales['net_revenue'].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)
            sales['date'] = pd.to_datetime(sales['date'], dayfirst=True, errors='coerce')
            sales.dropna(subset=['date'], inplace=True)

        if not ads.empty:
            ads['spend_inr'] = pd.to_numeric(ads['spend_inr'].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)
            ads['ad_sales'] = pd.to_numeric(ads['ad_sales'].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)
            ads['date'] = pd.to_datetime(ads['date'], dayfirst=True, errors='coerce')
            ads.dropna(subset=['date'], inplace=True)

        return sales, ads
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

# ---------------------------------------------------------
# 🧮 PROCESSOR & UI
# ---------------------------------------------------------
def process_table_data(df_sales, df_ads, target_date):
    if df_sales.empty and df_ads.empty: return pd.DataFrame(), None, None
    curr_date_ts = pd.to_datetime(target_date)
    prev_date_ts = curr_date_ts - timedelta(days=1)
    
    target_dates = [curr_date_ts, prev_date_ts]
    sales_filt = df_sales[df_sales['date'].isin(target_dates)].copy()
    ads_filt = df_ads[df_ads['date'].isin(target_dates)].copy()

    sales_filt['date_str'] = sales_filt['date'].dt.date.astype(str)
    ads_filt['date_str'] = ads_filt['date'].dt.date.astype(str)

    sales_grp = sales_filt.groupby(['product', 'date_str'], as_index=False)['net_revenue'].sum()
    ads_grp = ads_filt.groupby(['product', 'date_str'], as_index=False)[['spend_inr', 'ad_sales']].sum()

    merged = pd.merge(ads_grp, sales_grp, on=['product', 'date_str'], how='outer').fillna(0)
    if merged.empty: return pd.DataFrame(), curr_date_ts, prev_date_ts

    pivot = merged.pivot_table(index='product', columns='date_str', values=['spend_inr', 'ad_sales', 'net_revenue'], aggfunc='sum').fillna(0)
    pivot.columns = [f"{col[0]}_{col[1]}" for col in pivot.columns]

    curr_key = str(curr_date_ts.date())
    prev_key = str(prev_date_ts.date())

    def get_col(metric, date_key):
        col_name = f"{metric}_{date_key}"
        return pivot[col_name] if col_name in pivot.columns else 0

    res = pd.DataFrame(index=pivot.index)
    res['D1_Ad_Spend'] = get_col('spend_inr', prev_key)
    res['D1_Ad_Sales'] = get_col('ad_sales', prev_key)
    res['D1_Gross_Sales'] = get_col('net_revenue', prev_key)
    res['Curr_Ad_Spend'] = get_col('spend_inr', curr_key)
    res['Curr_Ad_Sales'] = get_col('ad_sales', curr_key)
    res['Curr_Gross_Sales'] = get_col('net_revenue', curr_key)
    
    # Calculations
    res['D1_Direct_ROAS'] = np.where(res['D1_Ad_Spend'] > 0, res['D1_Ad_Sales'] / res['D1_Ad_Spend'], 0)
    res['Curr_Direct_ROAS'] = np.where(res['Curr_Ad_Spend'] > 0, res['Curr_Ad_Sales'] / res['Curr_Ad_Spend'], 0)
    res['Growth_Gross_Sales'] = np.where(res['D1_Gross_Sales'] > 0, ((res['Curr_Gross_Sales'] - res['D1_Gross_Sales']) / res['D1_Gross_Sales']) * 100, 0)
    res['Growth_Ad_Spend'] = np.where(res['D1_Ad_Spend'] > 0, ((res['Curr_Ad_Spend'] - res['D1_Ad_Spend']) / res['D1_Ad_Spend']) * 100, 0)

    if not res.empty:
        total = res.sum(numeric_only=True)
        total['D1_Direct_ROAS'] = total['D1_Ad_Sales'] / total['D1_Ad_Spend'] if total['D1_Ad_Spend'] > 0 else 0
        total['Curr_Direct_ROAS'] = total['Curr_Ad_Sales'] / total['Curr_Ad_Spend'] if total['Curr_Ad_Spend'] > 0 else 0
        total_row = pd.DataFrame(total).T
        total_row.index = ['Grand Total']
        res = pd.concat([res, total_row])

    return res, curr_date_ts, prev_date_ts

def page():
    st.markdown("### 📊 Amazon Ad Spend & Sales Report")
    sales, ads = get_amazon_data()

    if sales.empty and ads.empty:
        st.warning("No data available.")
        return

    # Chart
    with st.expander("📈 View Sales vs Ads Chart", expanded=True):
        col1, col2 = st.columns(2)
        with col2: range_lbl = st.selectbox("Range", ["Last 7 Days", "Last 14 Days", "Last 30 Days"])
        days = {"Last 7 Days": 7, "Last 14 Days": 14, "Last 30 Days": 30}
        
        max_date = sales['date'].max() if not sales.empty else pd.Timestamp.now()
        start_date = max_date - timedelta(days=days[range_lbl])
        
        s_c = sales[(sales['date'] >= start_date)].groupby('date')['net_revenue'].sum().reset_index()
        a_c = ads[(ads['date'] >= start_date)].groupby('date')['spend_inr'].sum().reset_index()
        merged = pd.merge(s_c, a_c, on='date', how='outer').fillna(0).sort_values('date')
        
        fig = px.bar(merged.melt('date'), x='date', y='value', color='variable', barmode='group', title="Daily Trends")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    
    # Table
    st.subheader("📋 Performance Report")
    report_date = st.date_input("Select Report Date", value=datetime.now().date() - timedelta(days=1))
    final_df, _, _ = process_table_data(sales, ads, report_date)

    if not final_df.empty:
        cols = ['D1_Ad_Spend', 'D1_Ad_Sales', 'D1_Gross_Sales', 'D1_Direct_ROAS', 'Curr_Ad_Spend', 'Curr_Ad_Sales', 'Curr_Gross_Sales', 'Curr_Direct_ROAS', 'Growth_Gross_Sales', 'Growth_Ad_Spend']
        st.dataframe(final_df[cols].style.format("{:,.2f}").applymap(color_growth, subset=['Growth_Gross_Sales', 'Growth_Ad_Spend']))