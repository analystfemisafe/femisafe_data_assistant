import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go

def page():

    st.title("📊 Overall Sales Overview")

    # -------------------------------
    # LOAD AGGREGATED DATA (UNCHANGED)
    # -------------------------------
    from utils.data_loader import get_data
    df = get_data()

    if len(df) < 1:
        st.warning("No data available.")
        return

    total_revenue = df['revenue'].sum()
    total_units = df['units'].sum()

    # -------------------------------
    # LOAD RAW DATA FOR LATEST MONTH
    # -------------------------------
    conn = psycopg2.connect(
        dbname="femisafe_test_db",
        user="ayish",
        password="ajtp@511Db",
        host="localhost",
        port="5432"
    )

    df_sales = pd.read_sql(
        "SELECT revenue, sku_units, order_date FROM femisafe_sales",
        conn
    )
    conn.close()

    df_sales['order_date'] = pd.to_datetime(df_sales['order_date'], errors='coerce')

    latest_date = df_sales['order_date'].max()
    latest_year = latest_date.year
    latest_month = latest_date.month
    month_name = latest_date.strftime("%B")

    latest_month_df = df_sales[
        (df_sales['order_date'].dt.year == latest_year) &
        (df_sales['order_date'].dt.month == latest_month)
    ]

    latest_month_revenue = latest_month_df['revenue'].sum()
    latest_month_units = latest_month_df['sku_units'].sum()

    # -----------------------------------------
    # CARD STYLES
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

    # -------------------------------
    # CARD 1 → LATEST MONTH
    # -------------------------------
    with col1:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">₹{latest_month_revenue:,.0f}</p>
            <p style="{units_style}">{int(latest_month_units):,} units</p>
            <p style="{label_style}">{month_name} Revenue</p>
        </div>
        """, unsafe_allow_html=True)

    # -------------------------------
    # CARD 2 → TOTAL
    # -------------------------------
    with col2:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">₹{total_revenue:,.0f}</p>
            <p style="{units_style}">{int(total_units):,} units</p>
            <p style="{label_style}">Total Revenue (All Months)</p>
        </div>
        """, unsafe_allow_html=True)

    # -----------------------------------------
    # CHART SECTION (ONLY THIS IS MODIFIED)
    # -----------------------------------------
    df_sales = pd.read_sql(
        "SELECT * FROM femisafe_sales",
        psycopg2.connect(
            dbname="femisafe_test_db",
            user="ayish",
            password="ajtp@511Db",
            host="localhost",
            port="5432"
        )
    )

    df_sales.columns = df_sales.columns.str.strip().str.lower()
    df_sales['order_date'] = pd.to_datetime(df_sales['order_date'], errors='coerce')

    latest_date = df_sales['order_date'].max()
    latest_month = latest_date.month

    if latest_month >= 4:
        df_sales = df_sales[df_sales['order_date'].dt.month.between(4, latest_month)]
    else:
        df_sales = df_sales[
            (df_sales['order_date'].dt.month >= 4) |
            (df_sales['order_date'].dt.month <= latest_month)
        ]

    df_monthly = df_sales.groupby('month', as_index=False).agg({
        'revenue': 'sum',
        'sku_units': 'sum'
    })

    month_map = {
        1:'January',2:'February',3:'March',4:'April',
        5:'May',6:'June',7:'July',8:'August',
        9:'September',10:'October',11:'November',12:'December'
    }

    month_order = (
        [month_map[m] for m in range(4, latest_month + 1)]
        if latest_month >= 4
        else [month_map[m] for m in range(4, 13)] +
             [month_map[m] for m in range(1, latest_month + 1)]
    )

    df_monthly['month'] = pd.Categorical(
        df_monthly['month'],
        categories=month_order,
        ordered=True
    )
    df_monthly = df_monthly.sort_values('month')

    # -------------------------------
    # SMOOTH LINE CHART (FINAL FIX)
    # -------------------------------
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
        y=df_monthly['sku_units'],
        mode='lines+markers',
        name='Units Sold',
        line=dict(color='green', shape='spline'),
        yaxis='y2',
        hovertemplate='Units: %{y:.0f} units<extra></extra>'
    ))

    fig.update_layout(
        title=f"📈 Month-wise Sales Overview (Apr–{month_map[latest_month]})",
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
