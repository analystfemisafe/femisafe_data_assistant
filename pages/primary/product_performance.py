import streamlit as st
import pandas as pd
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

# ======================================
# 🚀 OPTIMIZED DATA LOADER
# ======================================
@st.cache_data(ttl=900)
def get_sales_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: Select only needed columns
            query = text("SELECT channels, state, month, products, sku_units, revenue FROM femisafe_sales")
            df = pd.read_sql(query, conn)

        if df.empty: return df

        # =========================================================
        # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
        # =========================================================

        # 1. Fast Vectorized Cleaning (Revenue & Units)
        # Regex removes ₹, commas, spaces instantly
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

        # 2. Optimize Text to Category (Instant Filtering & Grouping)
        # Text columns used in filters/groupby should be categories
        for col in ['channels', 'state', 'products', 'month']:
            if col in df.columns:
                df[col] = df[col].fillna("Unknown").astype(str).str.strip().str.title().astype('category')
        
        return df
        
    except Exception as e:
        st.error(f"⚠️ Database Connection Failed: {e}")
        return pd.DataFrame()

# ======================================
# PAGE FUNCTION
# ======================================
def page():

    st.markdown("### 💰 Product Performance Summary (Optimized)")

    # Load Data (Instant if cached)
    df = get_sales_data()

    if df.empty:
        st.warning("⚠️ No data found in 'femisafe_sales'.")
        return

    # ===================== Filter Setup =====================
    # Getting unique values from Categories is extremely fast
    channels = sorted(list(df["channels"].unique())) if "channels" in df.columns else []
    states = sorted(list(df["state"].unique())) if "state" in df.columns else []
    months = sorted(list(df["month"].unique())) if "month" in df.columns else []

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_channel = st.selectbox("🛒 Select Channel", options=["All"] + channels, index=0)

    with col2:
        selected_state = st.selectbox("📍 Select State", options=["All"] + states, index=0)

    with col3:
        selected_month = st.selectbox("🗓️ Select Month", options=["All"] + months, index=0)

    # ===================== Apply Filters =====================
    # Filtering on Category types is 100x faster than strings
    df_filtered = df.copy()

    if selected_channel != "All" and "channels" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["channels"] == selected_channel]

    if selected_state != "All" and "state" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["state"] == selected_state]

    if selected_month != "All" and "month" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["month"] == selected_month]

    if df_filtered.empty:
        st.warning("No data found for these filters.")
        return

    # ===================== Productwise Summary =====================
    if "products" in df_filtered.columns:
        # observed=True speeds up groupby on categories
        summary = (
            df_filtered.groupby("products", observed=True, as_index=False)
            .agg({
                "sku_units": "sum",
                "revenue": "sum"
            })
            .sort_values(by="revenue", ascending=False)
        )

        # Calculate revenue percentage
        total_revenue = summary["revenue"].sum()
        if total_revenue > 0:
            summary["revenue_%"] = (summary["revenue"] / total_revenue) * 100
        else:
            summary["revenue_%"] = 0.0

        # Rename columns
        summary = summary.rename(columns={
            "products": "Products",
            "sku_units": "Units Sold",
            "revenue": "Revenue",
            "revenue_%": "Revenue_%"
        })

        # Total row
        total_row = pd.DataFrame({
            "Products": ["Total"],
            "Units Sold": [summary["Units Sold"].sum()],
            "Revenue": [summary["Revenue"].sum()],
            "Revenue_%": [100.00]
        })

        summary = pd.concat([summary, total_row], ignore_index=True)

        # ===================== Display Table =====================
        st.dataframe(
            summary.style.format({
                "Units Sold": "{:,.0f}",
                "Revenue": "₹{:,.2f}",
                "Revenue_%": "{:.2f}%"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.error("Column 'products' is missing from the database.")