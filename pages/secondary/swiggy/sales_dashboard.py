import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text

def page():
    st.title("🍜 Swiggy Sales Dashboard (Live Data)")

    # ---------------------------------------------------------
    # 1. LOAD DATA FROM NEON
    # ---------------------------------------------------------
    @st.cache_data(ttl=600)
    def load_data():
        try:
            # Connect to Neon
            db_url = st.secrets["postgres"]["url"]
            engine = create_engine(db_url)
            
            with engine.connect() as conn:
                # Query the lowercase Swiggy table
                query = text("SELECT * FROM femisafe_swiggy_salesdata")
                df = pd.read_sql(query, conn)
            return df
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    df = load_data()

    if df.empty:
        st.warning("⚠️ No data found. Please upload Swiggy data in the Admin Panel.")
        return

    # ---------------------------------------------------------
    # 2. DATA CLEANING & STANDARDIZATION
    # ---------------------------------------------------------
    # Convert columns to lowercase to match your database
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

    # Standardize 'Revenue'
    # Swiggy often uses 'item_total', 'net_total', or 'gross_sales'
    if 'net_total' in df.columns:
        df['revenue'] = df['net_total']
    elif 'item_total' in df.columns:
        df['revenue'] = df['item_total']
    elif 'gross_sales' in df.columns:
        df['revenue'] = df['gross_sales']
    else:
        df['revenue'] = 0

    # Standardize 'Order ID'
    if 'order_id' not in df.columns and 'id' in df.columns:
        df['order_id'] = df['id']

    # Standardize 'Date'
    if 'order_date' in df.columns:
        df['date'] = pd.to_datetime(df['order_date'], errors='coerce')
    elif 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    elif 'created_at' in df.columns:
        df['date'] = pd.to_datetime(df['created_at'], errors='coerce')

    # Ensure numeric values
    df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce').fillna(0)

    # ---------------------------------------------------------
    # 3. DASHBOARD METRICS
    # ---------------------------------------------------------
    
    total_revenue = df['revenue'].sum()
    total_orders = df.shape[0] # Count total rows as orders

    st.markdown("### 📊 Performance Overview")
    kpi1, kpi2 = st.columns(2)
    kpi1.metric("💰 Total Revenue", f"₹{total_revenue:,.0f}")
    kpi2.metric("📦 Total Orders", f"{total_orders:,}")

    st.divider()

    # ---------------------------------------------------------
    # 4. CHARTS
    # ---------------------------------------------------------
    
    col1, col2 = st.columns(2)

    # Chart 1: Daily Revenue Trend
    with col1:
        st.subheader("📈 Daily Revenue Trend")
        if 'date' in df.columns and df['date'].notnull().any():
            daily_sales = df.groupby(df['date'].dt.date)['revenue'].sum().reset_index()
            fig_trend = px.line(
                daily_sales, 
                x='date', 
                y='revenue', 
                markers=True,
                title="Revenue over Time",
                color_discrete_sequence=['#FC8019'] # Swiggy Orange
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("Date column not found or empty.")

    # Chart 2: Top Items (if 'item_name' exists)
    with col2:
        st.subheader("🍔 Top Selling Items")
        item_col = None
        # Try to find the item name column
        possible_names = ['item_name', 'product_name', 'items', 'item']
        for col in possible_names:
            if col in df.columns:
                item_col = col
                break
        
        if item_col:
            top_items = df[item_col].value_counts().head(5).reset_index()
            top_items.columns = ['Item', 'Count']
            fig_bar = px.bar(
                top_items, 
                x='Count', 
                y='Item', 
                orientation='h', 
                title="Most Ordered Items",
                color='Count',
                color_continuous_scale='Oranges'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Item name column not found.")

    # Raw Data
    with st.expander("📄 View Raw Data"):
        st.dataframe(df.head(50))