import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
# 🚀 OPTIMIZED DATA LOADER
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def get_overall_sales_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: Select only needed columns
            # Note: We select specific columns to avoid 'SELECT *' overhead
            query = text("SELECT revenue, sku_units, order_date, month FROM femisafe_sales")
            df = pd.read_sql(query, conn)
        
        if df.empty: return df

        # =========================================================
        # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
        # =========================================================

        # 1. Standardize Column Names
        df.columns = df.columns.str.strip().str.lower()
        
        # 2. Rename 'sku_units' to 'units' for consistency
        if 'sku_units' in df.columns:
            df.rename(columns={'sku_units': 'units'}, inplace=True)
        elif 'units' not in df.columns:
            df['units'] = 0

        # 3. Fast Vectorized Cleaning (Revenue & Units)
        # Regex removes ₹, commas, spaces instantly
        if 'revenue' in df.columns:
            df['revenue'] = pd.to_numeric(
                df['revenue'].astype(str).str.replace(r'[₹,]', '', regex=True),
                errors='coerce'
            ).fillna(0)

        if 'units' in df.columns:
            df['units'] = pd.to_numeric(
                df['units'].astype(str).str.replace(',', ''),
                errors='coerce'
            ).fillna(0).astype('int32')

        # 4. Fast Date Parsing (dayfirst=True fixes date flipping)
        df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')
        df.dropna(subset=['order_date'], inplace=True)

        # 5. Optimize Text to Category
        if 'month' in df.columns:
            df['month'] = df['month'].astype(str).str.strip().astype('category')

        return df

    except Exception as e:
        st.error(f"⚠️ Data Load Error: {e}")
        return pd.DataFrame()

# ===========================================================
# PAGE
# ===========================================================
def page():

    st.title("📊 Overall Sales Overview (Optimized)")

    # Load Data (Instant if cached)
    df = get_overall_sales_data()

    if df.empty:
        st.warning("No data available in 'femisafe_sales'.")
        return

    # ---------------------------------------------------------
    # 2. PREPROCESS DATA
    # ---------------------------------------------------------
    # Total Metrics
    total_revenue = df['revenue'].sum()
    total_units = df['units'].sum()

    # Latest Month Metrics
    latest_date = df['order_date'].max()
    latest_year = latest_date.year
    latest_month_num = latest_date.month
    month_name = latest_date.strftime("%B")

    # Fast filtering for latest month
    latest_month_df = df[
        (df['order_date'].dt.year == latest_year) &
        (df['order_date'].dt.month == latest_month_num)
    ]

    latest_month_revenue = latest_month_df['revenue'].sum()
    latest_month_units = latest_month_df['units'].sum()

    # -----------------------------------------
    # 3. CARD STYLES
    # -----------------------------------------
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
    label_style = "font-size: 0.9rem; margin-top: 4px; color: #e0e0e0; font-weight: 500;"
    units_style = "font-size: 0.9rem; margin-top: 2px; color: #cfcfcf;"

    col1, col2 = st.columns(2)

    # CARD 1 → LATEST MONTH
    with col1:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">₹{latest_month_revenue:,.0f}</p>
            <p style="{units_style}">{int(latest_month_units):,} units</p>
            <p style="{label_style}">{month_name} Revenue</p>
        </div>
        """, unsafe_allow_html=True)

    # CARD 2 → TOTAL
    with col2:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">₹{total_revenue:,.0f}</p>
            <p style="{units_style}">{int(total_units):,} units</p>
            <p style="{label_style}">Total Revenue (All Months)</p>
        </div>
        """, unsafe_allow_html=True)

    # -----------------------------------------
    # 4. CHART SECTION
    # -----------------------------------------
    
    # Filter Logic (April to Latest)
    # Using .dt accessors is fast enough here
    if latest_month_num >= 4:
        df_chart = df[df['order_date'].dt.month.between(4, latest_month_num)]
    else:
        # If current month is Jan/Feb/Mar, show April-Dec of prev year + Jan-Current of this year
        # Logic: Month is >= 4 OR Month is <= current month
        df_chart = df[
            (df['order_date'].dt.month >= 4) | 
            (df['order_date'].dt.month <= latest_month_num)
        ]

    # observed=True speeds up grouping on 'month' category
    df_monthly = df_chart.groupby('month', observed=False, as_index=False).agg({
        'revenue': 'sum',
        'units': 'sum'
    })

    month_map = {
        1:'January',2:'February',3:'March',4:'April',
        5:'May',6:'June',7:'July',8:'August',
        9:'September',10:'October',11:'November',12:'December'
    }

    # Define custom sort order for months
    if latest_month_num >= 4:
        month_order = [month_map[m] for m in range(4, latest_month_num + 1)]
    else:
        month_order = [month_map[m] for m in range(4, 13)] + [month_map[m] for m in range(1, latest_month_num + 1)]

    # Filter out months that might not exist in data yet to prevent empty categories
    existing_months = set(df_monthly['month'].unique())
    month_order = [m for m in month_order if m in existing_months]

    df_monthly['month'] = pd.Categorical(
        df_monthly['month'],
        categories=month_order,
        ordered=True
    )
    df_monthly = df_monthly.sort_values('month')

    # SMOOTH LINE CHART
    fig = go.Figure()

    # Revenue trace
    fig.add_trace(go.Scatter(
        x=df_monthly['month'],
        y=df_monthly['revenue'],
        mode='lines+markers',
        name='Net Sales (INR)',
        line=dict(color='purple', shape='spline'),
        hovertemplate='Revenue: ₹%{y:,.0f}<extra></extra>'
    ))

    # Units trace
    fig.add_trace(go.Scatter(
        x=df_monthly['month'],
        y=df_monthly['units'],
        mode='lines+markers',
        name='Units Sold',
        line=dict(color='green', shape='spline'),
        yaxis='y2',
        hovertemplate='Units: %{y:.0f} units<extra></extra>'
    ))

    fig.update_layout(
        title=f"📈 Month-wise Sales Overview (Apr–{month_map[latest_month_num]})",
        xaxis_title="Date",
        yaxis_title="Revenue (₹)",
        yaxis2=dict(
            title="Units",
            overlaying="y",
            side="right"
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="black",
            font_size=13,
            font_color="white"
        )
    )

    st.plotly_chart(fig, use_container_width=True)