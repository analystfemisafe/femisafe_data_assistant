import streamlit as st
import pandas as pd
import psycopg2
import numpy as np
import plotly.graph_objects as go

def page():
    st.title("📈 Product Wise Trend Dashboard")

    # ---------- DB Connection Helper ----------
    def db_connect():
        return psycopg2.connect(
            dbname="femisafe_test_db",
            user="ayish",
            password="ajtp@511Db",
            host="localhost",
            port="5432"
        )

    # ---------- Blinkit ----------
    @st.cache_data(ttl=600)
    def get_blinkit_data():
        conn = db_connect()
        query = """
            SELECT
                order_date,
                COALESCE(product_name, product) AS product,
                sku,
                quantity AS units_sold,
                net_revenue AS revenue
            FROM femisafe_blinkit_salesdata;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        df["channel"] = "Blinkit"
        return df

    # ---------- Shopify ----------
    @st.cache_data(ttl=600)
    def get_shopify_data():
        conn = db_connect()
        query = """
            SELECT
                order_date,
                COALESCE(product, product_title_at_time_of_sale) AS product,
                sku,
                units_sold,
                revenue
            FROM femisafe_shopify_salesdata;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        df["channel"] = "Shopify"
        return df

    # ---------- Amazon ----------
    @st.cache_data(ttl=600)
    def get_amazon_data():
        conn = db_connect()
        query = """
            SELECT
                date,
                COALESCE(product, title) AS product,
                sku,
                units_sold,
                COALESCE(net_revenue, gross_revenue) AS revenue
            FROM femisafe_amazon_salesdata;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        df = df.rename(columns={"date": "order_date"})
        df["channel"] = "Amazon"
        return df

    # ---------- Load All ----------
    df_blink = get_blinkit_data()
    df_shop  = get_shopify_data()
    df_amz   = get_amazon_data()

    # ---------- Combine ----------
    df = pd.concat([df_blink, df_shop, df_amz], ignore_index=True)

    # ---------- Clean ----------
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df = df[df["order_date"].notna()]       # Keep valid dates only

    df["product"] = df["product"].astype(str).str.strip()
    df["sku"] = df["sku"].astype(str).str.strip()

    df["units_sold"] = pd.to_numeric(df["units_sold"], errors="coerce").fillna(0)
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0.0)

    df["date_only"] = df["order_date"].dt.date
    df["month"] = df["order_date"].dt.strftime("%B")

    # ---------- Filters ----------
    col1, col2, col3 = st.columns(3)

    months = sorted(df["month"].unique().tolist())
    channels = sorted(df["channel"].unique().tolist())
    products = sorted(df["product"].unique().tolist())

    selected_months = col1.multiselect("Select Month(s)", months, default=months)
    selected_channels = col2.multiselect("Select Channel(s)", channels, default=channels)
    selected_products = col3.multiselect("Select Product(s)", products, default=products)

    filtered = df[
        (df["month"].isin(selected_months)) &
        (df["channel"].isin(selected_channels)) &
        (df["product"].isin(selected_products))
    ]

    if filtered.empty:
        st.warning("No data for selected filters.")
        return

    # ---------- Aggregation ----------
    agg = (
        filtered.groupby(["date_only", "channel"], as_index=False)
        .agg({"units_sold": "sum", "revenue": "sum"})
        .sort_values("date_only")
    )

    # ---------- Plot ----------
    fig = go.Figure()
    colors = {"Amazon": "purple", "Shopify": "green", "Blinkit": "#1f77b4"}

    for channel in selected_channels:
        ch = agg[agg["channel"] == channel]
        fig.add_trace(
            go.Bar(
                x=ch["date_only"],
                y=ch["units_sold"],
                name=f"{channel} Units",
                marker_color=colors.get(channel),
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
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)

    # ---------- Table ----------
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
