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
    st.title("📥 Goods Receiving Note (GRN)")
    st.markdown("Log incoming stock or add/update Raw Materials in your catalog.")

    engine = get_db_engine()
    if not engine:
        st.error("⚠️ Database connection failed.")
        return

    # 1. Fetch available RM SKUs
    with engine.connect() as conn:
        try:
            rm_list = pd.read_sql("SELECT rm_sku, description FROM inv_rm_master", conn)
        except Exception as e:
            st.warning("⚠️ Could not fetch RM Master Data. Please ensure the database tables are created.")
            rm_list = pd.DataFrame()

    # Create Tabs for the UI
    tab1, tab2 = st.tabs(["📥 Log Incoming Stock (GRN)", "➕ Add / Update RM Catalog"])

    # ==========================================
    # TAB 2: CREATE / UPDATE RAW MATERIAL CATALOG
    # ==========================================
    with tab2:
        st.subheader("Manage Raw Material Catalog")
        
        with st.expander("✍️ Option 1: Add/Update a Single RM Manually", expanded=False):
            with st.form("new_rm_form", clear_on_submit=True):
                new_sku = st.text_input("RM SKU (e.g., BOX-PINK-01)")
                new_desc = st.text_input("Description (e.g., Small Pink Box)")
                
                if st.form_submit_button("✅ Save SKU"):
                    if not new_sku or not new_desc:
                        st.error("⚠️ Please fill in both the SKU and the Description.")
                    else:
                        try:
                            upsert_query = text("""
                                INSERT INTO inv_rm_master (rm_sku, description) 
                                VALUES (:sku, :desc)
                                ON CONFLICT (rm_sku) DO UPDATE SET description = EXCLUDED.description;
                            """)
                            with engine.begin() as conn:
                                conn.execute(upsert_query, {"sku": new_sku.strip(), "desc": new_desc.strip()})
                            st.success(f"🎉 Saved `{new_sku}` to your catalog!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Error saving SKU: {e}")

        st.markdown("---")
        st.subheader("📁 Option 2: Bulk Upload via File")
        uploaded_file = st.file_uploader("Upload RM Master File (Required columns: rm_sku, description)", type=["csv", "xlsx"])
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'): df_upload = pd.read_csv(uploaded_file)
                else: df_upload = pd.read_excel(uploaded_file)
                
                df_upload.columns = df_upload.columns.str.strip().str.lower()
                
                if 'rm_sku' not in df_upload.columns:
                    st.error("⚠️ Error: Your file must contain a column named `rm_sku`.")
                else:
                    if 'description' not in df_upload.columns: df_upload['description'] = "Bulk Uploaded RM"
                    df_upload = df_upload[['rm_sku', 'description']].dropna(subset=['rm_sku'])
                    
                    st.write(f"📄 Found {len(df_upload)} rows. Preview:")
                    st.dataframe(df_upload.head())
                    
                    if st.button("🚀 Confirm & Force Sync Data", type="primary"):
                        upsert_query = text("""
                            INSERT INTO inv_rm_master (rm_sku, description) 
                            VALUES (:sku, :desc)
                            ON CONFLICT (rm_sku) DO UPDATE SET description = EXCLUDED.description;
                        """)
                        try:
                            with engine.begin() as conn:
                                for index, row in df_upload.iterrows():
                                    conn.execute(upsert_query, {"sku": str(row['rm_sku']).strip(), "desc": str(row['description']).strip()})
                            st.success(f"🎉 Successfully synced {len(df_upload)} Raw Materials!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Database Error: {e}")
            except Exception as e:
                st.error(f"⚠️ Error processing file: {e}")

    # ==========================================
    # TAB 1: THE GRN FORM (Receive Multiple Stocks)
    # ==========================================
    with tab1:
        if rm_list.empty:
            st.info("👆 You don't have any Raw Materials in the system yet. Go to the **'Add / Update RM Catalog'** tab first!")
        else:
            st.subheader("Add Stock to Inventory")
            
            # General details for the entire GRN batch
            c1, c2 = st.columns(2)
            with c1:
                grn_date = st.date_input("Receiving Date", datetime.today())
            with c2:
                ref_id = st.text_input("Invoice / Ref ID (Optional)", placeholder="e.g., PO-1024")

            st.write("##### 🛒 Line Items")
            st.caption("Tip: Use the table below to log multiple items. Click the row number to delete a row. A new blank row automatically appears at the bottom!")
            
            # Start the table with 3 empty rows by default
            default_data = pd.DataFrame(
                [{"RM SKU": None, "Quantity": None, "Total Cost (₹)": None, "Bin No.": "", "Remarks": ""}] * 3
            )

            # The Interactive Data Editor
            edited_df = st.data_editor(
                default_data,
                num_rows="dynamic", # This allows the user to add infinite rows!
                column_config={
                    "RM SKU": st.column_config.SelectboxColumn(
                        "Raw Material SKU *",
                        help="Select the SKU from the dropdown",
                        options=rm_list['rm_sku'].tolist(),
                        required=True
                    ),
                    "Quantity": st.column_config.NumberColumn(
                        "Quantity *", min_value=1, step=1, required=True
                    ),
                    "Total Cost (₹)": st.column_config.NumberColumn(
                        "Total Cost / COGS (₹)", min_value=0.0, step=1.0
                    ),
                    "Bin No.": st.column_config.TextColumn("Bin No. (Optional)"),
                    "Remarks": st.column_config.TextColumn("Remarks (Optional)")
                },
                use_container_width=True,
                hide_index=False,
                key="grn_data_editor"
            )

            # Submit Button
            submit_btn = st.button("✅ Save GRN & Update Stock", type="primary", use_container_width=True)

            if submit_btn:
                # 1. Clean up the data: Drop rows where SKU or Quantity wasn't filled out
                valid_rows = edited_df.dropna(subset=["RM SKU", "Quantity"])
                valid_rows = valid_rows[valid_rows["RM SKU"].astype(str).str.strip() != ""]
                valid_rows = valid_rows[valid_rows["Quantity"] > 0]

                if valid_rows.empty:
                    st.error("⚠️ Please fill in at least one valid line item (SKU and Quantity are required).")
                else:
                    insert_query = text("""
                        INSERT INTO inv_ledger (transaction_date, transaction_type, reference_id, rm_sku, qty_change, unit_cost, bin_no, remark)
                        VALUES (:t_date, 'GRN', :ref, :sku, :qty, :cost, :bin, :rem)
                    """)
                    
                    try:
                        with engine.begin() as conn: 
                            for index, row in valid_rows.iterrows():
                                sku = row["RM SKU"]
                                qty = row["Quantity"]
                                
                                # Safe calculation for total cost
                                total_cost = row["Total Cost (₹)"] if pd.notna(row["Total Cost (₹)"]) else 0.0
                                unit_cost = total_cost / qty if qty > 0 else 0
                                
                                # Safe extraction for text fields
                                bin_no = row["Bin No."] if pd.notna(row["Bin No."]) else ""
                                remark = row["Remarks"] if pd.notna(row["Remarks"]) else ""

                                conn.execute(insert_query, {
                                    "t_date": grn_date,
                                    "ref": ref_id.strip() if ref_id else "", 
                                    "sku": sku,
                                    "qty": qty,
                                    "cost": unit_cost,
                                    "bin": str(bin_no).strip(),
                                    "rem": str(remark).strip()
                                })
                        
                        st.success(f"🎉 Success! Added {len(valid_rows)} line items to inventory.")
                        st.balloons()
                        
                        # Refresh the page after 1.5 seconds to clear the table for the next entry
                        time.sleep(1.5)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"⚠️ Failed to save to database: {e}")