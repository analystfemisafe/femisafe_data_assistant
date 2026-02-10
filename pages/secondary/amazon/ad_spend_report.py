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
# 🚀 SAFE DATA LOADER (No UI elements inside!)
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def get_amazon_data():
    engine = get_db_engine()
    if not engine: return pd.DataFrame(), pd.DataFrame()

    try:
        with engine.connect() as conn:
            # 1. Fetch Sales Data
            sales = pd.read_sql(text("SELECT * FROM femisafe_amazon_salesdata"), conn)
            
            # 2. Fetch Ads Data
            ads = pd.read_sql(text("SELECT * FROM femisafe_amazon_addata"), conn)

        # =========================================================
        # ⚡ CLEANING
        # =========================================================
        
        # --- Clean Sales ---
        if not sales.empty:
            sales.columns = [c.lower().strip() for c in sales.columns] # Standardize headers
            
            if 'net_revenue' in sales.columns:
                sales['net_revenue'] = pd.to_numeric(sales['net_revenue'].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)
            
            if 'units_sold' in sales.columns:
                sales['units_sold'] = pd.to_numeric(sales['units_sold'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype('int32')
            
            # Find date column
            date_col = next((c for c in sales.columns if 'date' in c), None)
            if date_col:
                sales['date'] = pd.to_datetime(sales[date_col], dayfirst=True, errors='coerce')
                sales.dropna(subset=['date'], inplace=True)
                sales['product'] = sales['product'].fillna("Unknown").astype(str).str.strip()

        # --- Clean Ads ---
        if not ads.empty:
            ads.columns = [c.lower().strip() for c in ads.columns] # Standardize headers
            
            # 1. FIND SPEND COLUMN
            spend_col = next((c for c in ads.columns if 'spend' in c or 'cost' in c), None)
            if spend_col:
                 ads['spend_inr'] = pd.to_numeric(ads[spend_col].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)
            else:
                 ads['spend_inr'] = 0

            # 2. FIND SALES COLUMN (We do this dynamically now)
            # We look for ANY column that might be sales
            ad_sales_col = next((c for c in ads.columns if '7 day' in c and 'sales' in c), None) # Priority 1
            if not ad_sales_col:
                ad_sales_col = next((c for c in ads.columns if 'ordered' in c and 'sales' in c), None) # Priority 2
            
            if ad_sales_col:
                ads['ad_sales'] = pd.to_numeric(ads[ad_sales_col].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)
            else:
                ads['ad_sales'] = 0 

            # Date cleaning
            date_col = next((c for c in ads.columns if 'date' in c), None)
            if date_col:
                ads['date'] = pd.to_datetime(ads[date_col], dayfirst=True, errors='coerce')
                ads.dropna(subset=['date'], inplace=True)
                ads['product'] = ads['product'].fillna("Unknown").astype(str).str.strip()

        return sales, ads

    except Exception as e:
        # We can't print error here inside cache, so we return empty DFs
        return pd.DataFrame(), pd.DataFrame()

# ---------------------------------------------------------
# 🧮 PROCESSOR
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

    d1_spend = get_col('spend_inr', prev_key)
    d1_ad_sales = get_col('ad_sales', prev_key)
    d1_gross_sales = get_col('net_revenue', prev_key)
    curr_spend = get_col('spend_inr', curr_key)
    curr_ad_sales = get_col('ad_sales', curr_key)
    curr_gross_sales = get_col('net_revenue', curr_key)

    res = pd.DataFrame(index=pivot.index)
    res['D1_Ad_Spend'] = d1_spend
    res['D1_Ad_Sales'] = d1_ad_sales
    res['D1_Gross_Sales'] = d1_gross_sales
    res['D1_Direct_ROAS'] = np.where(d1_spend > 0, d1_ad_sales / d1_spend, 0)
    res['D1_ROAS'] = np.where(d1_spend > 0, d1_gross_sales / d1_spend, 0)
    res['Curr_Ad_Spend'] = curr_spend
    res['Curr_Ad_Sales'] = curr_ad_sales
    res['Curr_Gross_Sales'] = curr_gross_sales
    res['Curr_Direct_ROAS'] = np.where(curr_spend > 0, curr_ad_sales / curr_spend, 0)
    res['Curr_ROAS'] = np.where(curr_spend > 0, curr_gross_sales / curr_spend, 0)
    res['Growth_Gross_Sales'] = np.where(d1_gross_sales > 0, ((curr_gross_sales - d1_gross_sales) / d1_gross_sales) * 100, 0)
    res['Growth_Ad_Spend'] = np.where(d1_spend > 0, ((curr_spend - d1_spend) / d1_spend) * 100, 0)
    res = res.sort_values('Curr_Gross_Sales', ascending=False)

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
        res = pd.concat([res, total_row])

    return res, curr_date_ts, prev_date_ts

# ---------------------------------------------------------
# PAGE
# ---------------------------------------------------------
def page():

    st.markdown("### 📊 Amazon Ad Spend & Sales Report")

    # Load Data
    sales, ads = get_amazon_data()

    if sales.empty and ads.empty:
        st.warning("No data available.")
        return

    # -----------------------------------------------------
    # 🕵️‍♂️ DEBUGGER: SHOW ME THE COLUMNS! (SAFE PLACE)
    # -----------------------------------------------------
    with st.expander("🐞 DATABASE INSPECTOR (Click to find Missing Columns)", expanded=True):
        st.write("### 1. Actual Columns in your Amazon Ads Table:")
        st.code(list(ads.columns)) 
        st.caption("Look for something like '7 day total sales', 'attributed sales', or just 'sales' in the list above.")

    # ... (Rest of your UI code for Chart and Table goes here, same as before) ...
    
    # Chart Section
    with st.expander("📈 View Sales vs Ads Chart", expanded=True):
        col1, col2 = st.columns(2)
        with col2:
            range_label = st.selectbox("Chart Range", ["Last 7 Days", "Last 14 Days", "Last 30 Days"], key="chart_range")
        with col1:
            all_products = sorted(list(set(sales['product'].unique()) | set(ads['product'].unique())))
            chart_product = st.selectbox("Chart Product", ["All"] + all_products, key="chart_prod")

        days_map = {"Last 7 Days": 7, "Last 14 Days": 14, "Last 30 Days": 30}
        max_date = max(sales["date"].max(), ads["date"].max()) if not sales.empty else pd.Timestamp.now()
        start_date = max_date - timedelta(days=days_map[range_label])

        s_chart = sales[(sales['date'] >= start_date) & (sales['date'] <= max_date)]
        a_chart = ads[(ads['date'] >= start_date) & (ads['date'] <= max_date)]

        if chart_product != "All":
            s_chart = s_chart[s_chart['product'] == chart_product]
            a_chart = a_chart[a_chart['product'] == chart_product]

        s_agg = s_chart.groupby("date", as_index=False)['net_revenue'].sum().rename(columns={'net_revenue': 'Sales'})
        a_agg = a_chart.groupby("date", as_index=False)['spend_inr'].sum().rename(columns={'spend_inr': 'Ads'})

        chart_merged = pd.merge(s_agg, a_agg, on='date', how='outer').fillna(0).sort_values('date')
        
        if not chart_merged.empty:
            chart_melt = chart_merged.melt(id_vars='date', var_name='Metric', value_name='Amount')
            fig = px.bar(chart_melt, x='date', y='Amount', color='Metric', barmode='group', color_discrete_map={"Sales": "#2ca02c", "Ads": "#d62728"}, title=f"Daily Trends ({range_label})")
            fig.update_layout(height=400, xaxis_title="Date", yaxis_title="Amount (₹)")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Table Section
    st.subheader("📋 Detailed Performance Report (T vs T-1)")
    col_date, _ = st.columns([2, 5])
    with col_date:
        default_date = datetime.now().date() - timedelta(days=1)
        report_date = st.date_input("Select Report Date", value=default_date)

    final_df, curr_ts, prev_ts = process_table_data(sales, ads, report_date)

    if final_df.empty:
        st.warning(f"No data found for {report_date}")
        return

    d1_label = prev_ts.strftime('%B %d') 
    curr_label = curr_ts.strftime('%B %d') 
    st.info(f"Comparing: **{curr_label}** (Selected) vs **{d1_label}** (Previous Day)")

    cols_ordered = ['D1_Ad_Spend', 'D1_Ad_Sales', 'D1_Gross_Sales', 'D1_Direct_ROAS', 'D1_ROAS', 'Curr_Ad_Spend', 'Curr_Ad_Sales', 'Curr_Gross_Sales', 'Curr_Direct_ROAS', 'Curr_ROAS', 'Growth_Gross_Sales', 'Growth_Ad_Spend']
    display_df = final_df[cols_ordered].copy()
    arrays = [[d1_label]*5 + [curr_label]*5 + ['Growth %']*2, ['Ad Spend', 'Ad Sales', 'Gross Sales', 'Direct ROAS', 'Total ROAS', 'Ad Spend', 'Ad Sales', 'Gross Sales', 'Direct ROAS', 'Total ROAS', 'Gross Sales', 'Ad Spend']]
    display_df.columns = pd.MultiIndex.from_arrays(arrays)

    money_subset = [(d1_label, 'Ad Spend'), (d1_label, 'Ad Sales'), (d1_label, 'Gross Sales'), (curr_label, 'Ad Spend'), (curr_label, 'Ad Sales'), (curr_label, 'Gross Sales')]
    float_subset = [(d1_label, 'Direct ROAS'), (d1_label, 'Total ROAS'), (curr_label, 'Direct ROAS'), (curr_label, 'Total ROAS')]
    growth_subset = [('Growth %', 'Gross Sales'), ('Growth %', 'Ad Spend')]

    styler = display_df.style.format("{:,.0f}", subset=money_subset).format("{:,.2f}", subset=float_subset).format("{:,.2f}%", subset=growth_subset).applymap(color_growth, subset=growth_subset).set_table_attributes('class="ad-table"')
    css = textwrap.dedent("""<style>.ad-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 13px; color: #000; } .ad-table th, .ad-table td { border: 1px solid #ccc; padding: 8px; text-align: right; } .ad-table thead tr:nth-child(1) th { background-color: #ffffff; text-align: center; font-weight: bold; font-size: 14px; border-bottom: 2px solid #000; } .ad-table thead tr:nth-child(2) th { background-color: #f8f9fa; text-align: center; font-size: 12px; font-weight: bold; color: #333; } .ad-table tbody tr { background-color: #ffffff !important; color: #000 !important; } .ad-table tbody tr th { text-align: left; background-color: #ffffff; font-weight: bold; color: #000; border-right: 2px solid #ccc; } .ad-table tbody tr:last-child { font-weight: bold; background-color: #f1f1f1 !important; border-top: 2px solid #000; }</style>""")
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(styler.to_html(), unsafe_allow_html=True)