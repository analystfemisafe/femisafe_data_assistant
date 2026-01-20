import os
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta
from sqlalchemy import create_engine, text

# ---------------------------------------------------------
# DB FETCH (Universal Connection)
# ---------------------------------------------------------
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
            return pd.DataFrame(), pd.DataFrame()

        # Define Queries
        sales_q = """
            SELECT
                date,
                product,
                net_revenue,
                units_sold
            FROM femisafe_amazon_salesdata
        """

        ads_q = """
            SELECT
                date,
                product,
                spend_inr
            FROM femisafe_amazon_addata
        """

        # Create Engine & Fetch Data
        engine = create_engine(db_url)
        with engine.connect() as conn:
            sales = pd.read_sql(text(sales_q), conn)
            ads = pd.read_sql(text(ads_q), conn)

        # Process Dates
        if not sales.empty:
            sales["date"] = pd.to_datetime(sales["date"])
        
        if not ads.empty:
            ads["date"] = pd.to_datetime(ads["date"])

        return sales, ads

    except Exception as e:
        st.error(f"⚠️ Database Connection Failed: {e}")
        return pd.DataFrame(), pd.DataFrame()


# ---------------------------------------------------------
# PAGE
# ---------------------------------------------------------
def page():

    st.markdown("### 📊 Amazon Day-wise Sales vs Ads")

    sales, ads = get_amazon_data()

    if sales.empty or ads.empty:
        st.warning("No data available for Sales or Ads.")
        return

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

    # Ensure we have valid dates to calculate range
    max_sales_date = sales["date"].max() if not sales.empty else pd.Timestamp.now()
    max_ads_date = ads["date"].max() if not ads.empty else pd.Timestamp.now()
    
    end_date = max(max_sales_date, max_ads_date)
    start_date = end_date - timedelta(days=days_map[range_label])

    # ---------------------------------------------------------
    # FILTER ADS FIRST → PRODUCTS WITH DAILY SPEND ≥ 50
    # ---------------------------------------------------------
    ads_range = ads[
        (ads["date"] >= start_date) &
        (ads["date"] <= end_date)
    ]

    # Handle case where ads_range might be empty
    if not ads_range.empty:
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
    else:
        valid_products = []

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
        if not df.empty:
            df["day_name"] = df["date"].dt.day_name()
            df["day_num"] = (df["date"].dt.weekday + 1) % 7

    # ---------------------------------------------------------
    # AGGREGATION (DATEWISE)
    # ---------------------------------------------------------
    if not sales_f.empty:
        sales_agg = (
            sales_f
            .groupby("date")
            .agg(
                sales_revenue=("net_revenue", "sum"),
                units=("units_sold", "sum")
            )
            .reset_index()
        )
    else:
        sales_agg = pd.DataFrame(columns=["date", "sales_revenue", "units"])

    if not ads_f.empty:
        ads_agg = (
            ads_f
            .groupby("date")
            .agg(
                ad_spend=("spend_inr", "sum")
            )
            .reset_index()
        )
    else:
        ads_agg = pd.DataFrame(columns=["date", "ad_spend"])

    merged = sales_agg.merge(
        ads_agg,
        on="date",
        how="left"
    ).fillna(0)

    if merged.empty:
        st.warning("No overlapping data found for the selected range.")
        return

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