import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine, text

# ===========================================================
# PAGE: SECONDARY → BLINKIT → SALES DASHBOARD
# ===========================================================

def page():

    st.title("📦 Blinkit Sales Dashboard")

    # ===================== Get Blinkit Data (Universal) =====================
    @st.cache_data(ttl=600)
    def get_blinkit_data():
        try:
            # --- Universal Secret Loader ---
            try:
                # 1. Try Local Secrets (Laptop)
                db_url = st.secrets["postgres"]["url"]
            except (FileNotFoundError, KeyError):
                # 2. Try Render Environment Variable (Cloud)
                db_url = os.environ.get("DATABASE_URL")
            
            # Check if URL was found
            if not db_url:
                st.error("❌ Database URL not found. Check secrets.toml or Render Environment Variables.")
                return pd.DataFrame()

            # Create Engine & Fetch Data
            engine = create_engine(db_url)
            with engine.connect() as conn:
                query = text("""
                    SELECT 
                        order_date,
                        sku,
                        feeder_wh,
                        net_revenue,
                        product,
                        quantity
                    FROM femisafe_blinkit_salesdata
                """)
                df = pd.read_sql(query, conn)
            return df
            
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    # Load data
    df_blinkit = get_blinkit_data()

    if df_blinkit.empty:
        st.warning("No Blinkit data available.")
        return

    # Process Dates
    df_blinkit['order_date'] = pd.to_datetime(df_blinkit['order_date'], errors='coerce')
    df_blinkit['month'] = df_blinkit['order_date'].dt.strftime('%B')

    # ===================== KPIs =====================
    total_revenue = df_blinkit['net_revenue'].sum()
    total_units = df_blinkit['quantity'].sum()

    latest_date = df_blinkit['order_date'].max()
    if pd.isnull(latest_date):
        latest_month = "Unknown"
        latest_revenue = 0
        latest_units = 0
    else:
        latest_month = latest_date.strftime('%B')
        latest_data = df_blinkit[df_blinkit['month'] == latest_month]
        latest_revenue = latest_data['net_revenue'].sum()
        latest_units = latest_data['quantity'].sum()

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
            <p style="{number_style}">₹{latest_revenue:,.0f}</p>
            <p style="{units_style}">{int(latest_units):,} units</p>
            <p style="{label_style}">{latest_month} Revenue</p>
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

    # ===================== Product Filter =====================

    # Create a sorted product list (added dropna)
    product_list = sorted(df_blinkit['product'].dropna().unique())

    # Single-select dropdown
    selected_product = st.selectbox(
        "Filter by Product",
        options=["All Products"] + product_list,
        index=0
    )

    # Apply filter
    if selected_product != "All Products":
        df_blinkit = df_blinkit[df_blinkit['product'] == selected_product]

    # ===================== Chart Section =====================

    if df_blinkit.empty:
        st.warning("No data for this selection.")
        return

    # Last 30 days filter based on MAX date in data
    max_date = df_blinkit['order_date'].max()
    df_blinkit_30 = df_blinkit[
        df_blinkit['order_date'] >= (max_date - pd.Timedelta(days=30))
    ]

    df_daily = df_blinkit_30.groupby('order_date', as_index=False).agg({
        'net_revenue': 'sum',
        'quantity': 'sum'
    })

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_daily['order_date'],
        y=df_daily['net_revenue'],
        mode='lines+markers',
        name='Revenue (INR)',
        line=dict(color='purple', width=3, shape='spline'),
        hovertemplate='Revenue: ₹%{y:,.0f}<extra></extra>'
    ))

    fig.add_trace(go.Scatter(
        x=df_daily['order_date'],
        y=df_daily['quantity'],
        mode='lines+markers',
        name='Units Sold',
        line=dict(color='green', width=3, shape='spline'),
        yaxis='y2',
        hovertemplate='Units: %{y:,} units<extra></extra>'
    ))

    fig.update_layout(
        title=dict(text="📈 Blinkit Sales (Last 30 Days)", font=dict(color="black", size=18)),
        xaxis=dict(
            title="Date",
            tickfont=dict(color="black"),
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
        ),
        yaxis=dict(
            title=dict(text="Net Sales (INR)", font=dict(color="purple")),
            tickfont=dict(color="purple"),
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",
        ),
        yaxis2=dict(
            title=dict(text="No. of Units Sold", font=dict(color="green")),
            tickfont=dict(color="green"),
            overlaying="y",
            side="right",
            showgrid=False
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