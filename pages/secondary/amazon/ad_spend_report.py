import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go 
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
# 🎨 SMART STYLING FUNCTIONS 
# ---------------------------------------------------------
def style_growth_sales(val):
    if pd.isna(val) or val == 0 or val == '': return ''
    bg = '#d4edda' if val > 0 else '#f8d7da' 
    text_color = '#155724' if val > 0 else '#721c24'
    return f'background-color: {bg}; color: {text_color}; font-weight: bold;'

def style_growth_spend(val):
    # Flipped logic: Red if spending more, Green if spending less
    if pd.isna(val) or val == 0 or val == '': return ''
    bg = '#f8d7da' if val > 0 else '#d4edda' 
    text_color = '#721c24' if val > 0 else '#155724'
    return f'background-color: {bg}; color: {text_color}; font-weight: bold;'

# ---------------------------------------------------------
# 🚀 DATA LOADER
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_amazon_data():
    engine = get_db_engine()
    if not engine: return pd.DataFrame(), pd.DataFrame()

    try:
        with engine.connect() as conn:
            # 1. Fetch Sales (We still need this for Gross Sales numbers)
            sales = pd.read_sql(text('SELECT date, "product", net_revenue FROM femisafe_amazon_salesdata'), conn)
            
            # 2. Fetch Ads (This will be our MASTER list for Product Names)
            a_cols = pd.read_sql(text("SELECT * FROM femisafe_amazon_addata LIMIT 1"), conn).columns.tolist()
            a_cols_low = {c.lower().strip(): c for c in a_cols}

            a_date = next((orig for low, orig in a_cols_low.items() if 'date' in low), 'date')
            a_spend = next((orig for low, orig in a_cols_low.items() if 'spend' in low or 'cost' in low), None)

            # Explicitly fetching "product" from Ad Data as requested
            a_query = [f'"{a_date}" as date', '"product" as product']
            a_query.append(f'"{a_spend}" as spend_inr' if a_spend else '0 as spend_inr')

            ads = pd.read_sql(text(f"SELECT {', '.join(a_query)} FROM femisafe_amazon_addata"), conn)

        # Clean and format both tables
        for df in [sales, ads]:
            if not df.empty:
                for col in df.columns:
                    if col not in ['date', 'product']:
                        df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)
                
                df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
                df.dropna(subset=['date'], inplace=True)
                
                if 'product' in df.columns:
                    df['product'] = df['product'].astype(str).str.strip()
                    df['product'] = df['product'].replace(['nan', 'None', ''], 'Unknown')

        return sales, ads
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

# ---------------------------------------------------------
# 🧮 PROCESSOR (Anchored to Ad Data Products)
# ---------------------------------------------------------
def process_table_data(df_sales, df_ads, target_date):
    if df_sales.empty and df_ads.empty: return pd.DataFrame(), None, None
    curr_date_ts = pd.to_datetime(target_date)
    prev_date_ts = curr_date_ts - timedelta(days=1)
    
    target_dates = [curr_date_ts, prev_date_ts]
    
    # Filter data by date
    sales_filt = df_sales[df_sales['date'].isin(target_dates)].copy()
    ads_filt = df_ads[df_ads['date'].isin(target_dates)].copy()

    sales_filt['date_str'] = sales_filt['date'].dt.date.astype(str)
    ads_filt['date_str'] = ads_filt['date'].dt.date.astype(str)

    # Group metrics
    sales_grp = sales_filt.groupby(['product', 'date_str'], as_index=False)['net_revenue'].sum()
    ads_grp = ads_filt.groupby(['product', 'date_str'], as_index=False)['spend_inr'].sum()

    # 🛑 THE FIX: LEFT JOIN onto ads_grp. 
    # This guarantees the table strictly uses the Product Names from your Ad Data.
    merged = pd.merge(ads_grp, sales_grp, on=['product', 'date_str'], how='left').fillna(0)
    if merged.empty: return pd.DataFrame(), curr_date_ts, prev_date_ts

    pivot = merged.pivot_table(index='product', columns='date_str', values=['spend_inr', 'net_revenue'], aggfunc='sum').fillna(0)
    pivot.columns = [f"{col[0]}_{col[1]}" for col in pivot.columns]

    curr_key = str(curr_date_ts.date())
    prev_key = str(prev_date_ts.date())

    def get_col(metric, date_key):
        col_name = f"{metric}_{date_key}"
        return pivot[col_name] if col_name in pivot.columns else pd.Series(0, index=pivot.index)

    d1_spend = get_col('spend_inr', prev_key)
    d1_sales = get_col('net_revenue', prev_key)
    d2_spend = get_col('spend_inr', curr_key)
    d2_sales = get_col('net_revenue', curr_key)

    d1_roas = np.where(d1_spend > 0, d1_sales / d1_spend, 0)
    d2_roas = np.where(d2_spend > 0, d2_sales / d2_spend, 0)

    g_sales = np.where(d1_sales > 0, (d2_sales - d1_sales) / d1_sales, np.nan)
    g_spend = np.where(d1_spend > 0, (d2_spend - d1_spend) / d1_spend, np.nan)

    d1_str = prev_date_ts.strftime("%B %d")
    d2_str = curr_date_ts.strftime("%B %d")

    res = pd.DataFrame(index=pivot.index)
    res[(d1_str, 'Ad Spend')] = d1_spend
    res[(d1_str, 'Gross Sales')] = d1_sales
    res[(d1_str, 'ROAS')] = d1_roas
    
    res[(d2_str, 'Ad Spend')] = d2_spend
    res[(d2_str, 'Gross Sales')] = d2_sales
    res[(d2_str, 'ROAS')] = d2_roas
    
    res[('Growth %', 'Gross Sales')] = g_sales
    res[('Growth %', 'Ad Spend')] = g_spend

    # Calculate Grand Totals
    total_d1_spend = d1_spend.sum()
    total_d1_sales = d1_sales.sum()
    total_d2_spend = d2_spend.sum()
    total_d2_sales = d2_sales.sum()

    t_g_sales = (total_d2_sales - total_d1_sales) / total_d1_sales if total_d1_sales > 0 else np.nan
    t_g_spend = (total_d2_spend - total_d1_spend) / total_d1_spend if total_d1_spend > 0 else np.nan

    total_row = pd.DataFrame({
        (d1_str, 'Ad Spend'): [total_d1_spend],
        (d1_str, 'Gross Sales'): [total_d1_sales],
        (d1_str, 'ROAS'): [total_d1_sales / total_d1_spend if total_d1_spend > 0 else 0],
        (d2_str, 'Ad Spend'): [total_d2_spend],
        (d2_str, 'Gross Sales'): [total_d2_sales],
        (d2_str, 'ROAS'): [total_d2_sales / total_d2_spend if total_d2_spend > 0 else 0],
        ('Growth %', 'Gross Sales'): [t_g_sales],
        ('Growth %', 'Ad Spend'): [t_g_spend]
    }, index=['Grand Total'])

    # Sort alphabetically by Product Name to act like a static Excel list
    res = res.sort_index() 
    
    res = pd.concat([res, total_row]) 
    res.columns = pd.MultiIndex.from_tuples(res.columns)
    res.index.name = "Product Name"
    
    return res, d1_str, d2_str

