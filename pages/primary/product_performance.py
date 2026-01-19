import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

def page():

    st.markdown("### 💰 Product Performance Summary")

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
                query = text("SELECT * FROM femisafe_sales")
                df = pd.read_sql(query, conn)
            return df
            
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    df = get_sales_data()

    if df.empty:
        st.warning("⚠️ No data found in 'femisafe_sales'.")
        return

    # Data Cleaning: Normalize Strings
    if "channels" in df.columns:
        df["channels"] = df["channels"].astype(str).str.strip().str.title()
    
    if "state" in df.columns:
        df["state"] = df["state"].astype(str).str.strip().str.title()

    if "products" in df.columns:
        df["products"] = df["products"].astype(str).str.strip()

    # Data Cleaning: Ensure Numerics
    for col in ["sku_units", "revenue"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # ===================== Filter Setup =====================
    # FIX: added .dropna() to remove None values before sorting
    channels = sorted(df["channels"].dropna().unique().tolist()) if "channels" in df.columns else []
    states = sorted(df["state"].dropna().unique().tolist()) if "state" in df.columns else []
    months = sorted(df["month"].dropna().unique().tolist()) if "month" in df.columns else []

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_channel = st.selectbox("🛒 Select Channel", options=["All"] + channels, index=0)

    with col2:
        selected_state = st.selectbox("📍 Select State", options=["All"] + states, index=0)

    with col3:
        selected_month = st.selectbox("🗓️ Select Month", options=["All"] + months, index=0)

    # ===================== Apply Filters =====================
    df_filtered = df.copy()

    if selected_channel != "All" and "channels" in df.columns:
        df_filtered = df_filtered[df_filtered["channels"] == selected_channel]

    if selected_state != "All" and "state" in df.columns:
        df_filtered = df_filtered[df_filtered["state"] == selected_state]

    if selected_month != "All" and "month" in df.columns:
        df_filtered = df_filtered[df_filtered["month"] == selected_month]

    # ===================== Productwise Summary =====================
    if "products" in df_filtered.columns:
        summary = (
            df_filtered.groupby("products", as_index=False)
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
            })
        )
    else:
        st.error("Column 'products' is missing from the database.")