import os
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text

def page():
    st.title("🟡 Blinkit Sales Dashboard (Live Data)")

    # ---------------------------------------------------------
    # 1. LOAD DATA FROM NEON (UNIVERSAL CONNECTIVITY)
    # ---------------------------------------------------------
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
                # Query the lowercase Blinkit table
                query = text("SELECT * FROM femisafe_blinkit_salesdata")
                df = pd.read_sql(query, conn)
            return df
            
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    df = load_data()

    if df.empty:
        st.warning("⚠️ No data found. Please upload Blinkit data in the Admin Panel.")
        return

    # ---------------------------------------------------------
    # 2. DATA CLEANING (The Fix 🛠️)
    # ---------------------------------------------------------
    try:
        # Convert all headers to lowercase
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

        # Identify Revenue Column
        rev_col = None
        if 'item_total' in df.columns:
            rev_col = 'item_total'
        elif 'net_sales' in df.columns:
            rev_col = 'net_sales'
        elif 'gross_amount' in df.columns:
            rev_col = 'gross_amount'
        elif 'revenue' in df.columns:
            rev_col = 'revenue'

        # CLEAN REVENUE (Remove ₹, commas, spaces)
        if rev_col:
            # This Regex keeps ONLY numbers (0-9) and dots (.)
            df['revenue'] = df[rev_col].astype(str).str.replace(r'[^\d.]', '', regex=True)
            df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce').fillna(0)
        else:
            df['revenue'] = 0

        # CLEAN UNITS (Remove commas)
        unit_col = None
        if 'quantity' in df.columns:
            unit_col = 'quantity'
        elif 'qty' in df.columns:
            unit_col = 'qty'
        
        if unit_col:
            df['units_sold'] = df[unit_col].astype(str).str.replace(r'[^\d.]', '', regex=True)
            df['units_sold'] = pd.to_numeric(df['units_sold'], errors='coerce').fillna(0)
        else:
            df['units_sold'] = 0

        # Standardize Date
        if 'order_date' in df.columns:
            df['date'] = pd.to_datetime(df['order_date'], errors='coerce')
        elif 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')

    except Exception as e:
        st.error(f"⚠️ Data Cleaning Error: {e}")
        return

    # ---------------------------------------------------------
    # 3. DASHBOARD METRICS
    # ---------------------------------------------------------
    
    total_rev = df['revenue'].sum()
    total_units = df['units_sold'].sum()

    st.markdown("### 📊 Performance Overview")
    kpi1, kpi2 = st.columns(2)
    kpi1.metric("💰 Total Revenue", f"₹{total_rev:,.0f}")
    kpi2.metric("📦 Total Units Sold", f"{int(total_units):,}")

    st.divider()

    # ---------------------------------------------------------
    # 4. CHARTS
    # ---------------------------------------------------------
    
    col1, col2 = st.columns(2)

    # Chart 1: Sales Trend
    with col1:
        st.subheader("📈 Sales Trend")
        if 'date' in df.columns and df['date'].notnull().any() and total_rev > 0:
            daily_sales = df.groupby(df['date'].dt.date)['revenue'].sum().reset_index()
            fig_trend = px.line(
                daily_sales, 
                x='date', y='revenue', markers=True,
                title="Revenue over Time",
                color_discrete_sequence=['#F4C430']
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("No revenue trend data available.")

    # Chart 2: Top Products
    with col2:
        st.subheader("🏆 Top Products")
        # Identify Product Name Column
        prod_col = None
        for col in ['item_name', 'product_name', 'product', 'item']:
            if col in df.columns:
                prod_col = col
                break
        
        if prod_col:
            top_products = df.groupby(prod_col)['revenue'].sum().reset_index().sort_values(by='revenue', ascending=False).head(5)
            top_products['short_name'] = top_products[prod_col].astype(str).str[:30] + "..."
            
            fig_bar = px.bar(
                top_products, 
                x='revenue', y='short_name', orientation='h',
                title="Top 5 Products by Revenue",
                color='revenue', color_continuous_scale='YlOrBr'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Product Name column missing.")