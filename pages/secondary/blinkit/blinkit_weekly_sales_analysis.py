import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px

# ---------------------------------------------------------
# DB FETCH
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def get_blinkit_data():
    conn = psycopg2.connect(
        dbname="femisafe_test_db",
        user="ayish",
        password="ajtp@511Db",
        host="localhost",
        port="5432"
    )

    query = """
        SELECT
            order_date,
            order_week,
            sku,
            feeder_wh,
            net_revenue,
            quantity
        FROM femisafe_blinkit_salesdata
        WHERE order_status NOT IN ('Cancelled', 'Returned');
    """

    df = pd.read_sql(query, conn)
    conn.close()

    df["order_date"] = pd.to_datetime(df["order_date"])
    df["day_name"] = df["order_date"].dt.day_name()

    # Sunday = 0
    df["day_num"] = (df["order_date"].dt.weekday + 1) % 7

    return df


# ---------------------------------------------------------
# PAGE
# ---------------------------------------------------------
def page():

    st.markdown("### 📊 Day-wise Revenue (Week Comparison)")

    df = get_blinkit_data()

    # ---------------------------------------------------------
    # FILTERS
    # ---------------------------------------------------------
    col1, col2, col3 = st.columns(3)

    with col1:
        sku = st.selectbox(
            "Select sku",
            ["All"] + sorted(df["sku"].dropna().unique())
        )

    with col2:
        warehouse = st.selectbox(
            "Select Warehouse",
            ["All"] + sorted(df["feeder_wh"].dropna().unique())
        )

    with col3:
        week_limit = st.selectbox(
            "Number of Weeks",
            [2, 3, 4, 5, 6]
        )

    # ---------------------------------------------------------
    # APPLY FILTERS
    # ---------------------------------------------------------
    filtered = df.copy()

    if sku != "All":
        filtered = filtered[filtered["sku"] == sku]

    if warehouse != "All":
        filtered = filtered[filtered["feeder_wh"] == warehouse]

    # ---------------------------------------------------------
    # PICK LATEST N WEEKS (OLDEST → NEWEST)
    # ---------------------------------------------------------
    all_weeks = (
        filtered["order_week"]
        .dropna()
        .unique()
        .tolist()
    )

    latest_weeks = sorted(
        all_weeks,
        key=lambda x: int(x.replace("WK", ""))
    )[-week_limit:]

    filtered = filtered[filtered["order_week"].isin(latest_weeks)]

    # ---------------------------------------------------------
    # AGGREGATION
    # ---------------------------------------------------------
    agg = (
        filtered
        .groupby(["day_name", "day_num", "order_week"])
        .agg(
            revenue=("net_revenue", "sum"),
            units=("quantity", "sum")
        )
        .reset_index()
    )

    agg = agg.sort_values("day_num")

    # ---------------------------------------------------------
    # 🚨 CRITICAL FIX — CATEGORY ORDERS AT CREATION TIME
    # ---------------------------------------------------------
    fig = px.bar(
        agg,
        x="day_name",
        y="revenue",
        color="order_week",
        barmode="group",
        text="units",
        category_orders={
            "order_week": latest_weeks,   # 🔥 THIS FIXES WEEK ORDER
            "day_name": [
                "Sunday", "Monday", "Tuesday",
                "Wednesday", "Thursday", "Friday", "Saturday"
            ]
        },
        labels={
            "day_name": "Day of Week",
            "revenue": "Net Revenue",
            "order_week": "Week"
        },
        hover_data={
            "revenue": ":,.0f",
            "units": True
        }
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False
    )

    fig.update_layout(
        height=500,
        xaxis_title="Day",
        yaxis_title="Revenue",
        bargap=0.2,
        legend_title="Week",
        legend_traceorder="normal"
    )

    st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------------------------------
    # PRODUCT-WISE SUMMARY TABLE
    # (WEEK + WAREHOUSE FILTER APPLIED)
    # ---------------------------------------------------------

    # Start from FULL data
    table_source = df.copy()

    # Apply week filter
    table_source = table_source[
        table_source["order_week"].isin(latest_weeks)
    ]

    # ✅ Apply warehouse filter
    if warehouse != "All":
        table_source = table_source[
            table_source["feeder_wh"] == warehouse
        ]

    # ---------------------------------------------------------
    # AGGREGATION
    # ---------------------------------------------------------
    table_df = (
        table_source
        .groupby("sku", as_index=False)
        .agg(
            units=("quantity", "sum"),
            revenue=("net_revenue", "sum")
        )
    )

    # Total revenue
    total_revenue = table_df["revenue"].sum()

    # Revenue %
    table_df["revenue_pct"] = (
        table_df["revenue"] / total_revenue * 100
    ).round(1)

    # Sort by revenue
    table_df = table_df.sort_values("revenue", ascending=False)

    # ---------------------------------------------------------
    # ADD TOTAL ROW
    # ---------------------------------------------------------
    total_row = pd.DataFrame([{
        "sku": "GRAND TOTAL",
        "units": table_df["units"].sum(),
        "revenue": table_df["revenue"].sum(),
        "revenue_pct": 100.0
    }])

    table_df = pd.concat([table_df, total_row], ignore_index=True)

    # ---------------------------------------------------------
    # ROW HIGHLIGHTING
    # ---------------------------------------------------------
    def highlight_selected(row):
        if row["sku"] == "TOTAL":
            return ["font-weight: bold"] * len(row)
        if sku != "All" and row["sku"] == sku:
            return ["background-color: #808080"] * len(row)
        return [""] * len(row)

    styled_table = (
        table_df
        .style
        .apply(highlight_selected, axis=1)
        .format({
            "units": "{:,.0f}",
            "revenue": "₹{:,.0f}",
            "revenue_pct": "{:.1f}%"
        })
    )

    # ---------------------------------------------------------
    # DISPLAY
    # ---------------------------------------------------------
    st.markdown("### 📋 Product-wise Summary (Last Selected Weeks)")
    st.dataframe(styled_table, use_container_width=True)
