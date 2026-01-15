import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
from datetime import datetime
from dateutil.relativedelta import relativedelta

def page():
    st.title("📊 Product-wise Revenue Trend (Last 6 Months)")

    # ----------------------------
    # DATABASE CONNECTION
    # ----------------------------
    try:
        conn = psycopg2.connect(
            dbname="femisafe_test_db",
            user="ayish",
            password="ajtp@511Db",
            host="localhost",
            port="5432"
        )
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return

    # ----------------------------
    # LOAD DATA
    # ----------------------------
    @st.cache_data
    def load_data():
        query = """
            SELECT order_date,
                   month,
                   channels,
                   products,
                   sku_units,
                   revenue
            FROM public.femisafe_sales
            WHERE order_date >= current_date - interval '6 months'
        """
        return pd.read_sql(query, conn)

    df = load_data()

    if df.empty:
        st.warning("No data available for the last 6 months.")
        return

    # ----------------------------
    # FILTERS (Multi-select)
    # ----------------------------
    # Remove Hot Water Bag
    products_list = sorted([p for p in df["products"].dropna().unique() if p != "Hot Water Bag"])
    channels_list = sorted(df["channels"].dropna().unique())

    col1, col2 = st.columns(2)
    selected_products = col1.multiselect("Select Product(s)", products_list, default=products_list)
    selected_channels = col2.multiselect("Select Channel(s)", channels_list, default=channels_list)

    filtered = df[
        (df["products"].isin(selected_products)) &
        (df["channels"].isin(selected_channels))
    ]

    if filtered.empty:
        st.warning("No data available for the selected filters.")
        return

    # ----------------------------
    # GET LAST 6 MONTHS
    # ----------------------------
    latest_date = filtered["order_date"].max()
    last_6_months = [(latest_date - relativedelta(months=i)).strftime("%b %Y") for i in reversed(range(6))]

    filtered["month_str"] = pd.to_datetime(filtered["order_date"]).dt.strftime("%b %Y")

    # ----------------------------
    # AGGREGATE: Product x Month
    # ----------------------------
    agg = filtered.groupby(["products", "month_str"]).agg({
        "sku_units": "sum",
        "revenue": "sum"
    }).reset_index()

    # Ensure all months exist for each product
    all_combinations = pd.MultiIndex.from_product(
        [agg["products"].unique(), last_6_months],
        names=["products", "month_str"]
    )
    agg = agg.set_index(["products", "month_str"]).reindex(all_combinations, fill_value=0).reset_index()

    # ----------------------------
    # PLOT: Multi-line chart
    # ----------------------------
    fig = go.Figure()

    for product in agg["products"].unique():
        prod_data = agg[agg["products"] == product]
        # Ensure months are in correct order
        prod_data = prod_data.set_index("month_str").reindex(last_6_months).reset_index()
        fig.add_trace(go.Scatter(
            x=prod_data["month_str"],
            y=prod_data["revenue"],
            mode="lines+markers",
            name=product,
            text=prod_data["sku_units"],
            hovertemplate=(
                "<b>%{fullData.name}</b><br>" +
                "Month: %{x}<br>" +
                "Revenue: ₹%{y:,.0f}<br>" +
                "Units Sold: %{text:.0f}<extra></extra>"
            )
        ))

    fig.update_layout(
        title="📈 Product-wise Revenue Trend (Last 6 Months)",
        xaxis_title="Month",
        yaxis_title="Revenue (₹)",
        template="plotly_white",
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="black",
            font_size=12,
            font_color="white"
        ),
        legend=dict(title="Products")
    )

    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------
    # CLOSE CONNECTION
    # ----------------------------
    conn.close()
