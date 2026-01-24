import streamlit as st
import pandas as pd
import plotly.express as px
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

# ---------------------------------------------------------
# 🚀 OPTIMIZED DATA LOADER
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def get_amazon_data():
    engine = get_db_engine()
    if not engine:
        return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # ⚡ SQL OPTIMIZATION: Fetch only needed columns
            # We explicitly select and alias columns to avoid Python-side renaming overhead
            query = text("""
                SELECT 
                    title, 
                    ordered_product_sales, 
                    units_ordered 
                FROM femisafe_amazon_salesdata
            """)
            df = pd.read_sql(query, conn)
        
        if df.empty: return df

        # =========================================================
        # ⚡ PANDAS MEMORY & SPEED OPTIMIZATION
        # =========================================================
        
        # 1. Fast Vectorized Cleaning (Regex removes ₹, comma, spaces)
        # Handle 'ordered_product_sales' (Money)
        if 'ordered_product_sales' in df.columns:
            df['ordered_product_sales'] = pd.to_numeric(
                df['ordered_product_sales'].astype(str).str.replace(r'[₹,]', '', regex=True),
                errors='coerce'
            ).fillna(0)

        # Handle 'units_ordered' (Integer)
        if 'units_ordered' in df.columns:
            df['units_ordered'] = pd.to_numeric(
                df['units_ordered'].astype(str).str.replace(',', ''),
                errors='coerce'
            ).fillna(0).astype('int32')

        # 2. Optimize Text to Category (Faster grouping)
        if 'title' in df.columns:
            df['title'] = df['title'].fillna("Unknown").astype(str).str.strip().astype('category')

        return df

    except Exception as e:
        st.error(f"⚠️ Data Load Error: {e}")
        return pd.DataFrame()

# ===========================================================
# PAGE
# ===========================================================
def page():
    st.title("📦 Amazon Product Performance (Optimized)")

    # Load Data (Instant if cached)
    df = get_amazon_data()

    if df.empty:
        st.warning("⚠️ No data found. Please upload Amazon data in the Admin Panel.")
        return

    # ---------------------------------------------------------
    # ANALYSIS LOGIC
    # ---------------------------------------------------------
    st.subheader("🏆 Top Selling Products")

    if 'title' in df.columns and 'ordered_product_sales' in df.columns:
        
        # Group by Product Title (observed=True makes groupby faster on categories)
        product_performance = (
            df.groupby('title', observed=True)[['ordered_product_sales', 'units_ordered']]
            .sum()
            .reset_index()
        )
        
        # Sort by Revenue
        top_products = product_performance.sort_values(by='ordered_product_sales', ascending=False).head(10)
        
        # Trim long titles for the chart (Convert back to string for manipulation)
        top_products['short_title'] = top_products['title'].astype(str).str[:40] + "..."

        # Bar Chart
        fig = px.bar(
            top_products, 
            x='ordered_product_sales', 
            y='short_title', 
            orientation='h',
            title="Top 10 Products by Revenue",
            labels={'ordered_product_sales': 'Revenue (₹)', 'short_title': 'Product'},
            color='ordered_product_sales',
            color_continuous_scale='Oranges',
            text_auto='.2s'
        )
        fig.update_layout(
            yaxis={'categoryorder':'total ascending'},
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Data Table
        st.write("### Detailed Product Data")
        
        # Display with formatting
        st.dataframe(
            product_performance.sort_values(by='ordered_product_sales', ascending=False),
            column_config={
                "ordered_product_sales": st.column_config.NumberColumn("Total Sales", format="₹%.2f"),
                "units_ordered": st.column_config.NumberColumn("Units", format="%d"),
                "title": "Product Title"
            },
            use_container_width=True,
            hide_index=True
        )
    
    else:
        st.error("❌ Required columns ('Title' or 'Ordered Product Sales') not found in database.")