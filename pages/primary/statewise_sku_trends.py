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
                # Using the exact table name you provided
                query = text("SELECT * FROM femisafe_sales")
                df = pd.read_sql(query, conn)
            return df
            
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    df = get_sales_data()

    if df.empty:
        st.warning("⚠️ No data found in 'femisafe_sales' table.")
        return

    # Clean Channels column if it exists
    if "channels" in df.columns:
        df["channels"] = df["channels"].astype(str).str.strip().str.title()
    else:
        st.error("Column 'channels' missing in database.")
        return

    # ===================== Filter Options =====================
    channels = sorted(df["channels"].dropna().unique().tolist())
    
    # Handle missing columns gracefully
    products = sorted(df["products"].dropna().unique().tolist()) if "products" in df.columns else []
    months = sorted(df["month"].dropna().unique().tolist()) if "month" in df.columns else []

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

    if selected_product != "All" and "products" in df.columns:
        df_filtered = df_filtered[df_filtered["products"] == selected_product]

    if selected_month != "All" and "month" in df.columns:
        df_filtered = df_filtered[df_filtered["month"] == selected_month]

    # Normalize state column
    if "state" in df_filtered.columns:
        df_filtered["state"] = df_filtered["state"].astype(str).str.strip().str.title()
    else:
        st.warning("State column missing.")
        return

    # ===================== Grouped Summary =====================
    # Ensure numeric columns are actually numeric
    for col in ["sku_units", "revenue"]:
        if col in df_filtered.columns:
            df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce').fillna(0)

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
        })
    )