import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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

def page():

    st.markdown("### 🧭 Amazon vs Shopify — Statewise Overlap (Optimized)")

    # ===================== Connect to database (Optimized) =====================
    @st.cache_data(ttl=900)
    def load_data():
        engine = get_db_engine()
        if not engine:
            return pd.DataFrame()

        try:
            with engine.connect() as conn:
                # ⚡ SQL OPTIMIZATION: Select only needed columns
                query = text("SELECT channels, state, month, products, sku_units, revenue FROM femisafe_sales")
                df = pd.read_sql(query, conn)
            
            if df.empty: return df

            # Standardize column names
            df.columns = df.columns.str.strip().str.lower()

            # =========================================================
            # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
            # =========================================================

            # 1. Fast Vectorized Cleaning (Numerics)
            for col in ["sku_units", "revenue"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # 2. Optimize Text to Category (Instant Filtering)
            # Convert these columns to category type for faster grouping and filtering
            text_cols = ["channels", "state", "month", "products"]
            for col in text_cols:
                if col in df.columns:
                    # Clean string and convert to category
                    df[col] = df[col].astype(str).str.strip().str.title().astype('category')
            
            return df

        except Exception as e:
            st.error(f"⚠️ Data Load Error: {e}")
            return pd.DataFrame()

    df = load_data()

    if df.empty:
        st.warning("No data available.")
        return

    # ===================== Filters =====================
    # Getting unique values from Categories is extremely fast
    months = sorted(list(df["month"].unique())) if "month" in df.columns else []
    products = sorted(list(df["products"].unique())) if "products" in df.columns else []
    top_options = ["Top 5", "Top 10", "Top 15", "All"]

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_month = st.selectbox("🗓️ Select Month", options=["All"] + months, index=0)
    with col2:
        selected_product = st.selectbox("📦 Select Product", options=["All"] + products, index=0)
    with col3:
        selected_top = st.selectbox("🏆 Show", options=top_options, index=1)

    # ===================== Filter Data =====================
    # Filtering on Category types is faster
    df_filtered = df.copy()

    if selected_month != "All" and "month" in df.columns:
        df_filtered = df_filtered[df_filtered["month"] == selected_month]
    if selected_product != "All" and "products" in df.columns:
        df_filtered = df_filtered[df_filtered["products"] == selected_product]

    # Keep only Amazon and Shopify
    if "channels" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["channels"].isin(["Amazon", "Shopify"])]

    if df_filtered.empty:
        st.warning("No data for Amazon/Shopify with these filters.")
        return

    # ===================== Aggregate =====================
    # observed=True makes groupby on categories faster
    overlap_summary = (
        df_filtered.groupby(["state", "channels"], observed=True, as_index=False)
        .agg({"sku_units": "sum", "revenue": "sum"})
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
    shopify_stats = df_filtered[df_filtered["channels"] == "Shopify"][["sku_units", "revenue"]].sum()
    amazon_stats = df_filtered[df_filtered["channels"] == "Amazon"][["sku_units", "revenue"]].sum()

    shopify_units = shopify_stats["sku_units"]
    shopify_revenue = shopify_stats["revenue"]
    
    amazon_units = amazon_stats["sku_units"]
    amazon_revenue = amazon_stats["revenue"]

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