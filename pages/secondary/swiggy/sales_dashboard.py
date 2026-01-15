# ===========================================================
# PAGE: SWIGGY → SALES DASHBOARD
# ===========================================================

import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go

def page():

    st.title("🛵 Swiggy Sales Dashboard")

    # ===================== Fetch Swiggy Data =====================
    @st.cache_data
    def get_swiggy_data():
        conn = psycopg2.connect(
            dbname="femisafe_test_db",
            user="ayish",
            password="ajtp@511Db",
            host="localhost",
            port="5432"
        )
        query = """
            SELECT 
                ordered_date,
                sku,
                product,
                units_sold,
                city,
                area_name,
                l1_category,
                l2_category,
                l3_category,
                month
            FROM femisafe_swiggy_salesdata;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    # Load data
    df = get_swiggy_data()
    df['ordered_date'] = pd.to_datetime(df['ordered_date'], errors='coerce')

    # KPI calculations
    total_units = df['units_sold'].sum()

    latest_month = df['ordered_date'].max().strftime('%B')
    latest_data = df[df['month'] == latest_month]

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

    # Latest month KPI
    with col1:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">{int(latest_units):,}</p>
            <p style="{units_style}">units</p>
            <p style="{label_style}">{latest_month} Units Sold</p>
        </div>
        """, unsafe_allow_html=True)

    # Total units
    with col2:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">{int(total_units):,}</p>
            <p style="{units_style}">units</p>
            <p style="{label_style}">Total Units Sold (All Months)</p>
        </div>
        """, unsafe_allow_html=True)

    # ===================== Units Chart: Last 30 Days =====================

    df_30 = df[
        df['ordered_date'] >= (df['ordered_date'].max() - pd.Timedelta(days=30))
    ]

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
