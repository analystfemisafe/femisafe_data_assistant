# ===========================================================
# PAGE: SECONDARY → AMAZON → SALES DASHBOARD
# ===========================================================

import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go

def page():

    st.title("🛒 Amazon Sales Dashboard")

    # ===================== Get Amazon Data =====================
    @st.cache_data
    def get_amazon_data():
        conn = psycopg2.connect(
            dbname="femisafe_test_db",
            user="ayish",
            password="ajtp@511Db",
            host="localhost",
            port="5432"
        )
        query = """
            SELECT
                date,
                sku,
                product,
                net_revenue,
                units_sold
            FROM femisafe_amazon_salesdata;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    # Load data
    df_amz = get_amazon_data()
    df_amz['date'] = pd.to_datetime(df_amz['date'], errors='coerce')
    df_amz['month'] = df_amz['date'].dt.strftime('%B')

    # KPIs
    total_revenue = df_amz['net_revenue'].sum()
    total_units = df_amz['units_sold'].sum()

    latest_month = df_amz['date'].max().strftime('%B')
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

    df_30 = df_amz[
        df_amz['date'] >= (df_amz['date'].max() - pd.Timedelta(days=30))
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
