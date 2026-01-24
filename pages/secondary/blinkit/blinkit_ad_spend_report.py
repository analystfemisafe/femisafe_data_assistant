import streamlit as st
import pandas as pd
import numpy as np  # <--- Added this missing import
from sqlalchemy import text

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    # Fallback if utils folder missing
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 🚀 OPTIMIZED DATA LOADER: AD DATA
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def get_blinkit_addata():
    engine = get_db_engine()
    if not engine: return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ Select ALL is okay here if table is small, otherwise select specific columns
            query = text("SELECT * FROM femisafe_blinkit_addata")
            df = pd.read_sql(query, conn)
        
        if df.empty: return df

        # =========================================================
        # ⚡ FAST CLEANING & OPTIMIZATION
        # =========================================================
        
        # 1. Vectorized Cleaning (Regex is faster than chained replace)
        cols_to_clean = ['estimated_budget_consumed', 'direct_sales', 'impressions', 'clicks', 'roas']
        for col in cols_to_clean:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(r'[₹,%]', '', regex=True),
                    errors='coerce'
                ).fillna(0)

        # 2. Fast Date Parsing (dayfirst=True prevents date flipping)
        df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
        
        # 3. Optimize Text to Category
        if 'product_name' in df.columns:
            df['product_name'] = df['product_name'].astype(str).str.strip().astype('category')

        return df
        
    except Exception as e:
        st.error(f"⚠️ Error fetching Ad Data: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 🚀 OPTIMIZED DATA LOADER: SALES DATA
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def get_blinkit_salesdata():
    engine = get_db_engine()
    if not engine: return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ Only fetch columns needed for this report
            query = text("SELECT order_date, product, total_gross_bill_amount FROM femisafe_blinkit_salesdata")
            df = pd.read_sql(query, conn)
            
        if df.empty: return df

        # 1. Clean Revenue
        if 'total_gross_bill_amount' in df.columns:
            df['total_gross_bill_amount'] = pd.to_numeric(
                df['total_gross_bill_amount'].astype(str).str.replace(r'[₹,]', '', regex=True),
                errors='coerce'
            ).fillna(0)
        
        # 2. Fast Date Parsing
        df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')
        
        # 3. Optimize Product Name
        if 'product' in df.columns:
            df['product'] = df['product'].astype(str).str.strip().astype('category')

        return df
        
    except Exception as e:
        st.error(f"⚠️ Error fetching Sales Data: {e}")
        return pd.DataFrame()
    
# ===========================================================
# PAGE
# ===========================================================
def page():

    st.markdown("### 📊 Blinkit Ad Report (Optimized)")

    # Load Data (Instant if cached)
    df_ad = get_blinkit_addata()
    df_sales = get_blinkit_salesdata()

    if df_ad.empty:
        st.warning("No Ad Data Found.")
        return
    if df_sales.empty:
        st.warning("No Sales Data Found.")
        return

    # ===================== METRIC CARDS =====================

    card_style = """
        background-color: #3a3a3a;
        color: white;
        padding: 25px 10px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        width: 100%;
    """
    number_style = "font-size: 2rem; font-weight: bold; margin: 0;"
    label_style = "font-size: 0.9rem; margin-top: 4px; color: #e0e0e0;"
    units_style = "font-size: 0.9rem; margin-top: 2px; color: #cfcfcf;"

    # Valid Dates Check
    latest_date = df_ad['date'].max()
    if pd.isnull(latest_date):
        st.error("Invalid Dates in Ad Data.")
        return
        
    latest_month = df_ad['date'].dt.to_period('M').max()

    # Card Values
    month_spend = df_ad[df_ad['date'].dt.to_period('M') == latest_month]['estimated_budget_consumed'].sum()
    day_spend = df_ad[df_ad['date'] == latest_date]['estimated_budget_consumed'].sum()

    seven_days_ago = latest_date - pd.Timedelta(days=7)
    df_last7 = df_ad[(df_ad['date'] >= seven_days_ago) & (df_ad['date'] <= latest_date)]

    total_spend_7 = df_last7['estimated_budget_consumed'].sum()
    total_sales_7 = df_last7['direct_sales'].sum()

    if total_spend_7 > 0:
        last7_roas = total_sales_7 / total_spend_7
    else:
        last7_roas = 0

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
            <div style="{card_style}">
                <p style="{number_style}">₹{month_spend:,.0f}</p>
                <p style="{units_style}">{latest_month.strftime('%B %Y')}</p>
                <p style="{label_style}">Latest Month Spend</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div style="{card_style}">
                <p style="{number_style}">₹{day_spend:,.0f}</p>
                <p style="{units_style}">{latest_date.strftime('%b %d, %Y')}</p>
                <p style="{label_style}">Latest Day Spend</p>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        roas_display = f"{last7_roas:.2f}×"
        st.markdown(f"""
            <div style="{card_style}">
                <p style="{number_style}">{roas_display}</p>
                <p style="{units_style}">Last 7 Days</p>
                <p style="{label_style}">Average ROAS</p>
            </div>
        """, unsafe_allow_html=True)

    # ===================== DATA FOR TABLE =====================

    prev_date = latest_date - pd.Timedelta(days=1)

    # Filter last 2 days
    df_ad_last2 = df_ad[df_ad['date'].isin([latest_date, prev_date])]
    df_sales_last2 = df_sales[df_sales['order_date'].isin([latest_date, prev_date])]

    # Aggregate Ads by Product & Date (observed=True for speed)
    ad_summary = df_ad_last2.groupby(['product_name', 'date'], observed=True, as_index=False).agg({
        'estimated_budget_consumed': 'sum',
        'direct_sales': 'sum'
    })

    # Aggregate Sales by Product & Date
    sales_summary = df_sales_last2.groupby(['product', 'order_date'], observed=True, as_index=False).agg({
        'total_gross_bill_amount': 'sum'
    }).rename(columns={'order_date': 'date', 'total_gross_bill_amount': 'gross_sales'})

    # Merge Ads + Sales
    # Note: Merging on Categorical columns is faster if categories match
    merged = pd.merge(ad_summary, sales_summary,
                      left_on=['product_name', 'date'],
                      right_on=['product', 'date'],
                      how='outer') 

    # Fill NaNs with 0
    merged['estimated_budget_consumed'] = merged['estimated_budget_consumed'].fillna(0)
    merged['direct_sales'] = merged['direct_sales'].fillna(0)
    merged['gross_sales'] = merged['gross_sales'].fillna(0)
    
    # Consolidate Product Names
    # We convert to object temporarily to fillna, then back to category if needed
    merged['product_name'] = merged['product_name'].astype(object).fillna(merged['product'].astype(object))
    merged = merged.drop(columns=['product'])

    # ROAS Calculations
    # Vectorized calculation is faster than apply
    merged['direct_roas'] = np.where(merged['estimated_budget_consumed'] > 0, 
                                     merged['direct_sales'] / merged['estimated_budget_consumed'], 0)
    merged['roas'] = np.where(merged['estimated_budget_consumed'] > 0, 
                              merged['gross_sales'] / merged['estimated_budget_consumed'], 0)
    
    # Pivot Table
    pivot = merged.pivot_table(
        index='product_name',
        columns='date',
        values=['estimated_budget_consumed', 'direct_sales', 'gross_sales', 'direct_roas', 'roas'],
        aggfunc='sum'
    )

    # Flatten Columns
    pivot.columns = [f"{metric}_{date.strftime('%b %d')}" for metric, date in pivot.columns]
    pivot = pivot.reset_index()

    prev_label = prev_date.strftime("%b %d")
    latest_label = latest_date.strftime("%b %d")

    # Ensure required columns exist
    req_cols = [
        f'gross_sales_{latest_label}', f'gross_sales_{prev_label}',
        f'estimated_budget_consumed_{latest_label}', f'estimated_budget_consumed_{prev_label}'
    ]
    for col in req_cols:
        if col not in pivot.columns:
            pivot[col] = 0

    # Growth Calculations (Vectorized)
    
    col_sales_curr = f'gross_sales_{latest_label}'
    col_sales_prev = f'gross_sales_{prev_label}'
    pivot['Gross_Sales_Growth_%'] = np.where(
        pivot[col_sales_prev] > 0,
        ((pivot[col_sales_curr] - pivot[col_sales_prev]) / pivot[col_sales_prev] * 100),
        0
    )

    col_spend_curr = f'estimated_budget_consumed_{latest_label}'
    col_spend_prev = f'estimated_budget_consumed_{prev_label}'
    pivot['Ad_Spend_Growth_%'] = np.where(
        pivot[col_spend_prev] > 0,
        ((pivot[col_spend_curr] - pivot[col_spend_prev]) / pivot[col_spend_prev] * 100),
        0
    )

    # Sort
    pivot = pivot.sort_values(by=f'gross_sales_{latest_label}', ascending=False)

    # ===================== Total Row =====================
    total_data = {'product_name': '🏆 TOTAL'}
    
    for col in pivot.columns:
        if col != 'product_name':
            if "Growth" in col:
                total_data[col] = pivot[col].mean()
            else:
                total_data[col] = pivot[col].sum()

    total_row = pd.DataFrame([total_data])
    pivot = pd.concat([pivot, total_row], ignore_index=True)

    # ===================== Display Table =====================
    st.markdown("### 📄 Ad Performance Summary")
    
    st.dataframe(
        pivot,
        use_container_width=True,
        hide_index=True,
        column_config={
            "product_name": "Product",
            f"estimated_budget_consumed_{latest_label}": st.column_config.NumberColumn(f"Ads Spend ({latest_label})", format="₹%.0f"),
            f"gross_sales_{latest_label}": st.column_config.NumberColumn(f"Gross Sales ({latest_label})", format="₹%.0f"),
            "Gross_Sales_Growth_%": st.column_config.NumberColumn("Sales Growth", format="%.2f%%"),
            "Ad_Spend_Growth_%": st.column_config.NumberColumn("Spend Growth", format="%.2f%%"),
        }
    )