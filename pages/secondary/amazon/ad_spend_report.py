import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import timedelta

# ---------------------------------------------------------
# DB FETCH
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def get_amazon_data():
    conn = psycopg2.connect(
        dbname="femisafe_test_db",
        user="ayish",
        password="ajtp@511Db",
        host="localhost",
        port="5432"
    )

    sales_q = """
        SELECT
            date,
            product,
            net_revenue,
            units_sold
        FROM femisafe_amazon_salesdata;
    """

    ads_q = """
        SELECT
            date,
            product,
            spend_inr
        FROM femisafe_amazon_addata;
    """

    sales = pd.read_sql(sales_q, conn)
    ads = pd.read_sql(ads_q, conn)

    conn.close()

    sales["date"] = pd.to_datetime(sales["date"])
    ads["date"] = pd.to_datetime(ads["date"])

    return sales, ads


# ---------------------------------------------------------
# PAGE
# ---------------------------------------------------------
def page():

    st.markdown("### 📊 Amazon Day-wise Sales vs Ads")

    sales, ads = get_amazon_data()

    # ---------------------------------------------------------
    # DATE RANGE FILTER (needed before product list)
    # ---------------------------------------------------------
    col1, col2 = st.columns(2)

    with col2:
        range_label = st.selectbox(
            "Date Range",
            ["Last 7 Days", "Last 14 Days", "Last 30 Days", "Last 60 Days", "Last 90 Days"]
        )

    days_map = {
        "Last 7 Days": 7,
        "Last 14 Days": 14,
        "Last 30 Days": 30,
        "Last 60 Days": 60,
        "Last 90 Days": 90
    }

    end_date = max(sales["date"].max(), ads["date"].max())
    start_date = end_date - timedelta(days=days_map[range_label])

    # ---------------------------------------------------------
    # FILTER ADS FIRST → PRODUCTS WITH DAILY SPEND ≥ 50
    # ---------------------------------------------------------
    ads_range = ads[
        (ads["date"] >= start_date) &
        (ads["date"] <= end_date)
    ]

    ads_daily = (
        ads_range
        .groupby(["date", "product"], as_index=False)
        .agg(daily_spend=("spend_inr", "sum"))
    )

    valid_products = (
        ads_daily[ads_daily["daily_spend"] >= 50]
        ["product"]
        .dropna()
        .unique()
        .tolist()
    )

    # ---------------------------------------------------------
    # PRODUCT FILTER (only valid products)
    # ---------------------------------------------------------
    with col1:
        product = st.selectbox(
            "Select Product",
            ["All"] + sorted(valid_products)
        )

    # ---------------------------------------------------------
    # APPLY FILTERS
    # ---------------------------------------------------------
    sales_f = sales[
        (sales["date"] >= start_date) &
        (sales["date"] <= end_date)
    ]

    ads_f = ads_range.copy()

    if product != "All":
        sales_f = sales_f[sales_f["product"] == product]
        ads_f = ads_f[ads_f["product"] == product]


    # ---------------------------------------------------------
    # DAY FIELDS
    # ---------------------------------------------------------
    for df in [sales_f, ads_f]:
        df["day_name"] = df["date"].dt.day_name()
        df["day_num"] = (df["date"].dt.weekday + 1) % 7

    # ---------------------------------------------------------
    # AGGREGATION (DATEWISE)
    # ---------------------------------------------------------
    sales_agg = (
        sales_f
        .groupby("date")
        .agg(
            sales_revenue=("net_revenue", "sum"),
            units=("units_sold", "sum")
        )
        .reset_index()
    )

    ads_agg = (
        ads_f
        .groupby("date")
        .agg(
            ad_spend=("spend_inr", "sum")
        )
        .reset_index()
    )

    merged = sales_agg.merge(
        ads_agg,
        on="date",
        how="left"
    ).fillna(0)

    merged = merged.sort_values("date")

    # ---------------------------------------------------------
    # RESHAPE FOR CLUSTERED BAR
    # ---------------------------------------------------------
    chart_df = pd.melt(
        merged,
        id_vars=["date", "units"],
        value_vars=["sales_revenue", "ad_spend"],
        var_name="metric",
        value_name="value"
    )

    chart_df["metric"] = chart_df["metric"].map({
        "sales_revenue": "Sales",
        "ad_spend": "Ads"
    })

    # ---------------------------------------------------------
    # CHART
    # ---------------------------------------------------------
    fig = px.bar(
        chart_df,
        x="date",
        y="value",
        color="metric",
        barmode="group",
        text=chart_df.apply(
            lambda x: f'₹{x["value"]:,.0f}',
            axis=1
        ),
        category_orders={
        "metric": ["Ads", "Sales"] 
        },
        labels={
            "date": "Date",
            "value": "Amount (₹)",
            "metric": ""
        }
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False
    )

    fig.update_layout(
        height=520,
        bargap=0.25,
        legend_title="",
        yaxis_tickformat=",.0f",
        xaxis_tickformat="%b %d"   # Dec 01, Dec 02 style
    )

    st.plotly_chart(fig, use_container_width=True)
