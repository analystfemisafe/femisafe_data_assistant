import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine, text

# ===========================================================
# PAGE: SECONDARY → AMAZON → SALES DASHBOARD
# ===========================================================

def page():

    st.title("🛒 Amazon Sales Dashboard")

    # ===================== Get Amazon Data (Universal) =====================
    @st.cache_data(ttl=600)
    def get_amazon_data():
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
                        date,
                        sku,
                        product,
                        net_revenue,
                        units_sold
                    FROM femisafe_amazon_salesdata
                """)
                df = pd.read_sql(query, conn)
            return df
            
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    # Load data
    df_amz = get_amazon_data()

    if df_amz.empty:
        st.warning("No Amazon data available.")
        return

    # Process Dates
    df_amz['date'] = pd.to_datetime(df_amz['date'], errors='coerce')
    df_amz['month'] = df_amz['date'].dt.strftime('%B')

    # ===================== KPIs =====================
    total_revenue = df_amz['net_revenue'].sum()
    total_units = df_amz['units_sold'].sum()

    latest_date = df_amz['date'].max()
    if pd.isnull(latest_date):
        latest_month = "Unknown"
        latest_revenue = 0
        latest_units = 0
    else:
        latest_month = latest_date.strftime('%B')
        latest_data = df_amz[df_amz['month'] == latest_month]
        latest_revenue = latest_data['net_revenue'].sum()
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

    # dropna added to prevent sorting errors
    product_list = sorted(df_amz['product'].dropna().unique())

    selected_product = st.selectbox(
        "Filter by Product",
        options=["All Products"] + product_list,
        index=0
    )

    # Apply filter
    if selected_product != "All Products":
        df_amz = df_amz[df_amz['product'] == selected_product]

    # ===================== Chart Section =====================

    # Handle case where filtered data might be empty
    if df_amz.empty:
        st.warning("No data for this selection.")
        return

    # Filter last 30 days based on the MAX date in the data
    max_date = df_amz['date'].max()
    df_30 = df_amz[
        df_amz['date'] >= (max_date - pd.Timedelta(days=30))
    ]

    df_daily = df_30.groupby('date', as_index=False).agg({
        'net_revenue': 'sum',
        'units_sold': 'sum'
    })

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_daily['date'],
        y=df_daily['net_revenue'],
        mode='lines+markers',
        name='Revenue (INR)',
        line=dict(color='purple', width=3, shape='spline'),
        hovertemplate='Revenue: ₹%{y:,.0f}<extra></extra>'
    ))

    fig.add_trace(go.Scatter(
        x=df_daily['date'],
        y=df_daily['units_sold'],
        mode='lines+markers',
        name='Units Sold',
        line=dict(color='green', width=3, shape='spline'),
        yaxis='y2',
        hovertemplate='Units: %{y:,} units<extra></extra>'
    ))

    fig.update_layout(
        title=dict(text="📈 Amazon Sales (Last 30 Days)", font=dict(color="black", size=18)),
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