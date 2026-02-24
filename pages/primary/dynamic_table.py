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
def load_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: Select all needed columns explicitly (safer than *)
            # If your table is huge, listing columns is better. For now * is fine if table isn't massive.
            query = text("SELECT * FROM femisafe_sales")
            df = pd.read_sql(query, conn)
        
        if df.empty: return df

        # Standardize columns
        df.columns = df.columns.str.strip().str.lower()

        # =========================================================
        # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
        # =========================================================

        # 1. Fast Vectorized Cleaning (Numerics)
        # Handle revenue & units efficiently
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
        # Identify columns that are likely categorical (low cardinality)
        cat_cols = [
            'month', 'channels', 'distributor', 'fulfilment_type', 
            'state', 'city', 'products', 'categories', 'sku'
        ]
        
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna("Unknown").astype(str).str.strip().astype('category')
        
        # 3. Fast Date Parsing
        if 'order_date' in df.columns:
             df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')

        return df

    except Exception as e:
        st.error(f"⚠️ Database Connection Failed: {e}")
        return pd.DataFrame()


# ======================================
# PAGE
# ======================================
def page():

    st.title("📊 Dynamic Table Maker")

    # Load Data
    df = load_data()

    if df.empty:
        st.warning("No data available.")
        return

    # ==============================
    # 🔍 FILTER SECTION
    # ==============================
    with st.expander("🔍 Filters", expanded=True):
        # Define filter columns
        possible_cols = ['month', 'channels', 'distributor', 'fulfilment_type', 'state', 'city', 'products']
        filter_cols = [col for col in possible_cols if col in df.columns]

        filters = {}
        cols = st.columns(3)
        for i, col in enumerate(filter_cols):
            with cols[i % 3]:
                unique_vals = sorted([str(x) for x in df[col].unique()])
                selected = st.multiselect(f"{col.title()}", unique_vals, key=f"filter_{col}")
                if selected:
                    filters[col] = selected

    # Apply filters
    filtered_df = df.copy()
    for col, vals in filters.items():
        filtered_df = filtered_df[filtered_df[col].astype(str).isin(vals)]

    # ==============================
    # 📌 CONFIGURATION SECTION
    # ==============================
    st.subheader("⚙️ Table Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Row Dimensions
        possible_rows = ['order_date', 'month', 'channels', 'distributor', 'fulfilment_type', 'categories', 'products', 'sku', 'state', 'city']
        avail_rows = [c for c in possible_rows if c in df.columns]
        row_dims = st.multiselect("Group By (Rows)", avail_rows, default=['month'])

    with col2:
        # Value Columns
        possible_vals = ["sku_units", "revenue"]
        avail_vals = [c for c in possible_vals if c in df.columns]
        selected_values = st.multiselect("Values to Aggregate", avail_vals, default=avail_vals)

    with col3:
        # Aggregation Type
        agg_choice = st.selectbox("Aggregation Type", ["sum", "mean", "max", "min"])
        # 👇 NEW: Grand Total Checkbox
        show_total = st.checkbox("Show Grand Total Row", value=True)

    # ==============================
    # 🚀 GENERATE TABLE
    # ==============================
    st.markdown("---")
    
    if not row_dims or not selected_values:
        st.info("👆 Please select at least one **Group By** column and one **Value** column.")
        return

    # 1. Group & Aggregate
    # observed=True makes it faster for categorical data
    try:
        pivot_table = filtered_df.groupby(row_dims, observed=False)[selected_values].agg(agg_choice).reset_index()
    except TypeError:
        st.error("Error aggregating data. Ensure selected values are numeric.")
        return

    # 2. Add Grand Total (If requested)
    if show_total and not pivot_table.empty:
        # Calculate totals for the value columns
        total_row = pd.DataFrame(columns=pivot_table.columns)
        total_row.loc[0, row_dims[0]] = "GRAND TOTAL"  # Label first column
        
        for col in selected_values:
            if agg_choice == "sum":
                total_row.loc[0, col] = pivot_table[col].sum()
            elif agg_choice == "mean":
                total_row.loc[0, col] = pivot_table[col].mean()
            elif agg_choice == "max":
                total_row.loc[0, col] = pivot_table[col].max()
            elif agg_choice == "min":
                total_row.loc[0, col] = pivot_table[col].min()

        # Append to the bottom
        pivot_table = pd.concat([pivot_table, total_row], ignore_index=True)

    # 3. Display
    st.dataframe(
        pivot_table.style.format({
            'revenue': '₹{:,.0f}', 
            'sku_units': '{:,.0f}'
        }, na_rep="-"), 
        use_container_width=True,
        height=500
    )

    # 4. Download
    st.download_button(
        "⬇️ Download Table as CSV",
        data=pivot_table.to_csv(index=False).encode("utf-8"),
        file_name="dynamic_pivot_with_total.csv",
        mime="text/csv"
    )
    # ==============================
    # 📥 Excel Export
    # ==============================
    st.download_button(
        "⬇️ Download Table as CSV",
        data=pivot_table.to_csv(index=False).encode("utf-8"),
        file_name="dynamic_pivot.csv",
        mime="text/csv"
    )