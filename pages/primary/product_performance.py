import streamlit as st
import pandas as pd
import psycopg2


def page():

    st.markdown("### 💰 Product Performance Summary")

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

    # ===================== Filter Setup =====================
    channels = sorted(df["channels"].dropna().unique().tolist())
    states = sorted(df["state"].dropna().unique().tolist())
    months = sorted(df["month"].dropna().unique().tolist())

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_channel = st.selectbox("🛒 Select Channel", options=["All"] + channels, index=0)

    with col2:
        selected_state = st.selectbox("📍 Select State", options=["All"] + states, index=0)

    with col3:
        selected_month = st.selectbox("🗓️ Select Month", options=["All"] + months, index=0)

    # ===================== Apply Filters =====================
    df_filtered = df.copy()

    if selected_channel != "All":
        df_filtered = df_filtered[df_filtered["channels"] == selected_channel]

    if selected_state != "All":
        df_filtered = df_filtered[df_filtered["state"] == selected_state]

    if selected_month != "All":
        df_filtered = df_filtered[df_filtered["month"] == selected_month]

    # ===================== Productwise Summary =====================
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
    summary["revenue_%"] = (summary["revenue"] / total_revenue) * 100

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
