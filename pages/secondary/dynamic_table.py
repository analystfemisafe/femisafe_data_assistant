import streamlit as st
import pandas as pd
from sqlalchemy import text

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

# ======================================
# 🗺️ TABLE CONFIGURATION 
# ======================================
# Map your dropdown names to your actual Supabase table names here:
TABLE_MAPPING = {
    "Amazon": "femisafe_amazon_salesdata",
    "Blinkit": "femisafe_blinkit_salesdata",
    "Flipkart": "femisafe_flipkart_salesdata",
    "Shopify": "femisafe_shopify_salesdata",
    "Swiggy": "femisafe_swiggy_salesdata"
}

# ======================================
# 🚀 SECONDARY DATA LOADER
# ======================================
# Notice we now pass `table_name` into the function!
@st.cache_data(ttl=900)
def load_secondary_data(table_name):
    engine = get_db_engine()
    if not engine: return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # Dynamically select from the chosen table
            query = text(f'SELECT * FROM "{table_name}"')
            df = pd.read_sql(query, conn)
        
        if df.empty: return df

        # Standardize columns
        df.columns = df.columns.str.strip().str.lower()

        # Clean Numerics
        if 'revenue' in df.columns:
            df['revenue'] = pd.to_numeric(df['revenue'].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)
        if 'sku_units' in df.columns:
            df['sku_units'] = pd.to_numeric(df['sku_units'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            df.rename(columns={'sku_units': 'units'}, inplace=True) # Rename for cleaner UI
        elif 'units' not in df.columns:
            df['units'] = 0

        # Categorize text for speed
        cat_cols = ['month', 'channels', 'distributor', 'state', 'city', 'products', 'sku']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna("Unknown").astype(str).str.strip().astype('category')
        
        # Parse Dates
        if 'order_date' in df.columns:
             df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')
             if 'year' not in df.columns:
                 df['year'] = df['order_date'].dt.year.fillna(0).astype(int).astype(str).replace('0', 'Unknown')

        return df

    except Exception as e:
        st.error(f"⚠️ Database Error when loading {table_name}: {e}")
        return pd.DataFrame()

# ======================================
# PAGE
# ======================================
def page():
    st.title("🏬 Secondary Dynamic Table")
    st.caption("Select a channel table to slice and dice your data.")

    # ==============================
    # 🎯 1. CHOOSE DATA SOURCE
    # ==============================
    selected_channel_name = st.selectbox(
        "📂 Select Channel Data Source:", 
        options=list(TABLE_MAPPING.keys())
    )
    
    # Get the actual database table name based on selection
    selected_table_name = TABLE_MAPPING[selected_channel_name]

    # Load the specific table
    df = load_secondary_data(selected_table_name)

    if df.empty:
        st.warning(f"No data available in the '{selected_channel_name}' table ({selected_table_name}).")
        return

    # ==============================
    # 🔍 2. FILTERS
    # ==============================
    with st.expander("🔍 Filters", expanded=False):
        # We dynamically check which columns exist in THIS specific table
        possible_cols = ['year', 'month', 'distributor', 'state', 'city', 'products', 'sku']
        filter_cols = [col for col in possible_cols if col in df.columns]

        filters = {}
        cols = st.columns(3)
        for i, col in enumerate(filter_cols):
            with cols[i % 3]:
                unique_vals = sorted([str(x) for x in df[col].unique()])
                selected = st.multiselect(f"{col.title()}", unique_vals, key=f"sec_filter_{col}")
                if selected:
                    filters[col] = selected

        # Apply additional filters
        filtered_df = df.copy()
        for col, vals in filters.items():
            filtered_df = filtered_df[filtered_df[col].astype(str).isin(vals)]

    if filtered_df.empty:
        st.warning("No data matches these filters.")
        return

    # ==============================
    # 📌 3. CONFIGURATION SECTION
    # ==============================
    st.markdown("---")
    st.markdown("### ⚙️ Configure Table")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Row Dimensions (Only shows options that exist in the selected table)
        possible_rows = ['year', 'month', 'order_date', 'distributor', 'products', 'sku', 'state', 'city']
        avail_rows = [c for c in possible_rows if c in df.columns]
        
        # Default to distributor or month if available
        default_row = ['distributor'] if 'distributor' in avail_rows else (['month'] if 'month' in avail_rows else [])
        row_dims = st.multiselect("Group By (Rows)", avail_rows, default=default_row)

    with col2:
        # Value Columns
        possible_vals = ["units", "revenue"]
        avail_vals = [c for c in possible_vals if c in df.columns]
        selected_values = st.multiselect("Values to Aggregate", avail_vals, default=avail_vals)

    with col3:
        # Aggregation Type
        agg_choice = st.selectbox("Aggregation Type", ["sum", "mean", "max", "min"])
        show_total = st.checkbox("Show Grand Total Row", value=True)

    # ==============================
    # 🚀 4. GENERATE TABLE
    # ==============================
    st.markdown("---")
    
    if not row_dims or not selected_values:
        st.info("👆 Please select at least one **Group By** column and one **Value** column.")
        return

    # 1. Group & Aggregate
    try:
        pivot_table = filtered_df.groupby(row_dims, observed=False)[selected_values].agg(agg_choice).reset_index()
    except TypeError:
        st.error("Error aggregating data. Ensure selected values are numeric.")
        return

    # 2. Add Grand Total
    if show_total and not pivot_table.empty:
        total_row = pd.DataFrame(columns=pivot_table.columns)
        total_row.loc[0, row_dims[0]] = "GRAND TOTAL" 
        
        for col in selected_values:
            if agg_choice == "sum": total_row.loc[0, col] = pivot_table[col].sum()
            elif agg_choice == "mean": total_row.loc[0, col] = pivot_table[col].mean()
            elif agg_choice == "max": total_row.loc[0, col] = pivot_table[col].max()
            elif agg_choice == "min": total_row.loc[0, col] = pivot_table[col].min()

        pivot_table = pd.concat([pivot_table, total_row], ignore_index=True)

    # 3. Format & Display
    # Dynamically build formatting dict based on what columns exist
    format_dict = {}
    if 'revenue' in pivot_table.columns: format_dict['revenue'] = '₹{:,.0f}'
    if 'units' in pivot_table.columns: format_dict['units'] = '{:,.0f}'

    st.dataframe(
        pivot_table.style.format(format_dict, na_rep="-"), 
        use_container_width=True,
        height=500
    )

    # 4. Download
    st.download_button(
        f"⬇️ Download {selected_channel_name} Table as CSV",
        data=pivot_table.to_csv(index=False).encode("utf-8"),
        file_name=f"{selected_table_name}_dynamic_table.csv",
        mime="text/csv"
    )