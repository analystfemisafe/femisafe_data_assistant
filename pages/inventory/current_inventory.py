import streamlit as st
import pandas as pd
from sqlalchemy import text
import math

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

def page():
    st.title("📦 Live Inventory Dashboard")
    st.markdown("Track your Raw Material levels and calculate your Finished Goods assembly potential.")

    engine = get_db_engine()
    if not engine:
        st.error("⚠️ Database connection failed.")
        return

    # ==========================================
    # DATA FETCHING
    # ==========================================
    with engine.connect() as conn:
        try:
            # 1. Fetch live stock from the ledger
            stock_query = text("""
                SELECT 
                    r.rm_sku, 
                    r.description, 
                    COALESCE(SUM(l.qty_change), 0) as current_stock
                FROM inv_rm_master r
                LEFT JOIN inv_ledger l ON r.rm_sku = l.rm_sku
                GROUP BY r.rm_sku, r.description
            """)
            stock_df = pd.read_sql(stock_query, conn)
            
            # 2. Fetch BOM (Recipes)
            bom_query = text("""
                SELECT 
                    b.fg_sku, 
                    f.description as fg_desc,
                    b.rm_sku, 
                    b.qty_required, 
                    b.rm_cost
                FROM inv_bom b
                LEFT JOIN inv_fg_master f ON b.fg_sku = f.fg_sku
            """)
            bom_df = pd.read_sql(bom_query, conn)
            
        except Exception as e:
            st.error(f"⚠️ Database error: {e}")
            return

    if stock_df.empty:
        st.warning("No inventory data found. Please add raw materials via GRN first!")
        return

    # Clean up stock dataframe
    stock_df['current_stock'] = stock_df['current_stock'].astype(float)
    
    # Create Tabs
    tab1, tab2 = st.tabs(["🧩 Raw Materials (Stock)", "📦 Finished Goods (Assembly Potential)"])

    # ==========================================
    # TAB 1: LIVE RAW MATERIAL STOCK
    # ==========================================
    with tab1:
        st.subheader("Current Raw Material Levels")
        
        # Add a quick filter
        search_rm = st.text_input("🔍 Search by RM SKU or Description:", "")
        
        display_stock = stock_df.copy()
        if search_rm:
            display_stock = display_stock[
                display_stock['rm_sku'].str.contains(search_rm, case=False, na=False) | 
                display_stock['description'].str.contains(search_rm, case=False, na=False)
            ]
            
        # Highlight low stock (Change text color instead of background for readability)
        def highlight_low_stock(val):
            if val <= 0:
                return 'color: #ff4b4b; font-weight: bold;' # Streamlit's native red text
            return ''

        st.dataframe(
            display_stock.style.applymap(highlight_low_stock, subset=['current_stock']).format({"current_stock": "{:,.0f}"}),
            use_container_width=True,
            height=500
        )

    # ==========================================
    # TAB 2: FINISHED GOODS POTENTIAL
    # ==========================================
    with tab2:
        st.subheader("Assembly Potential (What can we build?)")
        st.markdown("This calculates the maximum number of Finished Goods you can assemble based on your current Raw Material stock levels.")
        
        if bom_df.empty:
            st.info("No recipes found. Upload your BOM in the Consignment tab to unlock this feature!")
        else:
            # The Magic Calculation Logic
            potential_data = []
            
            # Group by Finished Good
            fg_groups = bom_df.groupby('fg_sku')
            
            for fg_sku, recipe in fg_groups:
                fg_desc = recipe['fg_desc'].iloc[0] if not pd.isna(recipe['fg_desc'].iloc[0]) else "Imported FG"
                total_cogs = recipe['rm_cost'].sum()
                
                max_buildable = float('inf')
                limiting_factor = "None"
                
                # Check every raw material required for this FG
                for _, row in recipe.iterrows():
                    rm = row['rm_sku']
                    req_qty = float(row['qty_required'])
                    
                    if req_qty > 0:
                        # Find current stock of this RM
                        stock_row = stock_df[stock_df['rm_sku'] == rm]
                        current_stock = stock_row['current_stock'].iloc[0] if not stock_row.empty else 0
                        
                        # How many can we build based on this specific RM?
                        possible = math.floor(current_stock / req_qty)
                        
                        # If this is the new lowest bottleneck, record it
                        if possible < max_buildable:
                            max_buildable = possible
                            limiting_factor = rm
                
                # If we have no stock or missing RMs, max buildable is 0
                if max_buildable == float('inf') or max_buildable < 0:
                    max_buildable = 0
                    
                potential_data.append({
                    "Finished Good SKU": fg_sku,
                    "Description": fg_desc,
                    "COGS per unit (₹)": total_cogs,
                    "Max Buildable Qty": max_buildable,
                    "Limiting RM": limiting_factor if max_buildable < 500 else "Plentiful" # Show bottleneck if stock is low
                })
                
            potential_df = pd.DataFrame(potential_data).sort_values(by="Max Buildable Qty", ascending=False)
            
            # Format and display
            st.dataframe(
                potential_df.style.format({
                    "COGS per unit (₹)": "₹{:,.2f}",
                    "Max Buildable Qty": "{:,.0f}"
                }),
                use_container_width=True,
                height=600
            )