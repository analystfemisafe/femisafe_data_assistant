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

    st.title("📊 Dynamic Table Maker (Optimized)")

    # Load Data (Instant if cached)
    df = load_data()

    if df.empty:
        st.warning("No data available.")
        return

    # ==============================
    # 🔍 FILTER SECTION
    # ==============================
    st.header("🔍 Filters")

    # Define filter columns (Check if they exist in DF first)
    possible_cols = ['month', 'channels', 'distributor', 'fulfilment_type', 'state', 'city', 'products']
    filter_cols = [col for col in possible_cols if col in df.columns]

    filter_selection = {}
    cols = st.columns(3)

    for i, column in enumerate(filter_cols):
        with cols[i % 3]:
            # Optimize: sorting unique values from Categories is extremely fast
            unique_vals = sorted(list(df[column].unique()))
            # Convert to string for display in multiselect (Categories might need this)
            unique_vals_str = [str(x) for x in unique_vals]
            
            choice = st.multiselect(f"Filter by {column.title()}", unique_vals_str)
            filter_selection[column] = choice

    # Apply filters
    # Filtering on Category types is faster
    filtered_df = df.copy()
    
    for column, selected_vals in filter_selection.items():
        if selected_vals:
            # We filter using .isin() which works great on categories
            filtered_df = filtered_df[filtered_df[column].isin(selected_vals)]

    # ==============================
    # 📌 ROWS SELECTION (GROUP BY)
    # ==============================
    st.header("📌 Select Row Dimensions (Group By)")

    possible_row_dims = ['order_date', 'month', 'channels', 'distributor', 'fulfilment_type',
                    'categories', 'products', 'sku', 'state', 'city', 'pincode']
    
    # Only show columns that actually exist in the database
    all_columns = [col for col in possible_row_dims if col in df.columns]

    # Add caching logic or session state if needed to remember choices, 
    # but for simple optimization, this is fine.
    row_dims = st.multiselect("Choose rows (grouping columns):", all_columns)

    # ==============================
    # 📦 VALUE COLUMNS + AGGREGATION
    # ==============================
    st.header("📦 Select Value Columns")

    possible_values = ["sku_units", "revenue"]
    value_columns = [col for col in possible_values if col in df.columns]

    selected_values = st.multiselect("Choose values to aggregate:", value_columns)

    agg_types = ["sum", "mean", "max", "min"]

    agg_choice = st.selectbox("Choose aggregation type:", agg_types)

    # ==============================
    # 🚀 GENERATE TABLE
    # ==============================
    st.header("📊 Output Table")

    if len(row_dims) == 0 or len(selected_values) == 0:
        st.warning("Select at least one row and one value to generate the table.")
        return

    # Create aggregation dictionary
    agg_dict = {value: agg_choice for value in selected_values}

    # Create grouped table (observed=True speeds up groupby on categories)
    pivot_table = filtered_df.groupby(row_dims, observed=True).agg(agg_dict).reset_index()

    st.dataframe(pivot_table, use_container_width=True)

    # ==============================
    # 📥 Excel Export
    # ==============================
    st.download_button(
        "⬇️ Download Table as CSV",
        data=pivot_table.to_csv(index=False).encode("utf-8"),
        file_name="dynamic_pivot.csv",
        mime="text/csv"
    )