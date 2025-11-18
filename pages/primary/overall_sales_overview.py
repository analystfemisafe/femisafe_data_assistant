import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go

# ===========================================================
# PAGE: PRIMARY → OVERALL SALES OVERVIEW
# ===========================================================

def page():

    st.title("📊 Overall Sales Overview")

    # Get cleaned data from main utility
    from utils.data_loader import get_data
    df = get_data()

    df = df.sort_values('month')

    if len(df) < 1:
        st.warning("No data available.")
        return

    total_revenue = df['revenue'].sum()
    total_units = df['units'].sum()

    oct_data = df[df['month'].str.lower() == 'october']
    october_revenue = oct_data['revenue'].sum()
    october_units = oct_data['units'].sum()

    month_name = "October"

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

    with col1:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">₹{october_revenue:,.0f}</p>
            <p style="{units_style}">{int(october_units):,} units</p>
            <p style="{label_style}">{month_name} Revenue</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">₹{total_revenue:,.0f}</p>
            <p style="{units_style}">{int(total_units):,} units</p>
            <p style="{label_style}">Total Revenue (All Months)</p>
        </div>
        """, unsafe_allow_html=True)

    # -----------------------------------------
    # CHART SECTION
    # -----------------------------------------

    # Connect to database
    conn = psycopg2.connect(
        dbname="femisafe_test_db",
        user="ayish",
        password="ajtp@511Db",
        host="localhost",
        port="5432"
    )

    df_sales = pd.read_sql("SELECT * FROM femisafe_sales", conn)
    conn.close()

    df_sales.columns = df_sales.columns.str.strip().str.lower()
    df_sales['order_date'] = pd.to_datetime(df_sales['order_date'], errors='coerce')

    # Find latest month
    latest_date = df_sales['order_date'].max()
    latest_month = latest_date.month

    # Filter financial year Apr → latest month
    if latest_month >= 4:
        df_sales = df_sales[df_sales['order_date'].dt.month.between(4, latest_month)]
    else:
        df_sales = df_sales[
            (df_sales['order_date'].dt.month >= 4) |
            (df_sales['order_date'].dt.month <= latest_month)
        ]

    # Group by month
    df_monthly = df_sales.groupby('month', as_index=False).agg({
        'revenue': 'sum',
        'sku_units': 'sum'
    })

    # Proper month order
    month_map = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }

    if latest_month >= 4:
        month_order = [month_map[m] for m in range(4, latest_month + 1)]
    else:
        month_order = [month_map[m] for m in range(4, 13)] + [month_map[m] for m in range(1, latest_month + 1)]

    df_monthly['month'] = pd.Categorical(df_monthly['month'], categories=month_order, ordered=True)
    df_monthly = df_monthly.sort_values('month')

    # Plotly chart
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_monthly['month'],
        y=df_monthly['revenue'],
        mode='lines+markers',
        name='Net Sales (INR)',
        line=dict(color='purple', width=3, shape='spline'),
        hovertemplate='%{x}<br>Sales (₹): %{y:,.0f}<extra></extra>'
    ))

    fig.add_trace(go.Scatter(
        x=df_monthly['month'],
        y=df_monthly['sku_units'],
        mode='lines+markers',
        name='Units Sold',
        line=dict(color='green', width=3, shape='spline'),
        yaxis='y2',
        hovertemplate='%{x}<br>Units: %{y:,}<extra></extra>'
    ))

    fig.update_layout(
        title=f"📈 Month-wise Sales Overview (Apr–{month_map[latest_month]})",
        xaxis=dict(title="Month"),
        yaxis=dict(title="Revenue (₹)"),
        yaxis2=dict(title="Units Sold", overlaying="y", side="right"),
        template="plotly_white",
        height=450
    )

    st.plotly_chart(fig, use_container_width=True)
