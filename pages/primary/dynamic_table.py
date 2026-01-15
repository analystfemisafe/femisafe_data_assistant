import streamlit as st
import pandas as pd
import psycopg2

# ======================================
# Load Data
# ======================================
@st.cache_data(ttl=600)
def load_data():
    conn = psycopg2.connect(
        dbname="femisafe_test_db",
        user="ayish",
        password="ajtp@511Db",
        host="localhost",
        port="5432"
    )
    
    df = pd.read_sql("SELECT * FROM femisafe_sales", conn)
    conn.close()

    df.columns = df.columns.str.strip().str.lower()

    return df


# ======================================
# PAGE
# ======================================
def page():

    st.title("📊 Dynamic Table Maker / Pivot Builder")

    df = load_data()

    # ==============================
    # 🔍 FILTER SECTION
    # ==============================
    st.header("🔍 Filters")

    filter_cols = ['month', 'channels', 'distributor', 'fulfilment_type', 'state', 'city', 'products']

    filter_selection = {}
    cols = st.columns(3)

    for i, column in enumerate(filter_cols):
        with cols[i % 3]:
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

    all_columns = ['order_date', 'month', 'channels', 'distributor', 'fulfilment_type',
                   'categories', 'products', 'sku', 'state', 'city', 'pincode']

    row_dims = st.multiselect("Choose rows (grouping columns):", all_columns)

    # ==============================
    # 📦 VALUE COLUMNS + AGGREGATION
    # ==============================
    st.header("📦 Select Value Columns")

    value_columns = ["sku_units", "revenue"]

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

    # Create grouped table
    pivot_table = filtered_df.groupby(row_dims).agg(agg_dict).reset_index()

    st.dataframe(pivot_table, use_container_width=True)

    # ==============================
    # 📥 Excel Export
    # ==============================
    st.download_button(
        "⬇️ Download Table as Excel",
        data=pivot_table.to_csv(index=False).encode("utf-8"),
        file_name="dynamic_pivot.csv",
        mime="text/csv"
    )
