import streamlit as st
import pandas as pd
import plotly.express as px
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
# 🚀 OPTIMIZED DATA LOADER (Same as Table)
# ======================================
@st.cache_data(ttl=900)
def load_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # Select specific columns to keep it light
            query = text("SELECT * FROM femisafe_sales")
            df = pd.read_sql(query, conn)
        
        if df.empty: return df

        # Standardize
        df.columns = df.columns.str.strip().str.lower()

        # 1. Cleaning Numerics
        if 'revenue' in df.columns:
            df['revenue'] = pd.to_numeric(df['revenue'].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)

        if 'sku_units' in df.columns:
            df['sku_units'] = pd.to_numeric(df['sku_units'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            df.rename(columns={'sku_units': 'units'}, inplace=True) # Rename for cleaner UI

        # 2. Date Parsing & 🛑 NEW: Year Extraction
        if 'order_date' in df.columns:
            df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')
            
            # Automatically create a 'year' column if it doesn't exist
            if 'year' not in df.columns:
                df['year'] = df['order_date'].dt.year.fillna(0).astype(int).astype(str).replace('0', 'Unknown')

        return df

    except Exception as e:
        st.error(f"⚠️ Database Error: {e}")
        return pd.DataFrame()

# ======================================
# PAGE
# ======================================
def page():
    st.title("📈 Dynamic Chart Builder")

    df = load_data()
    if df.empty:
        st.warning("No data available.")
        return

    # ==============================
    # 🔍 FILTER SECTION
    # ==============================
    with st.expander("🔍 Filters", expanded=True):
        # 🛑 CHANGED: Added a 5th column for the Year filter
        col_yr, col1, col2, col3, col4 = st.columns(5)
        
        filters = {}
        
        # 🛑 NEW: 0. Year Filter
        with col_yr:
            if 'year' in df.columns:
                # Sort years descending so the newest year is at the top
                years = sorted([y for y in df['year'].unique() if y != 'Unknown'], reverse=True)
                sel_years = st.multiselect("Year", years)
                if sel_years: filters['year'] = sel_years

        # 1. Month Filter
        with col1:
            if 'month' in df.columns:
                months = list(df['month'].unique())
                # Try to sort months chronologically if possible, else alphabetical
                try:
                    month_order = ['April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March']
                    months = sorted(months, key=lambda x: month_order.index(x) if x in month_order else 99)
                except:
                    months = sorted(months)
                
                sel_months = st.multiselect("Month", months)
                if sel_months: filters['month'] = sel_months

        # 2. Channel Filter
        with col2:
            if 'channels' in df.columns:
                sel_chan = st.multiselect("Channel", sorted(df['channels'].dropna().unique()))
                if sel_chan: filters['channels'] = sel_chan

        # 3. State Filter
        with col3:
            if 'state' in df.columns:
                sel_state = st.multiselect("State", sorted(df['state'].dropna().unique()))
                if sel_state: filters['state'] = sel_state

        # 4. Product Filter
        with col4:
            if 'products' in df.columns:
                sel_prod = st.multiselect("Product", sorted(df['products'].dropna().unique()))
                if sel_prod: filters['products'] = sel_prod

    # Apply Filters
    df_filtered = df.copy()
    for col, vals in filters.items():
        df_filtered = df_filtered[df_filtered[col].isin(vals)]

    if df_filtered.empty:
        st.warning("No data matches these filters.")
        return

    # ==============================
    # ⚙️ CHART CONFIGURATION
    # ==============================
    st.divider()
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        chart_type = st.selectbox("📊 Chart Type", ["Line Chart", "Column Cluster Chart"], index=1)

    with c2:
        # X-Axis (Dimensions) - Added 'year' as an option here too!
        options_x = ['month', 'year', 'order_date', 'channels', 'state', 'products', 'distributor']
        avail_x = [c for c in options_x if c in df.columns]
        x_axis = st.selectbox("X-Axis (Group By)", avail_x, index=0)

    with c3:
        # Y-Axis (Metrics)
        options_y = ['revenue', 'units']
        avail_y = [c for c in options_y if c in df.columns]
        y_axis = st.selectbox("Y-Axis (Value)", avail_y, index=0)

    with c4:
        # Color (Breakdown) - Added 'year' as an option here too!
        options_color = ['None', 'channels', 'year', 'products', 'state', 'distributor']
        avail_color = ['None'] + [c for c in options_color if c in df.columns and c != 'None']
        
        default_color_idx = avail_color.index('channels') if 'channels' in avail_color else 0
        color_col = st.selectbox("Color (Split By)", avail_color, index=default_color_idx)

    # ==============================
    # 📊 PROCESS & PLOT
    # ==============================
    
    # 1. Group Data
    group_cols = [x_axis]
    if color_col != 'None':
        group_cols.append(color_col)
        
    df_grouped = df_filtered.groupby(group_cols, as_index=False)[y_axis].sum()

    # 2. Sort Data (Crucial for Charts)
    if x_axis == 'month':
        month_order = ['April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March']
        df_grouped['sort_key'] = df_grouped[x_axis].apply(lambda x: month_order.index(x) if x in month_order else 99)
        
        # If splitting by year on a monthly chart, sort by year then month
        if color_col == 'year' or 'year' in df_grouped.columns:
             if 'year' in df_grouped.columns:
                 df_grouped = df_grouped.sort_values(['year', 'sort_key']).drop(columns=['sort_key'])
             else:
                 df_grouped = df_grouped.sort_values('sort_key').drop(columns=['sort_key'])
        else:
            df_grouped = df_grouped.sort_values('sort_key').drop(columns=['sort_key'])

    elif x_axis == 'year':
        df_grouped = df_grouped.sort_values('year')
    elif x_axis == 'order_date':
        df_grouped = df_grouped.sort_values('order_date')
    else:
        df_grouped = df_grouped.sort_values(y_axis, ascending=False)

    # 3. Generate Chart
    color_arg = color_col if color_col != 'None' else None
    
    if chart_type == "Line Chart":
        fig = px.line(
            df_grouped, 
            x=x_axis, 
            y=y_axis, 
            color=color_arg,
            markers=True,
            title=f"{y_axis.title()} by {x_axis.title()}",
            template="plotly_dark"
        )
        fig.update_traces(line=dict(width=3))
        
    elif chart_type == "Column Cluster Chart":
        fig = px.bar(
            df_grouped, 
            x=x_axis, 
            y=y_axis, 
            color=color_arg,
            barmode='group', 
            text_auto='.2s', 
            title=f"{y_axis.title()} by {x_axis.title()}",
            template="plotly_dark"
        )

    # 4. Display
    st.plotly_chart(fig, use_container_width=True)

    # 5. Show Data (Optional)
    with st.expander("View Underlying Data"):
        st.dataframe(df_grouped, use_container_width=True)