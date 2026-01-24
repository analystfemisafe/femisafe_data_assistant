import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import text
from datetime import datetime
from dateutil.relativedelta import relativedelta

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
def get_trend_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: 
            # 1. Use subquery to find the LATEST date in the database
            # 2. Filter for 6 months relative to THAT date (not today's date)
            # 3. This ensures the chart is never empty, even with old data
            query = text("""
                WITH MaxDate AS (
                    SELECT MAX(order_date) as max_d FROM femisafe_sales
                )
                SELECT order_date, channels, products, sku_units, revenue 
                FROM femisafe_sales, MaxDate
                WHERE order_date >= MaxDate.max_d - INTERVAL '6 months'
            """)
            df = pd.read_sql(query, conn)

        if df.empty: return df

        # =========================================================
        # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
        # =========================================================

        # 1. Fast Vectorized Cleaning
        if 'revenue' in df.columns:
            df['revenue'] = pd.to_numeric(
                df['revenue'].astype(str).str.replace(r'[₹,]', '', regex=True),
                errors='coerce'
            ).fillna(0)

        if 'sku_units' in df.columns:
            df['sku_units'] = pd.to_numeric(
                df['sku_units'].astype(str).str.replace(',', ''),
                errors='coerce'
            ).fillna(0)

        # 2. Fast Date Parsing
        df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
        df.dropna(subset=['order_date'], inplace=True)

        # 3. Optimize Text to Category
        for col in ['channels', 'products']:
            if col in df.columns:
                df[col] = df[col].fillna("Unknown").astype(str).str.strip().astype('category')

        return df

    except Exception as e:
        st.error(f"⚠️ Data Load Error: {e}")
        return pd.DataFrame()

# ===========================================================
# PAGE
# ===========================================================
def page():

    st.title("📊 Product-wise Revenue Trend")
    st.caption("Showing trend for the latest 6 months available in data")

    # Load Data (Instant if cached)
    df = get_trend_data()

    if df.empty:
        st.warning("⚠️ No data available.")
        return

    # ---------------------------------------------------------
    # 2. FILTERS
    # ---------------------------------------------------------
    
    # Categories are fast for unique values
    all_products = sorted(list(df["products"].unique()))
    if "Hot Water Bag" in all_products:
        all_products.remove("Hot Water Bag")
        
    all_channels = sorted(list(df["channels"].unique()))

    col1, col2 = st.columns(2)
    selected_products = col1.multiselect("Select Product(s)", all_products, default=all_products)
    selected_channels = col2.multiselect("Select Channel(s)", all_channels, default=all_channels)

    # Filtering on Category types is fast
    filtered = df[
        (df["products"].isin(selected_products)) &
        (df["channels"].isin(selected_channels))
    ]

    if filtered.empty:
        st.warning("No data available for the selected filters.")
        return

    # ---------------------------------------------------------
    # 3. AGGREGATION & DATE PREP
    # ---------------------------------------------------------
    
    # Calculate dynamic X-axis range based on filtered data
    latest_date = filtered["order_date"].max()
    
    # Generate list of last 6 months based on the LATEST DATE in the data
    last_6_months = [(latest_date - relativedelta(months=i)).strftime("%b %Y") for i in reversed(range(6))]

    # Create formatted month column
    filtered = filtered.copy()
    filtered["month_str"] = filtered["order_date"].dt.strftime("%b %Y")

    # Aggregate: Product x Month
    agg = filtered.groupby(["products", "month_str"], observed=True).agg({
        "sku_units": "sum",
        "revenue": "sum"
    }).reset_index()

    # ---------------------------------------------------------
    # 4. PLOT: MULTI-LINE CHART
    # ---------------------------------------------------------
    fig = go.Figure()

    if not agg.empty:
        # Create full index to ensure continuity (fill missing months with 0)
        unique_products = agg["products"].unique()
        
        full_index = pd.MultiIndex.from_product(
            [unique_products, last_6_months], 
            names=["products", "month_str"]
        )
        
        # Reindex
        agg_indexed = agg.set_index(["products", "month_str"]).reindex(full_index, fill_value=0).reset_index()

        for product in unique_products:
            prod_data = agg_indexed[agg_indexed["products"] == product]
            
            fig.add_trace(go.Scatter(
                x=prod_data["month_str"],
                y=prod_data["revenue"],
                mode="lines+markers",
                name=str(product),
                text=prod_data["sku_units"],
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>" +
                    "Month: %{x}<br>" +
                    "Revenue: ₹%{y:,.0f}<br>" +
                    "Units Sold: %{text:.0f}<extra></extra>"
                )
            ))

    fig.update_layout(
        title="📈 Revenue Trend (Last 6 Active Months)",
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