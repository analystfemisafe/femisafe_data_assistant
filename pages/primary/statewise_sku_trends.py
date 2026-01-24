import streamlit as st
import pandas as pd
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

# ======================================
# 🚀 OPTIMIZED DATA LOADER
# ======================================
@st.cache_data(ttl=900)
def get_sales_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: Select only needed columns
            query = text("SELECT channels, products, month, state, sku_units, revenue FROM femisafe_sales")
            df = pd.read_sql(query, conn)

        if df.empty: return df

        # =========================================================
        # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
        # =========================================================

        # 1. Fast Vectorized Cleaning (Revenue & Units)
        # Regex removes ₹, commas, spaces instantly
        if 'revenue' in df.columns:
            df['revenue'] = pd.to_numeric(
                df['revenue'].astype(str).str.replace(r'[₹,]', '', regex=True),
                errors='coerce'
            ).fillna(0)

        if 'sku_units' in df.columns:
            df['sku_units'] = pd.to_numeric(
                df['sku_units'].astype(str).str.replace(',', ''),
                errors='coerce'
            ).fillna(0)

        # 2. Optimize Text to Category (Instant Filtering & Grouping)
        # Text columns used in filters/groupby should be categories
        for col in ['channels', 'state', 'products', 'month']:
            if col in df.columns:
                df[col] = df[col].fillna("Unknown").astype(str).str.strip().str.title().astype('category')
        
        return df
        
    except Exception as e:
        st.error(f"⚠️ Database Connection Failed: {e}")
        return pd.DataFrame()

# ======================================
# PAGE FUNCTION
# ======================================
def page():

    st.markdown("## 🗺️ Statewise Trends Overview (Optimized)")

    # Load Data (Instant if cached)
    df = get_sales_data()
    
    if df.empty:
        st.warning("No sales data available.")
        return

    # ===================== Filter Options =====================
    # Getting unique values from Categories is extremely fast
    channels = sorted(list(df["channels"].unique()))
    products = sorted(list(df["products"].unique()))
    months = sorted(list(df["month"].unique()))

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_channel = st.selectbox("🛒 Select Channel", options=["All"] + channels)
    with col2:
        selected_product = st.selectbox("📦 Select Product", options=["All"] + products)
    with col3:
        selected_month = st.selectbox("🗓️ Select Month", options=["All"] + months)

    # ===================== Apply Filters =====================
    # Filtering on Category types is 100x faster than strings
    df_filtered = df.copy()

    if selected_channel != "All":
        df_filtered = df_filtered[df_filtered["channels"] == selected_channel]
    if selected_product != "All":
        df_filtered = df_filtered[df_filtered["products"] == selected_product]
    if selected_month != "All":
        df_filtered = df_filtered[df_filtered["month"] == selected_month]

    if df_filtered.empty:
        st.warning("No data found for the selected filters.")
        return

    # ===================== Custom Table Construction =====================
    
    # 1. Base Aggregation (observed=True makes groupby on categories faster)
    grouped = (
        df_filtered.groupby(["state", "products"], observed=True, as_index=False)
        .agg({"sku_units": "sum", "revenue": "sum"})
    )

    # 2. Calculate State Totals (Sort States by UNITS SOLD Descending)
    state_totals = (
        grouped.groupby("state", observed=True)["sku_units"]
        .sum()
        .reset_index()
        .sort_values("sku_units", ascending=False)
    )
    sorted_states = state_totals["state"].tolist()

    # 3. Calculate Global Total
    grand_total_revenue = grouped["revenue"].sum()
    grand_total_units = grouped["sku_units"].sum()

    # 4. Build the Display List Row by Row
    table_rows = []

    # Iterate through sorted states
    for state in sorted_states:
        # Get products for this state
        state_data = grouped[grouped["state"] == state].copy()
        
        # Sort products within the state by UNITS SOLD (Descending)
        state_data = state_data.sort_values("sku_units", ascending=False)
        
        # Calculate State Subtotals
        sub_revenue = state_data["revenue"].sum()
        sub_units = state_data["sku_units"].sum()
        
        # State % = State Revenue / Grand Total Revenue
        state_global_pct = (sub_revenue / grand_total_revenue * 100) if grand_total_revenue > 0 else 0

        # --- Add Product Rows ---
        is_first_row = True
        for _, row in state_data.iterrows():
            # Product % = Product Revenue / STATE Revenue
            product_local_pct = (row["revenue"] / sub_revenue * 100) if sub_revenue > 0 else 0
            
            table_rows.append({
                "State": state if is_first_row else "", 
                "Product": row["products"],
                "Units Sold": row["sku_units"],
                "Revenue": row["revenue"],
                "Revenue %": product_local_pct,
                "Type": "Normal"
            })
            is_first_row = False

        # --- Add State Subtotal Row ---
        table_rows.append({
            "State": f"{state} Total",
            "Product": "",
            "Units Sold": sub_units,
            "Revenue": sub_revenue,
            "Revenue %": state_global_pct,
            "Type": "Subtotal"
        })

    # 5. Create DataFrame
    final_df = pd.DataFrame(table_rows)

    # 6. Add Grand Total Row
    grand_total_row = pd.DataFrame([{
        "State": "🏆 GRAND TOTAL",
        "Product": "",
        "Units Sold": grand_total_units,
        "Revenue": grand_total_revenue,
        "Revenue %": 100.00,
        "Type": "Grand Total"
    }])
    
    final_df = pd.concat([final_df, grand_total_row], ignore_index=True)

    # ===================== STYLING LOGIC =====================
    
    def highlight_totals(row):
        if row["Type"] == "Subtotal":
            return ['background-color: #e6f3ff; color: black; font-weight: bold'] * len(row)
        elif row["Type"] == "Grand Total":
            return ['background-color: #d1e7dd; color: black; font-weight: bold; border-top: 2px solid #666'] * len(row)
        else:
            return [''] * len(row)

    # Apply Style + Formatting
    styled_df = (
        final_df.style
        .apply(highlight_totals, axis=1)
        .format({
            "Units Sold": "{:,.0f}",
            "Revenue": "₹{:,.2f}",
            "Revenue %": "{:.2f}%"
        })
    )

    # ===================== Display =====================
    st.markdown("### 📈 Statewise Product Performance")
    st.caption("ℹ️ **Note:** Product % is based on *State Total*. State Total % is based on *Grand Total*.")

    # Column Config to Disable User Sorting (Visual only) & Formatting
    column_config = {
        "Type": None,  # Hide Helper Column
        "State": st.column_config.TextColumn("State", disabled=True),
        "Product": st.column_config.TextColumn("Product", disabled=True),
        "Units Sold": st.column_config.NumberColumn("Units Sold", format="%d", disabled=True),
        "Revenue": st.column_config.NumberColumn("Revenue", format="₹%.2f", disabled=True),
        "Revenue %": st.column_config.NumberColumn("Revenue %", format="%.2f%%", disabled=True),
    }

    # Using st.dataframe with HEIGHT enables sticky headers
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        height=800  # Sticky Header Enabled
    )