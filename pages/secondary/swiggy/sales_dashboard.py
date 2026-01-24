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
def get_swiggy_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: Fetch only columns used in KPIs and Charts
            query = text("""
                SELECT 
                    ordered_date,
                    units_sold,
                    month
                FROM femisafe_swiggy_salesdata
            """)
            df = pd.read_sql(query, conn)
        
        if df.empty: return df

        # =========================================================
        # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
        # =========================================================

        # 1. Fast Vectorized Cleaning
        if 'units_sold' in df.columns:
            df['units_sold'] = pd.to_numeric(
                df['units_sold'].astype(str).str.replace(',', ''),
                errors='coerce'
            ).fillna(0).astype('int32')

        # 2. Fast Date Parsing (dayfirst=True fixes date flipping)
        df['ordered_date'] = pd.to_datetime(df['ordered_date'], dayfirst=True, errors='coerce')
        df.dropna(subset=['ordered_date'], inplace=True)

        # 3. Optimize Text to Category
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

    st.title("🛵 Swiggy Sales Dashboard (Optimized)")

    # Load Data (Instant if cached)
    df = get_swiggy_data()

    if df.empty:
        st.warning("No Swiggy data available.")
        return

    # ===================== KPIs =====================
    total_units = df['units_sold'].sum()

    latest_date = df['ordered_date'].max()
    
    if pd.isnull(latest_date):
        latest_month = "Unknown"
        latest_units = 0
    else:
        latest_month = latest_date.strftime('%B')
        # Fast boolean indexing
        # Note: We rely on the DB 'month' column matching the strftime format
        # If the DB month column is unreliable, use: df[df['ordered_date'].dt.month == latest_date.month]
        if 'month' in df.columns and latest_month in df['month'].values:
             latest_data = df[df['month'] == latest_month]
        else:
             # Fallback: calculate based on date
             latest_data = df[df['ordered_date'] >= (latest_date - pd.Timedelta(days=30))]
             
        latest_units = latest_data['units_sold'].sum()

    # ===================== Card Styling =====================
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

    with col1:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">{int(latest_units):,}</p>
            <p style="{units_style}">units</p>
            <p style="{label_style}">{latest_month} Units Sold</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">{int(total_units):,}</p>
            <p style="{units_style}">units</p>
            <p style="{label_style}">Total Units Sold (All Months)</p>
        </div>
        """, unsafe_allow_html=True)

    # ===================== Chart Section =====================

    # Last 30 days filter based on MAX date in data
    max_date = df['ordered_date'].max()
    start_date = max_date - pd.Timedelta(days=30)
    
    df_30 = df[df['ordered_date'] >= start_date]

    if df_30.empty:
        st.warning("No data available for the last 30 days.")
        return

    # observed=True speeds up groupby on categories (if ordered_date were categorical)
    df_daily = df_30.groupby('ordered_date', as_index=False).agg({
        'units_sold': 'sum'
    })

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_daily['ordered_date'],
        y=df_daily['units_sold'],
        mode='lines+markers',
        name='Units Sold',
        line=dict(color='green', width=3, shape='spline'),
        hovertemplate='Units: %{y:,}<extra></extra>'
    ))

    fig.update_layout(
        title=dict(text="📈 Swiggy Units Sold (Last 30 Days)", font=dict(color="black", size=18)),
        xaxis=dict(
            title="Date",
            tickfont=dict(color="black"),
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)",
        ),
        yaxis=dict(
            title="Units Sold",
            tickfont=dict(color="green"),
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5
        ),
        template="plotly_white",
        hovermode='x unified',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    st.plotly_chart(fig, use_container_width=True)