import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text

def page():
    st.title("📦 Amazon Product Performance")

    # ---------------------------------------------------------
    # 1. LOAD DATA FROM NEON
    # ---------------------------------------------------------
    @st.cache_data(ttl=600)
    def load_data():
        try:
            db_url = st.secrets["postgres"]["url"]
            engine = create_engine(db_url)
            with engine.connect() as conn:
                # Query the lowercase Amazon table
                query = text("SELECT * FROM femisafe_amazon_salesdata")
                df = pd.read_sql(query, conn)
            return df
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    df = load_data()

    if df.empty:
        st.warning("⚠️ No data found. Please upload Amazon data in the Admin Panel.")
        return

    # ---------------------------------------------------------
    # 2. DATA CLEANING
    # ---------------------------------------------------------
    # Standardize column names
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

    # Ensure numeric columns
    numeric_cols = ['ordered_product_sales', 'units_ordered', 'sessions_total', 'page_views_total']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # ---------------------------------------------------------
    # 3. ANALYSIS LOGIC
    # ---------------------------------------------------------
    st.subheader("🏆 Top Selling Products")

    if 'title' in df.columns and 'ordered_product_sales' in df.columns:
        # Group by Product Title
        product_performance = df.groupby('title')[['ordered_product_sales', 'units_ordered']].sum().reset_index()
        
        # Sort by Revenue
        top_products = product_performance.sort_values(by='ordered_product_sales', ascending=False).head(10)
        
        # Trim long titles for the chart
        top_products['short_title'] = top_products['title'].str[:40] + "..."

        # Bar Chart
        fig = px.bar(
            top_products, 
            x='ordered_product_sales', 
            y='short_title', 
            orientation='h',
            title="Top 10 Products by Revenue",
            labels={'ordered_product_sales': 'Revenue (₹)', 'short_title': 'Product'},
            color='ordered_product_sales',
            color_continuous_scale='Oranges'
        )
        fig.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
        
        # Data Table
        st.write("### Detailed Product Data")
        st.dataframe(product_performance.sort_values(by='ordered_product_sales', ascending=False))
    
    else:
        st.error("❌ Required columns ('Title' or 'Ordered Product Sales') not found in database.")
        st.write("Available columns:", df.columns.tolist())