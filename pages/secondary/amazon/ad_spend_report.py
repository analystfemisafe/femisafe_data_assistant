import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta
from sqlalchemy import text

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    # Fallback if utils folder missing
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 🚀 OPTIMIZED DATA LOADER
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def get_amazon_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame(), pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: Select only needed columns
            sales_q = text("""
                SELECT date, product, net_revenue, units_sold 
                FROM femisafe_amazon_salesdata
            """)
            ads_q = text("""
                SELECT date, product, spend_inr 
                FROM femisafe_amazon_addata
            """)

            sales = pd.read_sql(sales_q, conn)
            ads = pd.read_sql(ads_q, conn)

        # =========================================================
        # ⚡ FAST CLEANING & OPTIMIZATION
        # =========================================================

        # --- Process Sales Data ---
        if not sales.empty:
            # 1. Vectorized Number Cleaning
            sales['net_revenue'] = pd.to_numeric(
                sales['net_revenue'].astype(str).str.replace(r'[₹,]', '', regex=True), 
                errors='coerce'
            ).fillna(0)
            
            sales['units_sold'] = pd.to_numeric(
                sales['units_sold'].astype(str).str.replace(',', ''), 
                errors='coerce'
            ).fillna(0).astype('int32')

            # 2. Fast Date Parsing
            sales['date'] = pd.to_datetime(sales['date'], dayfirst=True, errors='coerce')
            sales.dropna(subset=['date'], inplace=True)

            # 3. Optimize Text to Category
            sales['product'] = sales['product'].fillna("Unknown").astype(str).str.strip().astype('category')

        # --- Process Ads Data ---
        if not ads.empty:
            # 1. Vectorized Number Cleaning
            ads['spend_inr'] = pd.to_numeric(
                ads['spend_inr'].astype(str).str.replace(r'[₹,]', '', regex=True), 
                errors='coerce'
            ).fillna(0)

            # 2. Fast Date Parsing
            ads['date'] = pd.to_datetime(ads['date'], dayfirst=True, errors='coerce')
            ads.dropna(subset=['date'], inplace=True)

            # 3. Optimize Text to Category
            ads['product'] = ads['product'].fillna("Unknown").astype(str).str.strip().astype('category')

        return sales, ads

    except Exception as e:
        st.error(f"⚠️ Database Connection Failed: {e}")
        return pd.DataFrame(), pd.DataFrame()


# ---------------------------------------------------------
# PAGE
# ---------------------------------------------------------
def page():

    st.markdown("### 📊 Amazon Day-wise Sales vs Ads (Optimized)")

    # Load Data (Instant if cached)
    sales, ads = get_amazon_data()

    if sales.empty and ads.empty:
        st.warning("No data available for Sales or Ads.")
        return

    # ---------------------------------------------------------
    # DATE RANGE FILTER
    # ---------------------------------------------------------
    col1, col2 = st.columns(2)

    with col2:
        range_label = st.selectbox(
            "Date Range",
            ["Last 7 Days", "Last 14 Days", "Last 30 Days", "Last 60 Days", "Last 90 Days"]
        )

    days_map = {
        "Last 7 Days": 7, "Last 14 Days": 14, "Last 30 Days": 30,
        "Last 60 Days": 60, "Last 90 Days": 90
    }

    # Calculate Dates
    max_sales_date = sales["date"].max() if not sales.empty else pd.Timestamp.now()
    max_ads_date = ads["date"].max() if not ads.empty else pd.Timestamp.now()
    
    end_date = max(max_sales_date, max_ads_date)
    start_date = end_date - timedelta(days=days_map[range_label])

    # ---------------------------------------------------------
    # FILTER ADS & IDENTIFY VALID PRODUCTS
    # ---------------------------------------------------------
    if not ads.empty:
        # Filter by date first (Fast)
        ads_range = ads[
            (ads["date"] >= start_date) &
            (ads["date"] <= end_date)
        ]
        
        if not ads_range.empty:
            # groupby on 'category' dtype is very fast
            ads_daily = (
                ads_range
                .groupby(["date", "product"], observed=True, as_index=False)
                .agg(daily_spend=("spend_inr", "sum"))
            )
            
            valid_products = (
                ads_daily[ads_daily["daily_spend"] >= 50]
                ["product"]
                .unique()
                .tolist()
            )
        else:
            valid_products = []
            ads_range = pd.DataFrame() # Empty structure
    else:
        valid_products = []
        ads_range = pd.DataFrame()

    # ---------------------------------------------------------
    # PRODUCT FILTER
    # ---------------------------------------------------------
    with col1:
        # Sort the product list
        product = st.selectbox(
            "Select Product",
            ["All"] + sorted(list(valid_products))
        )

    # ---------------------------------------------------------
    # APPLY FINAL FILTERS
    # ---------------------------------------------------------
    # Sales Filter
    sales_f = pd.DataFrame()
    if not sales.empty:
        sales_f = sales[
            (sales["date"] >= start_date) & 
            (sales["date"] <= end_date)
        ]
        if product != "All":
            sales_f = sales_f[sales_f["product"] == product]

    # Ads Filter (ads_range is already date-filtered)
    ads_f = ads_range.copy()
    if not ads_f.empty and product != "All":
        ads_f = ads_f[ads_f["product"] == product]

    # ---------------------------------------------------------
    # AGGREGATION
    # ---------------------------------------------------------
    # Sales Aggregation
    if not sales_f.empty:
        sales_agg = (
            sales_f
            .groupby("date", observed=True)
            .agg(
                sales_revenue=("net_revenue", "sum"),
                units=("units_sold", "sum")
            )
            .reset_index()
        )
    else:
        sales_agg = pd.DataFrame(columns=["date", "sales_revenue", "units"])

    # Ads Aggregation
    if not ads_f.empty:
        ads_agg = (
            ads_f
            .groupby("date", observed=True)
            .agg(
                ad_spend=("spend_inr", "sum")
            )
            .reset_index()
        )
    else:
        ads_agg = pd.DataFrame(columns=["date", "ad_spend"])

    # Merge
    merged = sales_agg.merge(
        ads_agg,
        on="date",
        how="outer"  # Changed to outer to show spend even if 0 sales
    ).fillna(0)

    if merged.empty:
        st.warning("No overlapping data found for the selected range.")
        return

    merged = merged.sort_values("date")

    # ---------------------------------------------------------
    # CHART PREP
    # ---------------------------------------------------------
    chart_df = pd.melt(
        merged,
        id_vars=["date"],
        value_vars=["sales_revenue", "ad_spend"],
        var_name="metric",
        value_name="value"
    )

    chart_df["metric"] = chart_df["metric"].map({
        "sales_revenue": "Sales",
        "ad_spend": "Ads"
    })

    # ---------------------------------------------------------
    # PLOTLY CHART
    # ---------------------------------------------------------
    fig = px.bar(
        chart_df,
        x="date",
        y="value",
        color="metric",
        barmode="group",
        text=chart_df.apply(lambda x: f'₹{x["value"]:,.0f}', axis=1),
        category_orders={"metric": ["Ads", "Sales"]},
        labels={"date": "Date", "value": "Amount (₹)", "metric": ""},
        color_discrete_map={"Sales": "#2ca02c", "Ads": "#d62728"} # Green for Sales, Red for Ads
    )

    fig.update_traces(textposition="outside", cliponaxis=False)

    fig.update_layout(
        height=520,
        bargap=0.25,
        legend_title="",
        yaxis_tickformat=",.0f",
        xaxis_tickformat="%b %d",
        title=f"Sales vs Ad Spend ({product})"
    )

    st.plotly_chart(fig, use_container_width=True)