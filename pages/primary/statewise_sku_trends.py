import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# ======================================
# PAGE TITLE
# ======================================
def page():

    st.markdown("## 🗺️ Statewise Trends Overview")

    # ===================== Load Data (Universal) =====================
    @st.cache_data(ttl=600)
    def get_sales_data():
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
                return pd.DataFrame()

            # Create Engine & Fetch Data
            engine = create_engine(db_url)
            with engine.connect() as conn:
                query = text("SELECT * FROM femisafe_sales;")
                df = pd.read_sql(query, conn)
            return df
            
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    df = get_sales_data()
    
    if df.empty:
        st.warning("No sales data available.")
        return

    # Normalize data
    df["channels"] = df["channels"].str.strip().str.title()
    df["state"] = df["state"].str.strip().str.title()

    # ===================== Filter Options =====================
    channels = sorted(df["channels"].dropna().unique().tolist())
    products = sorted(df["products"].dropna().unique().tolist())
    months = sorted(df["month"].dropna().unique().tolist())

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_channel = st.selectbox("🛒 Select Channel", options=["All"] + channels)

    with col2:
        selected_product = st.selectbox("📦 Select Product", options=["All"] + products)

    with col3:
        selected_month = st.selectbox("🗓️ Select Month", options=["All"] + months)

    # ===================== Apply Filters =====================
    df_filtered = df.copy()

    if selected_channel != "All":
        df_filtered = df_filtered[df_filtered["channels"] == selected_channel]

    if selected_product != "All":
        df_filtered = df_filtered[df_filtered["products"] == selected_product]

    if selected_month != "All":
        df_filtered = df_filtered[df_filtered["month"] == selected_month]

    # ===================== Grouped Summary =====================
    if df_filtered.empty:
        st.warning("No data found for the selected filters.")
        return

    summary = (
        df_filtered.groupby("state", as_index=False)
        .agg({
            "sku_units": "sum",
            "revenue": "sum"
        })
        .sort_values("revenue", ascending=False)
    )

    # Revenue contribution percentage
    total_revenue = summary["revenue"].sum()
    if total_revenue > 0:
        summary["revenue_%"] = (summary["revenue"] / total_revenue * 100).round(2)
    else:
        summary["revenue_%"] = 0.0

    summary = summary.rename(columns={
        "state": "State",
        "sku_units": "Units Sold",
        "revenue": "Revenue",
        "revenue_%": "Revenue_%"
    })

    # Add Total row
    total_row = pd.DataFrame({
        "State": ["Total"],
        "Units Sold": [summary["Units Sold"].sum()],
        "Revenue": [summary["Revenue"].sum()],
        "Revenue_%": [100.00]
    })

    summary = pd.concat([summary, total_row], ignore_index=True)

    # ===================== Display Table =====================
    st.markdown("### 📈 Statewise Performance Summary")

    st.dataframe(
        summary.style.format({
            "Units Sold": "{:,.0f}",
            "Revenue": "₹{:,.2f}",
            "Revenue_%": "{:.2f}%"
        }),
        use_container_width=True
    )