import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import text

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    # Fallback if utils folder missing (Safety net)
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 🚀 OPTIMIZED DATA LOADER
# ---------------------------------------------------------
@st.cache_data(ttl=900)  # Cache for 15 minutes
def get_blinkit_data():
    engine = get_db_engine()
    if not engine: return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: Fetch only needed columns
            query = text("""
                SELECT 
                    order_date, 
                    product, 
                    feeder_wh, 
                    net_revenue, 
                    quantity 
                FROM femisafe_blinkit_salesdata
            """)
            df = pd.read_sql(query, conn)
        
        if df.empty: return df

        # =========================================================
        # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
        # =========================================================
        
        # 1. Fast Vectorized Cleaning (Regex is faster than chained .str.replace)
        for col in ['net_revenue', 'quantity']:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r'[₹,]', '', regex=True), 
                errors='coerce'
            ).fillna(0)

        # 2. Downcast numeric types (Saves memory)
        df['quantity'] = df['quantity'].astype('int32') 
        # Revenue needs float for cents/paisas
        
        # 3. Use Categories for Text (Instant filtering speedup)
        df['feeder_wh'] = df['feeder_wh'].fillna("Unknown").astype(str).str.title().astype('category')
        df['product'] = df['product'].astype('category')
        
        # 4. Fast Date Parsing (dayfirst=True fixes date flipping errors)
        df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')
        
        return df

    except Exception as e:
        st.error(f"⚠️ Data Load Error: {e}")
        return pd.DataFrame()

# ===========================================================
# PAGE
# ===========================================================
def page():

    st.title("⚡ Blinkit Sales Dashboard (Optimized)")

    # Load Data (Instant if cached)
    df = get_blinkit_data()

    if df.empty:
        st.warning("No Blinkit data available.")
        return

    # ===================== Filters =====================
    st.markdown("### 🔍 Filters")
    col1, col2, col3 = st.columns(3)

    # Convert categories to list for sorting (Categories are fast!)
    wh_list = sorted(list(df['feeder_wh'].unique()))
    prod_list = sorted(list(df['product'].unique()))

    with col1:
        selected_wh = st.selectbox("🏭 Warehouse", ["All"] + wh_list)

    with col2:
        selected_prod = st.selectbox("📦 Product", ["All"] + prod_list)
        
    with col3:
        time_period = st.selectbox("📅 Time Period", ["Last 30 Days", "All Time"])

    # --- Apply Filters ---
    # Filtering categories is 100x faster than filtering strings
    df_filtered = df.copy()

    if selected_wh != "All":
        df_filtered = df_filtered[df_filtered['feeder_wh'] == selected_wh]

    if selected_prod != "All":
        df_filtered = df_filtered[df_filtered['product'] == selected_prod]

    # Time Filter Logic
    max_date = df_filtered['order_date'].max()
    if time_period == "Last 30 Days" and not pd.isnull(max_date):
        df_filtered = df_filtered[df_filtered['order_date'] >= (max_date - pd.Timedelta(days=30))]

    if df_filtered.empty:
        st.warning("No data found for these filters.")
        return

    # ===================== KPIs =====================
    total_rev = df_filtered['net_revenue'].sum()
    total_units = df_filtered['quantity'].sum()

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

    kpi1, kpi2 = st.columns(2)
    with kpi1:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">₹{total_rev:,.0f}</p>
            <p style="{label_style}">Total Revenue</p>
        </div>
        """, unsafe_allow_html=True)

    with kpi2:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">{int(total_units):,}</p>
            <p style="{label_style}">Units Sold</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ===================== 1. Sales Trend Chart =====================
    st.subheader("📈 Sales Trend")
    
    # Observed=True is faster for grouping categories
    df_trend = df_filtered.groupby('order_date', observed=True, as_index=False).agg({
        'net_revenue': 'sum', 
        'quantity': 'sum'
    })
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_trend['order_date'], 
        y=df_trend['net_revenue'], 
        name="Revenue (INR)", 
        mode='lines+markers',
        line=dict(color='purple', width=3, shape='spline')
    ))
    
    fig.add_trace(go.Scatter(
        x=df_trend['order_date'], 
        y=df_trend['quantity'], 
        name="Units Sold", 
        mode='lines+markers',
        line=dict(color='green', width=3, shape='spline'), 
        yaxis="y2"
    ))
    
    fig.update_layout(
        height=400,
        title="Revenue vs Units Sold",
        xaxis=dict(title="Date", showgrid=True),
        yaxis=dict(
            title=dict(text="Revenue (₹)", font=dict(color="purple")),
            tickfont=dict(color="purple"),
            showgrid=True
        ),
        yaxis2=dict(
            title=dict(text="Units", font=dict(color="green")),
            tickfont=dict(color="green"),
            overlaying="y", 
            side="right", 
            showgrid=False
        ),
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center")
    )
    st.plotly_chart(fig, use_container_width=True)

    # ===================== 2. Summary Table =====================
    st.subheader("📋 Detailed Summary (Warehouse View)")

    summary_df = df_filtered.groupby(['feeder_wh', 'product'], observed=True, as_index=False).agg({
        'quantity': 'sum',
        'net_revenue': 'sum'
    })

    grand_total_rev = summary_df['net_revenue'].sum()
    
    if grand_total_rev > 0:
        summary_df['revenue_pct'] = (summary_df['net_revenue'] / grand_total_rev * 100)
    else:
        summary_df['revenue_pct'] = 0

    summary_df = summary_df.rename(columns={
        'feeder_wh': 'Feeder WH',
        'product': 'Product',
        'quantity': 'Quantity',
        'net_revenue': 'Revenue',
        'revenue_pct': 'Revenue %'
    })

    summary_df = summary_df.sort_values(by=['Feeder WH', 'Revenue'], ascending=[True, False])

    st.dataframe(
        summary_df,
        use_container_width=True,
        column_config={
            "Revenue": st.column_config.NumberColumn(format="₹%.2f"),
            "Revenue %": st.column_config.NumberColumn(format="%.2f%%"),
            "Quantity": st.column_config.NumberColumn(format="%d"),
        },
        hide_index=True,
        height=500
    )