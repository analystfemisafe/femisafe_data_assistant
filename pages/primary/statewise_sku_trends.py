import streamlit as st
import pandas as pd
import psycopg2

# ======================================
# PAGE TITLE
# ======================================
def page():

    st.markdown("## 🗺️ Statewise Trends Overview")

    # ===================== Load Data =====================
    @st.cache_data(ttl=600)
    def get_sales_data():
        conn = psycopg2.connect(
            host="localhost",
            database="femisafe_test_db",
            user="ayish",
            password="ajtp@511Db"
        )
        query = "SELECT * FROM femisafe_sales;"
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    df = get_sales_data()
    df["channels"] = df["channels"].str.strip().str.title()

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

    # Normalize state column
    df_filtered["state"] = df_filtered["state"].str.strip().str.title()

    # ===================== Grouped Summary =====================
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
    summary["revenue_%"] = (summary["revenue"] / total_revenue * 100).round(2)

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
