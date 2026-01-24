import streamlit as st
import pandas as pd
import plotly.express as px
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

# ---------------------------------------------------------
# 🚀 OPTIMIZED DATA LOADER
# ---------------------------------------------------------
@st.cache_data(ttl=900)  # Cache results for 15 minutes
def get_optimized_blinkit_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: 
            # 1. Fetch only needed columns (No SELECT *)
            # 2. Filter 'Cancelled' here (Saves Python processing & Bandwidth)
            query = text("""
                SELECT 
                    order_date, 
                    order_week, 
                    sku, 
                    feeder_wh, 
                    net_revenue, 
                    quantity 
                FROM femisafe_blinkit_salesdata 
                WHERE order_status NOT IN ('Cancelled', 'Returned')
            """)
            df = pd.read_sql(query, conn)
        
        if df.empty: return df

        # =========================================================
        # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
        # =========================================================
        
        # 1. Fast Vectorized Cleaning (Regex is faster than .str.replace chained)
        for col in ['net_revenue', 'quantity']:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r'[₹,]', '', regex=True), 
                errors='coerce'
            ).fillna(0)
            
        # 2. Downcast numeric types (Saves ~50% RAM)
        df['quantity'] = df['quantity'].astype('int32')
        # Revenue kept as float for accuracy
        
        # 3. Use Categories for Text (Instant filtering & Sorting)
        df['sku'] = df['sku'].astype('category')
        df['feeder_wh'] = df['feeder_wh'].fillna("Unknown").astype(str).str.title().astype('category')
        
        # 4. Fast Date Parsing (dayfirst=True fixes date flipping issues)
        df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')
        df.dropna(subset=['order_date'], inplace=True)
        
        # 5. Derive Day Columns
        df["day_name"] = df["order_date"].dt.day_name()
        df["day_num"] = (df["order_date"].dt.weekday + 1) % 7

        return df

    except Exception as e:
        st.error(f"⚠️ Data Load Error: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# PAGE LAYOUT
# ---------------------------------------------------------
def page():
    st.markdown("### 📊 Day-wise Revenue (Week Comparison)")

    # Load Data (Instant if cached)
    df = get_optimized_blinkit_data()

    if df.empty:
        st.warning("No data found in 'femisafe_blinkit_salesdata'.")
        return

    # --- FILTERS ---
    col1, col2, col3 = st.columns(3)
    
    # Using 'category' dtype makes these list generations instant
    with col1:
        # We convert unique categories to a sorted list for the dropdown
        sku_options = sorted(list(df["sku"].unique()))
        sku = st.selectbox("Select SKU", ["All"] + sku_options)
    
    with col2:
        wh_options = sorted(list(df["feeder_wh"].unique()))
        warehouse = st.selectbox("Select Warehouse", ["All"] + wh_options)
    
    with col3:
        week_limit = st.selectbox("Weeks to Compare", [2, 3, 4, 5, 6], index=2)

    # --- APPLY FILTERS ---
    # Filtering on categories is extremely fast
    filtered = df.copy()
    if sku != "All": 
        filtered = filtered[filtered["sku"] == sku]
    if warehouse != "All": 
        filtered = filtered[filtered["feeder_wh"] == warehouse]

    # --- WEEK SORTING ---
    # Robust logic for "WK01", "Week 1", "1"
    all_weeks = list(filtered["order_week"].unique())
    
    def get_week_num(val):
        import re
        nums = re.findall(r'\d+', str(val))
        return int(nums[0]) if nums else 0

    try:
        latest_weeks = sorted(all_weeks, key=get_week_num)[-week_limit:]
    except:
        latest_weeks = sorted(all_weeks)[-week_limit:]

    filtered = filtered[filtered["order_week"].isin(latest_weeks)]

    if filtered.empty:
        st.info("No data for these filters.")
        return

    # --- AGGREGATION & CHART ---
    # observed=True is required for groupby on Category types to prevent empty bins
    agg = (
        filtered
        .groupby(["day_name", "day_num", "order_week"], observed=True)
        .agg(
            revenue=("net_revenue", "sum"),
            units=("quantity", "sum")
        )
        .reset_index()
    )

    agg = agg.sort_values("day_num")

    fig = px.bar(
        agg, 
        x="day_name", 
        y="revenue", 
        color="order_week", 
        barmode="group", 
        text="units",
        category_orders={
            "day_name": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
            "order_week": latest_weeks
        },
        labels={"day_name": "Day", "revenue": "Revenue (₹)", "order_week": "Week"},
        hover_data={"revenue": ":,.0f", "units": True},
        height=500
    )
    
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title="Day", yaxis_title="Revenue", bargap=0.2)
    
    st.plotly_chart(fig, use_container_width=True)

    # --- SUMMARY TABLE ---
    # Start from FULL filtered data (Respects Warehouse/Week filters)
    table_source = filtered.copy()

    table_df = (
        table_source
        .groupby("sku", observed=True, as_index=False)
        .agg(
            units=("quantity", "sum"),
            revenue=("net_revenue", "sum")
        )
    )

    total_revenue = table_df["revenue"].sum()
    
    if total_revenue > 0:
        table_df["revenue_pct"] = (table_df["revenue"] / total_revenue * 100).fillna(0)
    else:
        table_df["revenue_pct"] = 0.0

    table_df = table_df.sort_values("revenue", ascending=False)

    # Add Grand Total
    total_row = pd.DataFrame([{
        "sku": "GRAND TOTAL",
        "units": table_df["units"].sum(),
        "revenue": table_df["revenue"].sum(),
        "revenue_pct": 100.0
    }])
    table_df = pd.concat([table_df, total_row], ignore_index=True)

    # Styling
    def highlight_selected(row):
        if row["sku"] == "GRAND TOTAL":
            return ["font-weight: bold"] * len(row)
        if sku != "All" and row["sku"] == sku:
            return ["background-color: #444444"] * len(row)
        return [""] * len(row)

    st.markdown("### 📋 Product Summary")
    st.dataframe(
        table_df.style.apply(highlight_selected, axis=1).format({
            "units": "{:,.0f}",
            "revenue": "₹{:,.0f}",
            "revenue_pct": "{:.1f}%"
        }),
        use_container_width=True
    )