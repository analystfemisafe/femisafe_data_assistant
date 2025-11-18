import streamlit as st
import psycopg2
import pandas as pd
import plotly.graph_objects as go


def page():

    st.markdown("### 🧭 Amazon vs Shopify — Statewise Overlap")

    # ✅ Connect to database and load fresh data
    conn = psycopg2.connect(
        dbname="femisafe_test_db",
        user="ayish",
        password="ajtp@511Db",
        host="localhost",
        port="5432"
    )
    df = pd.read_sql("SELECT * FROM femisafe_sales", conn)
    conn.close()

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()

    # Clean up channels and state names
    df["channels"] = df["channels"].str.strip().str.title()
    df["state"] = df["state"].str.strip().str.title()
    df["month"] = df["month"].str.strip().str.title()
    df["products"] = df["products"].str.strip()

    # ===================== Filters =====================
    months = sorted(df["month"].dropna().unique().tolist())
    products = sorted(df["products"].dropna().unique().tolist())
    top_options = ["Top 5", "Top 10", "Top 15", "All"]

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_month = st.selectbox("🗓️ Select Month", options=["All"] + months, index=0)
    with col2:
        selected_product = st.selectbox("📦 Select Product", options=["All"] + products, index=0)
    with col3:
        selected_top = st.selectbox("🏆 Show", options=top_options, index=1)

    # ===================== Filter Data =====================
    df_filtered = df.copy()

    if selected_month != "All":
        df_filtered = df_filtered[df_filtered["month"] == selected_month]
    if selected_product != "All":
        df_filtered = df_filtered[df_filtered["products"] == selected_product]

    # Keep only Amazon and Shopify
    df_filtered = df_filtered[df_filtered["channels"].isin(["Amazon", "Shopify"])]

    # ===================== Aggregate =====================
    overlap_summary = (
        df_filtered.groupby(["state", "channels"], as_index=False)
        .agg({"sku_units": "sum"})
    )

    # Pivot so that channels are columns
    overlap_pivot = overlap_summary.pivot(index="state", columns="channels", values="sku_units").fillna(0)

    # Add total column for sorting
    overlap_pivot["Total"] = overlap_pivot.sum(axis=1)
    overlap_pivot = overlap_pivot.sort_values("Total", ascending=False)

    # Apply Top N filter
    if selected_top != "All":
        n = int(selected_top.split()[1])
        overlap_pivot = overlap_pivot.head(n)

    # ===================== Totals for Shopify & Amazon =====================
    if not df_filtered.empty:
        shopify_data = df_filtered[df_filtered["channels"].str.lower() == "shopify"]
        amazon_data = df_filtered[df_filtered["channels"].str.lower() == "amazon"]

        shopify_units = shopify_data["sku_units"].sum()
        amazon_units = amazon_data["sku_units"].sum()

        shopify_revenue = shopify_data["revenue"].sum()
        amazon_revenue = amazon_data["revenue"].sum()
    else:
        shopify_units = amazon_units = shopify_revenue = amazon_revenue = 0

    # ===================== Card Styling =====================
    card_style = """
        background-color: #3a3a3a;
        color: white;
        padding: 20px 10px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        width: 100%;
    """
    number_style = "font-size: 1.8rem; font-weight: bold; margin: 0;"
    label_style = "font-size: 0.9rem; margin-top: 5px; color: #e0e0e0; font-weight: 500;"
    units_style = "font-size: 0.9rem; margin-top: 2px; color: #cfcfcf;"

    # ===================== Display Cards =====================
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">₹{shopify_revenue:,.0f}</p>
            <p style="{units_style}">{int(shopify_units):,} units</p>
            <p style="{label_style}">Shopify Total</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="{card_style}">
            <p style="{number_style}">₹{amazon_revenue:,.0f}</p>
            <p style="{units_style}">{int(amazon_units):,} units</p>
            <p style="{label_style}">Amazon Total</p>
        </div>
        """, unsafe_allow_html=True)

    # ===================== Plotly Chart =====================
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=overlap_pivot.index,
        y=overlap_pivot.get("Amazon", []),
        name="Amazon",
        marker_color="purple",
        hovertemplate="Amazon<br>%{x}: %{y:,} units<extra></extra>"
    ))

    fig.add_trace(go.Bar(
        x=overlap_pivot.index,
        y=overlap_pivot.get("Shopify", []),
        name="Shopify",
        marker_color="green",
        hovertemplate="Shopify<br>%{x}: %{y:,} units<extra></extra>"
    ))

    fig.update_layout(
        barmode="group",
        title=dict(
            text=f"📦 Unit-wise Overlap by State — Amazon vs Shopify",
            font=dict(color="black", size=18)
        ),
        xaxis=dict(
            title="State",
            tickfont=dict(color="black"),
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)"
        ),
        yaxis=dict(
            title="Units Sold",
            tickfont=dict(color="black"),
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(color="black")
        ),
        height=450,
        template="plotly_white",
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=50, r=50, t=50, b=50)
    )

    st.plotly_chart(fig, use_container_width=True)
