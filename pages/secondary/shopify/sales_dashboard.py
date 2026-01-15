# ===========================================================
# PAGE: SHOPIFY → SALES DASHBOARD
# ===========================================================

import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go

def page():

    st.title("🛍️ Shopify Sales Dashboard")

    # ===================== Fetch Shopify Data =====================
    @st.cache_data
    def get_shopify_data():
        conn = psycopg2.connect(
            dbname="femisafe_test_db",
            user="ayish",
            password="ajtp@511Db",
            host="localhost",
            port="5432"
        )
        query = """
            SELECT 
                order_date,
                sku,
                product,
                units_sold,
                revenue,
                shipping_city,
                shipping_region,
                shipping_country,
                month
            FROM femisafe_shopify_salesdata;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    # Load data
    df_shopify = get_shopify_data()
    df_shopify['order_date'] = pd.to_datetime(df_shopify['order_date'], errors='coerce')

    # KPIs
    total_revenue = df_shopify['revenue'].sum()
    total_units = df_shopify['units_sold'].sum()

    latest_month = df_shopify['order_date'].max().strftime('%B')
    latest_data = df_shopify[df_shopify['month'] == latest_month]

    latest_revenue = latest_data['revenue'].sum()
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

    product_list = sorted(df_shopify['product'].dropna().unique())

    selected_product = st.selectbox(
        "Filter by Product",
        options=["All Products"] + product_list,
        index=0
    )

    # Apply filter
    if selected_product != "All Products":
        df_shopify = df_shopify[df_shopify['product'] == selected_product]

    # ===================== Chart Section: Last 30 Days =====================

    df_30 = df_shopify[
        df_shopify['order_date'] >= (df_shopify['order_date'].max() - pd.Timedelta(days=30))
    ]

    df_daily = df_30.groupby('order_date', as_index=False).agg({
        'revenue': 'sum',
        'units_sold': 'sum'
    })

    fig = go.Figure()

    # Revenue line
    fig.add_trace(go.Scatter(
        x=df_daily['order_date'],
        y=df_daily['revenue'],
        mode='lines+markers',
        name='Revenue (INR)',
        line=dict(color='purple', width=3, shape='spline'),
        hovertemplate='Revenue: ₹%{y:,.0f}<extra></extra>'
    ))

    # Units sold
    fig.add_trace(go.Scatter(
        x=df_daily['order_date'],
        y=df_daily['units_sold'],
        mode='lines+markers',
        name='Units Sold',
        line=dict(color='green', width=3, shape='spline'),
        yaxis='y2',
        hovertemplate='Units: %{y:,}<extra></extra>'
    ))

    fig.update_layout(
        title=dict(text="📈 Shopify Sales (Last 30 Days)", font=dict(color="black", size=18)),
        xaxis=dict(
            title="Date",
            tickfont=dict(color="black"),
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)",
        ),
        yaxis=dict(
            title=dict(text="Revenue (INR)", font=dict(color="purple")),
            tickfont=dict(color="purple"),
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)",
        ),
        yaxis2=dict(
            title=dict(text="Units Sold", font=dict(color="green")),
            tickfont=dict(color="green"),
            overlaying='y',
            side='right',
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
