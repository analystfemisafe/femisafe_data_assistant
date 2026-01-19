import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine, text

def page():
    st.title("📊 Overall Sales Overview")
    st.markdown("### Combined Performance (Shopify + Amazon)")
    

    # ---------------------------------------------------------
    # 1. DATA LOADING FUNCTION (UNIVERSAL CONNECTIVITY)
    # ---------------------------------------------------------
    @st.cache_data(ttl=600)
    def get_data(query_string):
        """
        Connects to Neon and executes the specific query passed to it.
        Works on both Local (secrets.toml) and Render (Env Vars).
        """
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

            # Create Engine
            engine = create_engine(db_url)
            
            with engine.connect() as conn:
                df = pd.read_sql(text(query_string), conn)
            return df
            
        except Exception as e:
            # If a table doesn't exist yet or connection fails, return empty
            # st.error(f"Error: {e}") # Uncomment to debug
            return pd.DataFrame()

    # ---------------------------------------------------------
    # 2. FETCH DATA (Using Lowercase Table Names)
    # ---------------------------------------------------------
    
    # Fetch Shopify Data
    df_shopify = get_data("SELECT * FROM femisafe_shopify_salesdata")
    
    # Fetch Amazon Data
    df_amazon = get_data("SELECT * FROM femisafe_amazon_salesdata")

    # ---------------------------------------------------------
    # 3. CALCULATE & CLEAN TOTALS
    # ---------------------------------------------------------
    
    # --- Function to Clean Currency Columns ---
    def clean_currency(df, col_name):
        if not df.empty and col_name in df.columns:
            # Remove symbols like ₹, Rs, commas, spaces
            # Regex: Keep only digits (0-9) and dots (.)
            # We work on a copy to avoid SettingWithCopy warnings
            clean_series = df[col_name].astype(str).str.replace(r'[^\d.]', '', regex=True)
            return pd.to_numeric(clean_series, errors='coerce').fillna(0).sum()
        return 0

    # --- Process Shopify ---
    shopify_revenue = 0
    if not df_shopify.empty:
        # Standardize columns
        df_shopify.columns = df_shopify.columns.str.lower().str.strip().str.replace(' ', '_')
        
        # Calculate Revenue
        if 'total_sales' in df_shopify.columns:
            shopify_revenue = clean_currency(df_shopify, 'total_sales')
        elif 'revenue' in df_shopify.columns:
            shopify_revenue = clean_currency(df_shopify, 'revenue')
            
    # --- Process Amazon ---
    amazon_revenue = 0
    if not df_amazon.empty:
        # Standardize columns
        df_amazon.columns = df_amazon.columns.str.lower().str.strip().str.replace(' ', '_')
        
        # Calculate Revenue
        if 'ordered_product_sales' in df_amazon.columns:
            amazon_revenue = clean_currency(df_amazon, 'ordered_product_sales')
        elif 'gross_revenue' in df_amazon.columns:
            amazon_revenue = clean_currency(df_amazon, 'gross_revenue')

    # Combined Total
    total_combined_revenue = shopify_revenue + amazon_revenue

    # ---------------------------------------------------------
    # 4. DISPLAY METRICS
    # ---------------------------------------------------------
    
    st.divider()
    
    # Card Styles
    st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #d6d6d6;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    col1.metric("🌍 Total Revenue", f"₹{total_combined_revenue:,.0f}")
    col2.metric("🛍️ Shopify", f"₹{shopify_revenue:,.0f}")
    col3.metric("📦 Amazon", f"₹{amazon_revenue:,.0f}")

    st.divider()

    # ---------------------------------------------------------
    # 5. CHARTS
    # ---------------------------------------------------------
    
    if total_combined_revenue > 0:
        st.subheader("Distribution by Channel")
        
        labels = ['Shopify', 'Amazon']
        values = [shopify_revenue, amazon_revenue]
        colors = ['#95BF47', '#FF9900'] # Shopify Green, Amazon Orange

        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker=dict(colors=colors))])
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Waiting for data... (If you see 0, check if the CSVs are uploaded)")