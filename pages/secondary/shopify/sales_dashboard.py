import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine, text

def page():
    st.title("🛍️ Shopify Sales Dashboard (Live Data)")

    # ---------------------------------------------------------
    # 1. LOAD DATA (UNIVERSAL CONNECTIVITY)
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
                # UPDATED: Lowercase table name to match your database dump
                query = text("SELECT * FROM femisafe_shopify_salesdata")
                df = pd.read_sql(query, conn)
                return df
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    df = load_data()

    if df.empty:
        st.warning("⚠️ No data found! Please go to 'Admin Panel' and upload your Shopify CSV.")
        return

    # ---------------------------------------------------------
    # 2. AUTO-FIX COLUMN NAMES
    # ---------------------------------------------------------
    # Convert all columns to lowercase to handle any mismatches
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

    # Standardize 'revenue'
    if 'total_sales' in df.columns:
        df['revenue'] = df['total_sales']
    elif 'net_sales' in df.columns:
        df['revenue'] = df['net_sales']
    elif 'gross_sales' in df.columns:
        df['revenue'] = df['gross_sales']
    
    # Standardize 'units_sold'
    if 'quantity_ordered' in df.columns:
        df['units_sold'] = df['quantity_ordered']
    elif 'units_sold' not in df.columns:
        df['units_sold'] = 0
    
    # Standardize 'order_date'
    if 'day' in df.columns:
        df['order_date'] = df['day']

    # ---------------------------------------------------------
    # 3. DATA CLEANING
    # ---------------------------------------------------------
    try:
        # Convert Date (DD/MM/YY or standard)
        df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')
        
        # Clean numeric columns
        for col in ['revenue', 'units_sold']:
            if col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.replace(',', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    except Exception as e:
        st.error(f"⚠️ Error cleaning data: {e}")
        return

    # ---------------------------------------------------------
    # 4. DASHBOARD CHARTS
    # ---------------------------------------------------------
    
    # Filter: Last 30 Days
    if df['order_date'].notnull().any():
        max_date = df['order_date'].max()
        min_date = max_date - pd.Timedelta(days=30)
        df_recent = df[(df['order_date'] >= min_date) & (df['order_date'] <= max_date)]
    else:
        df_recent = df
        max_date = pd.Timestamp.now()

    # KPIs
    total_rev = df['revenue'].sum()
    total_units = df['units_sold'].sum()

    st.markdown("### 📊 Performance Overview")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("💰 Total Revenue", f"₹{total_rev:,.0f}")
    kpi2.metric("📦 Total Units", f"{int(total_units):,}")
    kpi3.metric("📅 Last Order Date", max_date.strftime('%d %b %Y'))

    st.divider()

    # Chart: Revenue Trend
    st.subheader("📈 Revenue Trend (Last 30 Days)")
    
    if not df_recent.empty:
        daily = df_recent.groupby('order_date')[['revenue', 'units_sold']].sum().reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily['order_date'], y=daily['revenue'],
            name='Revenue', marker_color='#8e44ad'
        ))
        fig.add_trace(go.Scatter(
            x=daily['order_date'], y=daily['units_sold'],
            name='Units', yaxis='y2', line=dict(color='#27ae60', width=3)
        ))

        fig.update_layout(
            xaxis=dict(title='Date'),
            yaxis=dict(title='Revenue (₹)', showgrid=False),
            yaxis2=dict(title='Units', overlaying='y', side='right', showgrid=False),
            template='plotly_white',
            hovermode='x unified',
            height=450
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No recent data to display.")

    # Raw Data View
    with st.expander("🔍 View Raw Data"):
        st.dataframe(df.sort_values('order_date', ascending=False).head(50))