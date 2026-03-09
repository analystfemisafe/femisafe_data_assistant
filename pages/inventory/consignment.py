import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import time

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
    st.title("🚚 Create Consignment")
    st.markdown("Dispatch Finished Goods (FG) and automatically deduct Raw Materials (RM) from inventory.")

    engine = get_db_engine()
    if not engine:
        st.error("⚠️ Database connection failed.")
        return

    # Fetch available Finished Goods (FG)
    with engine.connect() as conn:
        try:
            fg_list = pd.read_sql("SELECT DISTINCT fg_sku FROM inv_bom", conn)
        except Exception:
            fg_list = pd.DataFrame()

    tab1, tab2 = st.tabs(["🚚 Dispatch Consignment", "📋 Manage FG Recipes (BOM)"])

    # ==========================================
    # TAB 2: MANAGE BOM (Upload Recipes)
    # ==========================================
    with tab2:
        st.subheader("Upload Bill of Materials (Recipe Mapping)")
        st.markdown("Upload a CSV or Excel file to map your Finished Goods to your Raw Materials. \n\n**Required Columns:** `fg_sku`, `rm_sku`, `qty_required`.")
        
        uploaded_file = st.file_uploader("Upload BOM File", type=["csv", "xlsx"])
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'): df_upload = pd.read_csv(uploaded_file)
                else: df_upload = pd.read_excel(uploaded_file)
                
                df_upload.columns = df_upload.columns.str.strip().str.lower()
                
                required_cols = ['fg_sku', 'rm_sku', 'qty_required']
                if not all(col in df_upload.columns for col in required_cols):
                    st.error(f"⚠️ Error: Your file must contain these exact columns: {', '.join(required_cols)}")
                else:
                    df_upload = df_upload[required_cols].dropna()
                    
                    st.write(f"📄 Found {len(df_upload)} recipe mappings. Preview:")
                    st.dataframe(df_upload.head())
                    
                    if st.button("🚀 Sync Recipes to Database", type="primary"):
                        try:
                            with engine.begin() as conn:
                                # 1. Ensure all FG SKUs exist in the master table so the database doesn't reject them
                                unique_fgs = df_upload['fg_sku'].unique()
                                for fg in unique_fgs:
                                    conn.execute(text("INSERT INTO inv_fg_master (fg_sku, description) VALUES (:fg, 'Imported FG') ON CONFLICT (fg_sku) DO NOTHING"), {"fg": str(fg).strip()})
                                
                                # 2. Clear old recipes for the uploaded FGs to prevent doubling up
                                fg_tuple = tuple(unique_fgs)
                                if len(fg_tuple) == 1:
                                    conn.execute(text(f"DELETE FROM inv_bom WHERE fg_sku = '{fg_tuple[0]}'"))
                                else:
                                    conn.execute(text(f"DELETE FROM inv_bom WHERE fg_sku IN {fg_tuple}"))

                                # 3. Insert new recipes
                                insert_query = text("INSERT INTO inv_bom (fg_sku, rm_sku, qty_required) VALUES (:fg, :rm, :qty)")
                                for index, row in df_upload.iterrows():
                                    conn.execute(insert_query, {
                                        "fg": str(row['fg_sku']).strip(), 
                                        "rm": str(row['rm_sku']).strip(),
                                        "qty": float(row['qty_required'])
                                    })
                                    
                            st.success(f"🎉 Successfully mapped {len(df_upload)} components to your Finished Goods!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Database Error: {e}")
            except Exception as e:
                st.error(f"⚠️ Error processing file: {e}")

    # ==========================================
    # TAB 1: THE DISPATCH FORM
    # ==========================================
    with tab1:
        if fg_list.empty:
            st.info("👆 You don't have any Finished Goods recipes yet. Go to the **'Manage FG Recipes'** tab to upload your mapping!")
        else:
            with st.form("dispatch_form", clear_on_submit=True):
                st.subheader("Create Outbound Consignment")
                
                c1, c2 = st.columns(2)
                with c1:
                    dispatch_date = st.date_input("Dispatch Date", datetime.today())
                    destination = st.selectbox("Destination Channel", ["Amazon FBA", "Blinkit Dark Store", "Flipkart FC", "Swiggy Instamart", "Shopify/Direct", "Other Distributor"])
                    
                with c2:
                    selected_fg = st.selectbox("Finished Good SKU (FG)", options=fg_list['fg_sku'].tolist())
                    qty_dispatch = st.number_input("Quantity to Dispatch", min_value=1, step=1)
                    
                submit_btn = st.form_submit_button("🚀 Validate & Dispatch Stock", use_container_width=True)

                if submit_btn:
                    with st.spinner("Calculating required Raw Materials..."):
                        with engine.connect() as conn:
                            # 1. GET THE RECIPE
                            recipe_df = pd.read_sql(text("SELECT rm_sku, qty_required FROM inv_bom WHERE fg_sku = :fg"), conn, params={"fg": selected_fg})
                            
                            if recipe_df.empty:
                                st.error("⚠️ Recipe missing! This FG has no Raw Materials mapped to it.")
                            else:
                                # Calculate total RM needed
                                recipe_df['total_needed'] = recipe_df['qty_required'] * qty_dispatch
                                
                                # 2. CHECK CURRENT STOCK
                                stock_df = pd.read_sql("SELECT rm_sku, SUM(qty_change) as current_stock FROM inv_ledger GROUP BY rm_sku", conn)
                                
                                # Merge and validate
                                check_df = pd.merge(recipe_df, stock_df, on='rm_sku', how='left').fillna(0)
                                check_df['shortage'] = check_df['current_stock'] - check_df['total_needed']
                                
                                failed_items = check_df[check_df['shortage'] < 0]

                                # 3. EXECUTE OR REJECT
                                if not failed_items.empty:
                                    st.error("❌ **INSUFFICIENT STOCK!** You do not have enough Raw Materials to build this consignment.")
                                    st.write("You are short on the following items:")
                                    st.dataframe(failed_items[['rm_sku', 'total_needed', 'current_stock', 'shortage']].style.format({"shortage": "{:.0f}", "current_stock": "{:.0f}"}))
                                else:
                                    try:
                                        with engine.begin() as trans_conn:
                                            # A. Log the consignment
                                            trans_conn.execute(text("""
                                                INSERT INTO inv_consignments (dispatch_date, destination, fg_sku, fg_qty_dispatched) 
                                                VALUES (:d_date, :dest, :fg, :qty)
                                            """), {"d_date": dispatch_date, "dest": destination, "fg": selected_fg, "qty": qty_dispatch})
                                            
                                            # B. Backflush the Ledger (Negative entries for RMs used)
                                            ref_str = f"DISP-{destination[:3].upper()}-{dispatch_date.strftime('%d%m')}"
                                            
                                            for index, row in recipe_df.iterrows():
                                                trans_conn.execute(text("""
                                                    INSERT INTO inv_ledger (transaction_date, transaction_type, reference_id, rm_sku, qty_change)
                                                    VALUES (:d_date, 'CONSIGNMENT', :ref, :rm, :qty_change)
                                                """), {
                                                    "d_date": dispatch_date,
                                                    "ref": ref_str,
                                                    "rm": row['rm_sku'],
                                                    "qty_change": -(row['total_needed']) # 🛑 NEGATIVE NUMBER DEDUCTS STOCK
                                                })
                                        
                                        st.success(f"🎉 Consignment Successful! Dispatched {qty_dispatch} units of `{selected_fg}` to {destination}.")
                                        st.info("The required Raw Materials have been automatically deducted from your inventory ledger.")
                                        st.balloons()
                                    except Exception as e:
                                        st.error(f"⚠️ Database transaction failed: {e}")