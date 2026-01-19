import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from datetime import datetime
from dateutil.relativedelta import relativedelta

def page():
    st.title("📊 Product-wise Revenue Trend (Last 6 Months)")

    # ----------------------------
    # 1. LOAD DATA (UNIVERSAL CONNECTIVITY)
    # ----------------------------
    @st.cache_data(ttl=600)
    def load_data():
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
                # Query ensuring we get data for the last 6 months
                query = text("""
                    SELECT order_date,
                           month,
                           channels,
                           products,
                           sku_units,
                           revenue
                    FROM femisafe_sales
                    WHERE order_date >= current_date - interval '6 months'
                """)
                df = pd.read_sql(query, conn)
            return df
            
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    df = load_data()

    if df.empty:
        st.warning("⚠️ No data available for the last 6 months.")
        return

    # ----------------------------
    # 2. FILTERS (Multi-select)
    # ----------------------------
    
    # Ensure columns exist before filtering
    if "products" not in df.columns or "channels" not in df.columns:
        st.error("Required columns (products, channels) are missing from the database.")
        return

    # Remove Hot Water Bag if present
    products_list = sorted([str(p) for p in df["products"].dropna().unique() if p != "Hot Water Bag"])
    channels_list = sorted([str(c) for c in df["channels"].dropna().unique()])

    col1, col2 = st.columns(2)
    selected_products = col1.multiselect("Select Product(s)", products_list, default=products_list)
    selected_channels = col2.multiselect("Select Channel(s)", channels_list, default=channels_list)

    # Apply Filters
    filtered = df[
        (df["products"].isin(selected_products)) &
        (df["channels"].isin(selected_channels))
    ]

    if filtered.empty:
        st.warning("No data available for the selected filters.")
        return

    # ----------------------------
    # 3. PROCESS DATES & AGGREGATE
    # ----------------------------
    
    # Ensure order_date is datetime
    filtered["order_date"] = pd.to_datetime(filtered["order_date"])
    
    # Get List of Last 6 Months (for X-axis sorting)
    latest_date = filtered["order_date"].max()
    if pd.isnull(latest_date):
        latest_date = datetime.now()
        
    last_6_months = [(latest_date - relativedelta(months=i)).strftime("%b %Y") for i in reversed(range(6))]

    # Create formatted month column
    filtered["month_str"] = filtered["order_date"].dt.strftime("%b %Y")

    # Aggregate: Product x Month
    agg = filtered.groupby(["products", "month_str"]).agg({
        "sku_units": "sum",
        "revenue": "sum"
    }).reset_index()

    # Ensure all months exist for each product (fill missing months with 0)
    if not agg.empty:
        all_combinations = pd.MultiIndex.from_product(
            [agg["products"].unique(), last_6_months],
            names=["products", "month_str"]
        )
        agg = agg.set_index(["products", "month_str"]).reindex(all_combinations, fill_value=0).reset_index()

    # ----------------------------
    # 4. PLOT: Multi-line chart
    # ----------------------------
    fig = go.Figure()

    if not agg.empty:
        for product in agg["products"].unique():
            prod_data = agg[agg["products"] == product]
            
            # Ensure months are in correct order for plotting
            prod_data = prod_data.set_index("month_str").reindex(last_6_months).reset_index()
            
            fig.add_trace(go.Scatter(
                x=prod_data["month_str"],
                y=prod_data["revenue"],
                mode="lines+markers",
                name=product,
                text=prod_data["sku_units"],
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>" +
                    "Month: %{x}<br>" +
                    "Revenue: ₹%{y:,.0f}<br>" +
                    "Units Sold: %{text:.0f}<extra></extra>"
                )
            ))

    fig.update_layout(
        title="📈 Product-wise Revenue Trend (Last 6 Months)",
        xaxis_title="Month",
        yaxis_title="Revenue (₹)",
        template="plotly_white",
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="black",
            font_size=12,
            font_color="white"
        ),
        legend=dict(title="Products")
    )

    st.plotly_chart(fig, use_container_width=True)