import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
# 🚀 OPTIMIZED DATA LOADER
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_overall_sales_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # Fetch minimal data
            query = text('SELECT revenue, sku_units, order_date FROM femisafe_sales')
            df = pd.read_sql(query, conn)
        
        if df.empty: return df

        # Clean Column Names
        df.columns = df.columns.str.strip().str.lower()
        
        # Standardize Metrics
        if 'sku_units' in df.columns:
            df.rename(columns={'sku_units': 'units'}, inplace=True)
        elif 'units' not in df.columns:
            df['units'] = 0

        # Clean Numerics
        for col in ['revenue', 'units']:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(r'[₹,]', '', regex=True),
                    errors='coerce'
                ).fillna(0)

        # 🛠️ DATE FIX: Handle YYYY-MM-DD vs DD-MM-YYYY safely
        df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')
        df.dropna(subset=['order_date'], inplace=True)

        return df

    except Exception as e:
        st.error(f"⚠️ Data Load Error: {e}")
        return pd.DataFrame()

# ===========================================================
# PAGE
# ===========================================================
def page():

    st.title("📊 Overall Sales Overview")

    # 1. Load Data
    df = get_overall_sales_data()

    if df.empty:
        st.warning("No data available.")
        return

    # 2. Latest Date Context
    latest_date = df['order_date'].max()
    latest_month_name = latest_date.strftime("%B")
    
    # ---------------------------------------------------------
    # 3. METRIC CARDS (Current vs Previous Month)
    # ---------------------------------------------------------
    # Current Month
    current_month_df = df[
        (df['order_date'].dt.month == latest_date.month) & 
        (df['order_date'].dt.year == latest_date.year)
    ]
    curr_rev = current_month_df['revenue'].sum()
    curr_units = current_month_df['units'].sum()

    # Previous Month
    prev_date = latest_date - pd.DateOffset(months=1)
    prev_month_df = df[
        (df['order_date'].dt.month == prev_date.month) & 
        (df['order_date'].dt.year == prev_date.year)
    ]
    prev_rev = prev_month_df['revenue'].sum()
    prev_units = prev_month_df['units'].sum()
    prev_month_name = prev_date.strftime("%B")

    # Growth Calculation
    if prev_rev > 0:
        growth = ((curr_rev - prev_rev) / prev_rev) * 100
        growth_str = f"{growth:+.1f}%"
        growth_color = "#4caf50" if growth > 0 else "#ef5350"
    else:
        growth_str = "-"
        growth_color = "#ccc"

    # Display Cards
    card_style = "background-color: #1e1e1e; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #333;"
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div style="{card_style}">
            <h3 style="margin:0; color:#ccc; font-size:16px;">Current Month ({latest_month_name})</h3>
            <h2 style="margin:5px 0; font-size: 28px;">₹{curr_rev:,.0f}</h2>
            <p style="margin:0; color:#888;">{int(curr_units):,} units</p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div style="{card_style}">
            <h3 style="margin:0; color:#ccc; font-size:16px;">Last Month ({prev_month_name})</h3>
            <h2 style="margin:5px 0; font-size: 28px;">₹{prev_rev:,.0f}</h2>
            <p style="margin:0; color:#888;">
                {int(prev_units):,} units 
                <span style="font-size: 14px; color:{growth_color}; margin-left: 10px;">
                    ({growth_str})
                </span>
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ---------------------------------------------------------
    # 4. DYNAMIC CHART SECTION
    # ---------------------------------------------------------
    
    # A. View Selection
    view_mode = st.radio(
        "📅 Select Time Range", 
        ["Financial Year (Current)", "All Time (Lifetime)", "Quarterly View"], 
        horizontal=True
    )

    # B. Filter & Grouping Logic
    df_chart = df.copy()
    chart_title = ""
    x_label_col = 'label'

    # Logic for Financial Year
    if view_mode == "Financial Year (Current)":
        if latest_date.month >= 4:
            fy_start_year = latest_date.year
        else:
            fy_start_year = latest_date.year - 1
        
        start_date = pd.Timestamp(year=fy_start_year, month=4, day=1)
        df_chart = df_chart[df_chart['order_date'] >= start_date]
        
        # Group by Month (YYYY-MM)
        df_chart['sort_key'] = df_chart['order_date'].dt.to_period('M')
        chart_title = f"Sales Trend (FY {fy_start_year}-{fy_start_year+1})"

    # Logic for All Time
    elif view_mode == "All Time (Lifetime)":
        # No filter, just group by Month
        df_chart['sort_key'] = df_chart['order_date'].dt.to_period('M')
        chart_title = "Lifetime Sales Trend (All Months)"

    # Logic for Quarterly View
    elif view_mode == "Quarterly View":
        # No filter, but group by Quarter (YYYY-Q)
        df_chart['sort_key'] = df_chart['order_date'].dt.to_period('Q')
        chart_title = "Quarterly Performance (Q1/Q2/Q3/Q4)"

    # C. Aggregation
    # We group by 'sort_key' to ensure correct chronological sorting
    df_agg = df_chart.groupby('sort_key', as_index=False).agg({
        'revenue': 'sum', 
        'units': 'sum'
    })
    
    # Sort Chronologically (2025-01 comes before 2026-01)
    df_agg = df_agg.sort_values('sort_key')
    
    # Create readable labels
    if view_mode == "Quarterly View":
        df_agg['label'] = df_agg['sort_key'].astype(str) # e.g., "2025Q1"
    else:
        df_agg['label'] = df_agg['sort_key'].dt.strftime('%b %Y') # e.g., "Jan 2025"

    # D. Plotting
    fig = go.Figure()
    
    # Revenue Line
    fig.add_trace(go.Scatter(
        x=df_agg['label'], y=df_agg['revenue'],
        mode='lines+markers', name='Revenue',
        line=dict(color='#ab47bc', width=3, shape='spline'),
        hovertemplate='₹%{y:,.0f}<extra></extra>'
    ))
    
    # Units Line
    fig.add_trace(go.Scatter(
        x=df_agg['label'], y=df_agg['units'],
        mode='lines+markers', name='Units',
        yaxis='y2', line=dict(color='#66bb6a', width=3, shape='spline'),
        hovertemplate='%{y} units<extra></extra>'
    ))

    fig.update_layout(
        title=chart_title,
        height=500,
        hovermode="x unified",
        yaxis=dict(title="Revenue (₹)", showgrid=True, gridcolor='#333'),
        yaxis2=dict(title="Units Sold", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.1, x=0),
        margin=dict(l=20, r=20, t=80, b=20)
    )
    
    st.plotly_chart(fig, use_container_width=True)