# =======================================================
# 🖥️ PAGE RENDERING
# =======================================================
def page():
    st.markdown("### 📊 Amazon Ad Spend & Sales Report")
    sales, ads = get_amazon_data()

    if sales.empty and ads.empty:
        st.warning("No data available.")
        return

    with st.expander("📈 View Sales vs Ads Chart", expanded=True):
        col1, col2 = st.columns([3, 1])
        with col2: 
            range_lbl = st.selectbox("Range", ["Last 7 Days", "Last 14 Days", "Last 30 Days"])
        
        days = {"Last 7 Days": 7, "Last 14 Days": 14, "Last 30 Days": 30}
        max_date = sales['date'].max() if not sales.empty else pd.Timestamp.now()
        start_date = max_date - timedelta(days=days[range_lbl])
        
        s_c = sales[(sales['date'] >= start_date)].groupby('date')['net_revenue'].sum().reset_index()
        a_c = ads[(ads['date'] >= start_date)].groupby('date')['spend_inr'].sum().reset_index()
        merged = pd.merge(s_c, a_c, on='date', how='outer').fillna(0).sort_values('date')
        merged['label'] = merged['date'].dt.strftime('%b %d')

        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=merged['label'], y=merged['net_revenue'],
            name='Gross Sales', marker_color='#66bb6a',
            hovertemplate='₹%{y:,.0f}<extra></extra>'
        ))
        
        fig.add_trace(go.Bar(
            x=merged['label'], y=merged['spend_inr'],
            name='Ad Spend', marker_color='#ab47bc',
            hovertemplate='₹%{y:,.0f}<extra></extra>'
        ))

        fig.update_layout(
            title=f"Sales vs Ad Spend ({range_lbl})",
            height=450,
            barmode='group',
            hovermode="x unified",
            xaxis=dict(title="", showgrid=False),
            yaxis=dict(title="Amount (₹)", showgrid=True, gridcolor='#333'),
            legend=dict(orientation="h", y=1.1, x=0),
            margin=dict(l=20, r=20, t=60, b=20)
        )
        
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    
    st.subheader("📋 Performance Report")
    report_date = st.date_input("Select Report Date", value=datetime.now().date() - timedelta(days=1))
    
    final_df, d1_str, d2_str = process_table_data(sales, ads, report_date)

    if not final_df.empty:
        format_dict = {
            (d1_str, 'Ad Spend'): "{:,.0f}",
            (d1_str, 'Gross Sales'): "{:,.0f}",
            (d1_str, 'ROAS'): "{:,.2f}",
            (d2_str, 'Ad Spend'): "{:,.0f}",
            (d2_str, 'Gross Sales'): "{:,.0f}",
            (d2_str, 'ROAS'): "{:,.2f}",
            ('Growth %', 'Gross Sales'): "{:+.2%}",
            ('Growth %', 'Ad Spend'): "{:+.2%}"
        }

        # Styled as a strict, non-sortable Excel-style table
        styled_df = final_df.style.format(format_dict, na_rep="") \
            .map(style_growth_sales, subset=[('Growth %', 'Gross Sales')]) \
            .map(style_growth_spend, subset=[('Growth %', 'Ad Spend')])

        st.table(styled_df)