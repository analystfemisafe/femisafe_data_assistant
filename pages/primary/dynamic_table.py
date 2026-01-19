import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# ======================================
# Load Data (Universal)
# ======================================
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
            query = text("SELECT * FROM femisafe_sales")
            df = pd.read_sql(query, conn)
        
        # Standardize columns
        df.columns = df.columns.str.strip().str.lower()
        return df
        
    except Exception as e:
        st.error(f"⚠️ Database Connection Failed: {e}")
        return pd.DataFrame()


# ======================================
# PAGE
# ======================================
def page():

    st.title("📊 Dynamic Table Maker / Pivot Builder")

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
            # added dropna to prevent sorting error
            unique_vals = sorted(df[column].dropna().astype(str).unique())
            choice = st.multiselect(f"Filter by {column.title()}", unique_vals)
            filter_selection[column] = choice

    # Apply filters
    filtered_df = df.copy()
    for column, selected_vals in filter_selection.items():
        if selected_vals:
            filtered_df = filtered_df[filtered_df[column].astype(str).isin(selected_vals)]

    # ==============================
    # 📌 ROWS SELECTION (GROUP BY)
    # ==============================
    st.header("📌 Select Row Dimensions (Group By)")

    possible_row_dims = ['order_date', 'month', 'channels', 'distributor', 'fulfilment_type',
                    'categories', 'products', 'sku', 'state', 'city', 'pincode']
    
    # Only show columns that actually exist in the database
    all_columns = [col for col in possible_row_dims if col in df.columns]

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

    # Ensure numeric columns are numeric before aggregating
    for col in selected_values:
        filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce').fillna(0)

    # Create aggregation dictionary
    agg_dict = {value: agg_choice for value in selected_values}

    # Create grouped table
    pivot_table = filtered_df.groupby(row_dims).agg(agg_dict).reset_index()

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