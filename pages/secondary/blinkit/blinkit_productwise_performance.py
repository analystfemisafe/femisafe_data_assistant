import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sqlalchemy import text

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine(): return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 🚀 OPTIMIZED DATA LOADER (ALL CHANNELS)
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def get_combined_data():
    engine = get_db_engine()
    if not engine: return pd.DataFrame()

    dfs = []
    
    # 1. BLINKIT FETCH
    try:
        with engine.connect() as conn:
            df_b = pd.read_sql(text("""
                SELECT order_date, COALESCE(product_name, product) AS product, sku, quantity AS units_sold, net_revenue AS revenue 
                FROM femisafe_blinkit_salesdata
            """), conn)
            df_b['channel'] = 'Blinkit'
            dfs.append(df_b)
    except Exception: pass # Skip if table missing

    # 2. SHOPIFY FETCH
    try:
        with engine.connect() as conn:
            df_s = pd.read_sql(text("""
                SELECT order_date, COALESCE(product, product_title_at_time_of_sale) AS product, sku, units_sold, revenue 
                FROM femisafe_shopify_salesdata
            """), conn)
            df_s['channel'] = 'Shopify'
            dfs.append(df_s)
    except Exception: pass

    # 3. AMAZON FETCH
    try:
        with engine.connect() as conn:
            df_a = pd.read_sql(text("""
                SELECT date AS order_date, COALESCE(product, title) AS product, sku, units_sold, COALESCE(net_revenue, gross_revenue) AS revenue 
                FROM femisafe_amazon_salesdata
            """), conn)
            df_a['channel'] = 'Amazon'
            dfs.append(df_a)
    except Exception: pass

    if not dfs: return pd.DataFrame()

    # Combine all data
    df = pd.concat(dfs, ignore_index=True)
    if df.empty: return df

    # =========================================================
    # ⚡ FAST CLEANING & OPTIMIZATION
    # =========================================================
    
    # 1. Vectorized Number Cleaning (Fastest method)
    for col in ['units_sold', 'revenue']:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(r'[₹,]', '', regex=True),
            errors='coerce'
        ).fillna(0)

    # 2. Optimize Types (Memory Savings)
    df['units_sold'] = df['units_sold'].astype('int32')
    df['revenue'] = df['revenue'].astype('float32')

    # 3. Optimize Text to Categories (Instant Filtering)
    df['channel'] = df['channel'].astype('category')
    df['product'] = df['product'].fillna("Unknown").astype(str).str.strip().astype('category')
    
    # 4. Fast Date Parsing (dayfirst=True fixes date flipping)
    df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')
    df.dropna(subset=['order_date'], inplace=True)
    
    # 5. Derived Columns
    df["date_only"] = df["order_date"].dt.date
    df["month"] = df["order_date"].dt.strftime("%B").astype('category')

    return df

# ===========================================================
# PAGE
# ===========================================================
def page():
    st.title("📈 Product Wise Trend Dashboard (Optimized)")

    df = get_combined_data()

    if df.empty:
        st.warning("No data available from any channel.")
        return

    # ===================== Filters =====================
    col1, col2, col3 = st.columns(3)

    # Convert categories to list for sorting in multiselect
    months = sorted(list(df["month"].unique()))
    channels = sorted(list(df["channel"].unique()))
    products = sorted(list(df["product"].unique()))

    selected_months = col1.multiselect("Select Month(s)", months, default=months)
    selected_channels = col2.multiselect("Select Channel(s)", channels, default=channels)
    selected_products = col3.multiselect("Select Product(s)", products, default=products)

    # Filtering on Categories is extremely fast
    filtered = df[
        (df["month"].isin(selected_months)) &
        (df["channel"].isin(selected_channels)) &
        (df["product"].isin(selected_products))
    ]

    if filtered.empty:
        st.warning("No data for selected filters.")
        return

    # ===================== Aggregation =====================
    # observed=True speeds up groupby on Categorical data
    agg = (
        filtered.groupby(["date_only", "channel"], observed=True, as_index=False)
        .agg({"units_sold": "sum", "revenue": "sum"})
        .sort_values("date_only")
    )

    # ===================== Plot =====================
    fig = go.Figure()
    colors = {"Amazon": "purple", "Shopify": "green", "Blinkit": "#1f77b4"}

    for channel in selected_channels:
        ch = agg[agg["channel"] == channel]
        if ch.empty: continue
            
        fig.add_trace(
            go.Bar(
                x=ch["date_only"],
                y=ch["units_sold"],
                name=f"{channel} Units",
                marker_color=colors.get(channel, "gray"),
                customdata=np.stack((ch["revenue"].values,), axis=-1),
                hovertemplate=(
                    "<b>" + channel + "</b><br>"
                    "%{x}<br>"
                    "Units: %{y}<br>"
                    "Revenue: ₹%{customdata[0]:,.0f}<extra></extra>"
                )
            )
        )

    fig.update_layout(
        barmode="group",
        title="📦 Product-wise Units Trend (Revenue on hover)",
        height=520,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig, use_container_width=True)

    # ===================== Table =====================
    st.subheader("📋 Detailed Data")

    table_df = filtered[["date_only", "channel", "product", "units_sold", "revenue"]].sort_values(
        ["date_only", "channel", "product"]
    )

    st.dataframe(
        table_df.style.format({
            "units_sold": "{:,.0f}",
            "revenue": "₹{:,.2f}"
        }),
        use_container_width=True,
        height=450
    )

# For direct running
if __name__ == "__main__":
    page()