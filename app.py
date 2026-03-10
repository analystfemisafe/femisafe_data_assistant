import streamlit as st
import pandas as pd
from sqlalchemy import text, inspect
import os
import io
import time
import datetime
import extra_streamlit_components as stx  # 👈 IMPORT COOKIE MANAGER

# ------------------------------------------------------
# 1. PAGE SETUP (Must be the first Streamlit command)
# ------------------------------------------------------
st.set_page_config(page_title="FemiSafe Analytics", layout="wide", page_icon="📊")

# Initialize Cookie Manager (Bug Fixed: removed experimental_allow_widgets)
cookie_manager = stx.CookieManager(key="cookie_manager")

# =======================================================
# 🔐 GLOBAL LOGIN SYSTEM (With 1-Day Cookie & Secure Railway Vars)
# =======================================================
def check_password():
    """Returns `True` if the user is authenticated via session or cookie."""

    # 🛑 THE FIX: If they just clicked logout, ignore everything else
    if st.session_state.get("logout_triggered", False):
        return False

    # 1. CHECK BROWSER COOKIE FIRST
    auth_cookie = cookie_manager.get(cookie="femisafe_auth")
    if auth_cookie == "authenticated":
        st.session_state["password_correct"] = True
        return True

    # 2. CHECK SESSION STATE (Fallback)
    if st.session_state.get("password_correct", False):
        return True

    # 3. HANDLE LOGIN ATTEMPT (100% Secure for GitHub)
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        
        # Pull login credentials strictly from Railway Variables
        valid_user = os.environ.get("APP_USERNAME") 
        valid_pass = os.environ.get("APP_PASSWORD")

        # Failsafe: If variables are missing in Railway, show an error.
        if not valid_user or not valid_pass:
            st.error("🔒 Server Configuration Error: Login credentials are not set in Railway Variables.")
            st.session_state["password_correct"] = False
            return

        user_input = st.session_state.get("username", "")
        pass_input = st.session_state.get("password", "")

        # Check against Railway variables
        if user_input == valid_user and pass_input == valid_pass:
            st.session_state["password_correct"] = True
            
            # Reset the logout flag so they can log back in
            st.session_state["logout_triggered"] = False 
            
            # 🍪 SET COOKIE FOR 1 DAY
            expire_date = datetime.datetime.now() + datetime.timedelta(days=1)
            cookie_manager.set("femisafe_auth", "authenticated", expires_at=expire_date)
            
            # Clear sensitive info from session state
            if "password" in st.session_state:
                del st.session_state["password"] 
            if "username" in st.session_state:
                del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    # 4. SHOW LOGIN FORM
    st.markdown(
        """
        <style>
        .block-container { padding-top: 5rem; }
        </style>
        """, unsafe_allow_html=True
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.header("🔒 FemiSafe Analytics")
        st.write("Please log in to continue.")
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Log In", on_click=password_entered, type="primary", use_container_width=True)

        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("❌ User not found or password incorrect")

    return False

# 🛑 STOP EXECUTION IF NOT LOGGED IN
if not check_password():
    st.stop()  # <--- THIS STOPS THE REST OF THE APP FROM LOADING

# =======================================================
# ✅ APP LOGIC STARTS HERE
# =======================================================

if 'nav_mode' not in st.session_state:
    st.session_state.nav_mode = "Primary"

# ------------------------------------------------------
# 2. OPTIMIZED DB CONNECTION
# ------------------------------------------------------
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 3. SIDEBAR NAVIGATION
# ---------------------------------------------------------
with st.sidebar:
    st.header("Navigation Mode")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Primary", use_container_width=True): st.session_state.nav_mode = "Primary"
    with col2:
        if st.button("Secondary", use_container_width=True): st.session_state.nav_mode = "Secondary"
    
    st.markdown("---")
    
    if st.button("📉 T-1 Summary", use_container_width=True): st.session_state.nav_mode = "T-1"
    if st.button("🤖 Data Assistant", use_container_width=True): st.session_state.nav_mode = "Data Assistant"
    if st.button("📦 Inventory Management", use_container_width=True): st.session_state.nav_mode = "Inventory" 
    if st.button("⚙️ Admin Panel", use_container_width=True): st.session_state.nav_mode = "Admin Panel"

mode = st.session_state.nav_mode

# ------------------------------------------------------
# 4. PAGE ROUTING
# ------------------------------------------------------
if mode == "Primary":
    st.sidebar.subheader("Primary Dashboards")
    primary_choice = st.sidebar.selectbox("Choose Report",
        [
            "Overall Sales Overview", 
            "Statewise Trends", 
            "Product Performance", 
            "Special Primary Charts", 
            "Target 3 Months", 
            "Dynamic Table",
            "Dynamic Chart"
        ]
    )

    if primary_choice == "Overall Sales Overview": from pages.primary.overall_sales_overview import page; page()
    elif primary_choice == "Statewise Trends": from pages.primary.statewise_sku_trends import page; page()
    elif primary_choice == "Product Performance": from pages.primary.product_performance import page; page()
    elif primary_choice == "Special Primary Charts": from pages.primary.special_primary_charts import page; page()
    elif primary_choice == "Target 3 Months": from pages.primary.target_3_months import page; page()
    elif primary_choice == "Dynamic Table": from pages.primary.dynamic_table import page; page()
    elif primary_choice == "Dynamic Chart": from pages.primary.dynamic_chart import page; page()

# ------------------------------------------------------
# 📉 T-1 SUMMARY
# ------------------------------------------------------
elif mode == "T-1":
    st.sidebar.subheader("T-1 Analysis")
    t1_channel = st.sidebar.radio("Select Vertical", ["Sales Summary", "Ads Performance"])
    
    if t1_channel == "Sales Summary":
        t1_report = st.sidebar.selectbox("Choose Report", ["DRR (Daily Run Rate)", "Blinkit Product-wise", "Blinkit City-wise"])
        
        if t1_report == "DRR (Daily Run Rate)": 
            from pages.t1.reports.drr import show_drr; show_drr()
            
        elif t1_report == "Blinkit Product-wise": 
            from pages.secondary.blinkit.blinkit_productwise_performance import page; page()
            
        elif t1_report == "Blinkit City-wise": 
            from pages.secondary.blinkit.blinkit_citywise_performance import page; page()
            
    elif t1_channel == "Ads Performance":
        t1_report = st.sidebar.selectbox("Choose Report", ["Ad Overview", "Campaign Analysis"])
        if t1_report == "Ad Overview": from pages.t1.ad_performance import page; page()
        else: st.info("🚧 Report under construction")

# ------------------------------------------------------
# SECONDARY DASHBOARDS
# ------------------------------------------------------
elif mode == "Secondary":
    st.sidebar.subheader("Secondary Menu")
    sec_nav = st.sidebar.radio("Navigate", ["Channel Reports", "Dynamic Table"])
    
    st.sidebar.markdown("---")
    
    # 🛑 NEW: Route to Dynamic Table if selected
    if sec_nav == "Dynamic Table":
        from pages.secondary.dynamic_table import page; page()
        
    # 🏪 EXISTING: Route to specific channel dashboards
    else:
        st.sidebar.subheader("Select Channel")
        channel_choice = st.sidebar.radio("Channel", ["Amazon", "Blinkit", "Shopify", "Flipkart", "Swiggy"])
        
        if channel_choice == "Blinkit":
            report_options = ["Sales Dashboard", "Productwise Performance", "Citywise Performance", "Ad Spend Report", "Organic Share", "Aging Report", "Weekly Sales Analysis"]
        elif channel_choice == "Amazon":
            report_options = ["Sales Dashboard", "Productwise Sales", "Ad Spend Report", "Organic Share"]
        elif channel_choice == "Shopify":
            report_options = ["Sales Dashboard", "Ad Report"]
        elif channel_choice == "Swiggy":
            report_options = ["Sales Dashboard", "Ad Report"]
        elif channel_choice == "Flipkart":
            report_options = ["Sales Dashboard", "Ad Report"]
        else: report_options = ["Sales Dashboard"]

        report_choice = st.sidebar.selectbox("Select Report", report_options)

        if channel_choice == "Amazon":
            if report_choice == "Sales Dashboard": from pages.secondary.amazon.sales_dashboard import page; page()
            elif report_choice == "Productwise Sales": from pages.secondary.amazon.productwise_sales import page; page()
            elif report_choice == "Ad Spend Report": from pages.secondary.amazon.ad_spend_report import page; page()
            elif report_choice == "Organic Share": from pages.secondary.amazon.organic_share import page; page()
        elif channel_choice == "Blinkit":
            if report_choice == "Sales Dashboard": from pages.secondary.blinkit.blinkit_sales_dashboard import page; page()
            elif report_choice == "Productwise Performance": from pages.secondary.blinkit.blinkit_productwise_performance import page; page()
            elif report_choice == "Citywise Performance": from pages.secondary.blinkit.blinkit_citywise_performance import page; page()
            elif report_choice == "Ad Spend Report": from pages.secondary.blinkit.blinkit_ad_spend_report import page; page()
            elif report_choice == "Organic Share": from pages.secondary.blinkit.blinkit_organic_share import page; page()
            elif report_choice == "Aging Report": from pages.secondary.blinkit.blinkit_aging_report import page; page()
            elif report_choice == "Weekly Sales Analysis": from pages.secondary.blinkit.blinkit_weekly_sales_analysis import page; page()
        elif channel_choice == "Shopify":
            if report_choice == "Sales Dashboard": from pages.secondary.shopify.sales_dashboard import page; page()
            else: 
                try: from pages.secondary.shopify.ad_report import page; page()
                except: st.write("Page under construction")
        elif channel_choice == "Flipkart":
            if report_choice == "Sales Dashboard": from pages.secondary.flipkart.sales_dashboard import page; page()
            else: 
                try: from pages.secondary.flipkart.ad_report import page; page()
                except: st.write("Page under construction")
        elif channel_choice == "Swiggy":
            if report_choice == "Sales Dashboard": from pages.secondary.swiggy.sales_dashboard import page; page()
            elif report_choice == "Ad Report": from pages.secondary.swiggy.ad_spend_report import page; page()

elif mode == "Data Assistant":
    from pages.data_assistant.data_assistant import page; page()
    
# ------------------------------------------------------
# 📦 INVENTORY MANAGEMENT
# ------------------------------------------------------
elif mode == "Inventory":
    st.sidebar.subheader("Inventory Menu")
    inv_choice = st.sidebar.radio("Navigate", ["Current Inventory", "Goods Receiving (GRN)", "Create Consignment"])
    
    if inv_choice == "Current Inventory":
        from pages.inventory.current_inventory import page; page()
        
    elif inv_choice == "Goods Receiving (GRN)":
        from pages.inventory.grn import page; page()
        
    elif inv_choice == "Create Consignment":
        from pages.inventory.consignment import page; page()   

# ------------------------------------------------------
# 5. SUPER ADMIN PANEL (SECURE LOCK 🔒)
# ------------------------------------------------------
elif mode == "Admin Panel":
    st.title("🔐 Admin Security Check")
    
    # 1. DEFINE YOUR PASSWORD HERE
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "femisafe2026") 
    
    # 2. CHECK LOGIN STATUS
    if "admin_unlocked" not in st.session_state:
        st.session_state.admin_unlocked = False

    # 3. SHOW LOGIN SCREEN (If locked)
    if not st.session_state.admin_unlocked:
        st.markdown("### 🛑 Restricted Area")
        st.info("This panel allows editing database records. Double-authentication required.")
        
        password_input = st.text_input("Enter Admin Password:", type="password")
        
        if st.button("Unlock Panel"):
            if password_input == ADMIN_PASSWORD:
                st.session_state.admin_unlocked = True
                st.success("✅ Access Granted!")
                st.rerun()  # Refresh to show the panel
            else:
                st.error("❌ Incorrect Password.")
                
    # 4. SHOW ADMIN PANEL (If Unlocked)
    else:
        st.success("🔓 Admin Mode Active")
        if st.button("🔒 Lock Panel"):
            st.session_state.admin_unlocked = False
            st.rerun()

        st.markdown("---")
        
        # Helper to fetch tables
        @st.cache_data(ttl=3600)
        def get_all_tables():
            engine = get_db_engine()
            if engine:
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")).fetchall()
                        # We bring all tables now, not just ones with 'femisafe', so you can see 'inv_ledger', etc.
                        return [row[0] for row in result] 
                except Exception as e:
                    st.error(f"Error fetching tables: {e}")
                    return []
            return []

        all_tables = get_all_tables()
        
        if not all_tables:
            st.error("⚠️ No tables found in database!")
        else:
            # 🗂️ FIVE TABS FOR COMPLETE CONTROL (Visual Editor Added Here)
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["📤 Smart Uploader", "🗑️ Data Cleaner", "⚡ SQL Editor", "🔧 Schema Fixer", "🗂️ Visual Editor"])

            # =========================================================
            # TAB 1: SMART UPLOADER
            # =========================================================
            with tab1:
                st.subheader("Upload New Records")
                selected_table = st.selectbox("Select Target Table", all_tables)
                
                col_opt1, col_opt2 = st.columns(2)
                with col_opt1:
                    create_table_mode = st.checkbox("⚠️ First Time Upload? (Create Table Schema)", help="Check this if the table is empty.")
                
                uploaded_file = st.file_uploader(f"Upload CSV/Excel for `{selected_table}`", type=["csv", "xlsx"])
                
                if uploaded_file:
                    try:
                        # 1. READ FILE
                        if uploaded_file.name.endswith('.csv'):
                            df = pd.read_csv(uploaded_file)
                        else:
                            df = pd.read_excel(uploaded_file)
                        
                        df.columns = df.columns.str.strip()
                        df = df.loc[:, ~df.columns.duplicated()] # Init Dedupe
                        
                        clean_table_name = selected_table.lower()
                        rename_map = {} 

                        # 🧹 SWIGGY LOGIC
                        if "swiggy" in clean_table_name and "ad" in clean_table_name:
                            st.info("🧹 Swiggy Mode: Auto-Detecting Headers & Cleaning.")
                            if "metrics_date" not in [str(c).lower() for c in df.columns]:
                                try:
                                    uploaded_file.seek(0)
                                    header_idx = -1
                                    for i, line in enumerate(io.TextIOWrapper(uploaded_file, encoding='utf-8')):
                                        if "METRICS_DATE" in line or "CAMPAIGN_NAME" in line:
                                            header_idx = i; break
                                        if i > 30: break 
                                    uploaded_file.seek(0)
                                    if header_idx >= 0: df = pd.read_csv(uploaded_file, header=header_idx)
                                    else: df = pd.read_csv(uploaded_file)
                                    df = df.loc[:, ~df.columns.duplicated()] 
                                except Exception as e: st.warning(f"Header detect warning: {e}")

                            df = df.loc[:, ~df.columns.str.contains('^Unnamed', case=False)]
                            df = df.drop(columns=[c for c in df.columns if str(c).startswith("_")], errors='ignore')
                            if len(df.columns) >= 37: df = df.iloc[:, :37]

                            rename_map = {
                                "METRICS_DATE": "date", "CAMPAIGN_ID": "campaign_id", "CAMPAIGN_NAME": "campaign_name",
                                "TOTAL_BUDGET_BURNT": "estimated_budget_consumed", "TOTAL_DIRECT_GMV_7_DAYS": "direct_sales",
                                "PRODUCT_NAME": "product_name", "TOTAL_IMPRESSIONS": "impressions", "TOTAL_CLICKS": "clicks",
                                "TOTAL_CTR": "ctr", "TOTAL_ROI": "roas", "Week": "week", "Month": "month", "SKU": "sku"
                            }
                            df.rename(columns=rename_map, inplace=True)
                            for col in ["estimated_budget_consumed", "direct_sales", "roas"]:
                                if col in df.columns: df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[₹,%]', '', regex=True), errors='coerce').fillna(0)

                        # 🧩 OTHER CHANNELS
                        elif "blinkit" in clean_table_name and "ad" in clean_table_name:
                            df.columns = [str(c).strip().lower() for c in df.columns]
                            rename_map = {
                                "campaign id": "campaign_id", "campaign name": "campaign_name", "ad spend data": "ad_spend_data",
                                "product name": "product_name", "estimated budget consumed": "estimated_budget_consumed",
                                "direct sales": "direct_sales", "direct roas": "direct_roas"
                            }
                            df.rename(columns=rename_map, inplace=True)

                        elif "blinkit" in clean_table_name and "sales" in clean_table_name:
                            df.columns = [str(c).strip().lower() for c in df.columns]
                            rename_map = { "order date": "order_date", "product name": "product", "feeder warehouse": "feeder_wh", "net revenue": "net_revenue" }
                            df.rename(columns=rename_map, inplace=True)
                            
                        elif "shopify" in clean_table_name:
                            df.columns = [str(c).strip().lower() for c in df.columns]
                            rename_map = { 'product title at time of sale': 'product_title_at_time', 'gross sales': 'gross_sales', 'units sold': 'units_sold', 'order date': 'order_date' }
                            df.rename(columns=rename_map, inplace=True)

                        elif "amazon" in clean_table_name:
                            df.columns = [str(c).strip().lower() for c in df.columns]
                            rename_map = { '(parent) asin': 'parent_asin', 'ordered product sales': 'ordered_product_sales', 'units ordered': 'units_ordered' }
                            df.rename(columns=rename_map, inplace=True)
                        
                        elif "flipkart" in clean_table_name:
                            df.columns = [str(c).strip().lower() for c in df.columns]
                            pass

                        # ⚠️ FINAL PREP
                        df = df.loc[:, ~df.columns.duplicated()]
                        
                        for col in df.columns:
                            if "date" in str(col).lower(): df[col] = pd.to_datetime(df[col], errors='coerce')

                        st.write(f"✅ Ready to upload {len(df)} rows. Columns: {list(df.columns)}")
                        
                        if st.button("🚀 Confirm Upload"):
                            engine = get_db_engine()
                            if engine:
                                try:
                                    if create_table_mode:
                                        df.to_sql(selected_table, engine, if_exists='replace', index=False)
                                        st.success(f"✅ Table created and {len(df)} rows uploaded!")
                                    else:
                                        df.to_sql(selected_table, engine, if_exists='append', index=False)
                                        st.success(f"✅ Added {len(df)} rows to `{selected_table}`!")
                                except Exception as e: st.error(f"Upload failed: {e}")
                    except Exception as e: st.error(f"Error processing file: {e}")

            # =========================================================
            # TAB 2: DATA CLEANER (Delete Last N Rows)
            # =========================================================
            with tab2:
                st.subheader("🗑️ Delete Recent Rows")
                clean_table = st.selectbox("Select Table", all_tables, key="clean_tab_select")
                
                if clean_table:
                    engine = get_db_engine()
                    with engine.connect() as conn:
                        sort_col = "none"
                        try:
                            query = text(f'SELECT * FROM "{clean_table}" ORDER BY id DESC LIMIT 20')
                            sort_col = "id"
                        except:
                            try:
                                query = text(f'SELECT * FROM "{clean_table}" ORDER BY date DESC LIMIT 20')
                                sort_col = "date"
                            except:
                                query = text(f'SELECT * FROM "{clean_table}" LIMIT 20')

                        try:
                            df_view = pd.read_sql(query, conn)
                            st.dataframe(df_view)
                            
                            col_del_1, col_del_2 = st.columns(2)
                            with col_del_1:
                                rows_to_del = st.number_input("Rows to Delete (Top N)", min_value=0, max_value=50, value=0)
                            with col_del_2:
                                st.write("Action")
                                if st.button("🚨 DELETE ROWS", type="primary"):
                                    if rows_to_del > 0 and sort_col == "id":
                                        ids = tuple(df_view['id'].head(rows_to_del).tolist())
                                        if len(ids) == 1:
                                            conn.execute(text(f'DELETE FROM "{clean_table}" WHERE id = {ids[0]}'))
                                        else:
                                            conn.execute(text(f'DELETE FROM "{clean_table}" WHERE id IN {ids}'))
                                        conn.commit()
                                        st.success(f"Deleted {rows_to_del} rows.")
                                        st.rerun()
                                    elif sort_col != "id":
                                        st.error("Table has no 'id' column. Use SQL Editor.")
                        except Exception as e:
                            st.error(f"Cannot read table: {e}")

            # =========================================================
            # TAB 3: SQL EDITOR (Power User)
            # =========================================================
            with tab3:
                st.subheader("⚡ SQL Commander")
                col_sql_1, col_sql_2 = st.columns([3, 1])
                with col_sql_1:
                    sql_query = st.text_area("SQL Query", height=150, placeholder="SELECT * FROM femisafe_flipkart_salesdata LIMIT 10;")
                with col_sql_2:
                    st.write("Settings")
                    allow_unsafe = st.checkbox("Enable DELETE", value=False)
                    run_btn = st.button("▶️ RUN", use_container_width=True)
                
                if run_btn and sql_query:
                    forbidden = ["delete", "update", "drop", "truncate", "insert"]
                    if any(w in sql_query.lower() for w in forbidden) and not allow_unsafe:
                        st.error("🔒 Security Lock: Enable checkbox to run destructive queries.")
                    else:
                        engine = get_db_engine()
                        try:
                            with engine.connect() as conn:
                                if sql_query.strip().lower().startswith("select"):
                                    res = pd.read_sql(text(sql_query), conn)
                                    st.success(f"Returned {len(res)} rows")
                                    st.dataframe(res)
                                else:
                                    res = conn.execute(text(sql_query))
                                    conn.commit()
                                    st.success(f"Executed. Rows affected: {res.rowcount}")
                        except Exception as e: st.error(f"SQL Error: {e}")

            # =========================================================
            # TAB 4: SCHEMA FIXER (One-Click Repair)
            # =========================================================
            with tab4:
                st.subheader("🔧 Quick Fixes")
                
                col_fix_1, col_fix_2 = st.columns(2)
                
                with col_fix_1:
                    st.write("**Blinkit: Add Missing Columns**")
                    if st.button("Fix Blinkit Schema"):
                        engine = get_db_engine()
                        with engine.connect() as conn:
                            try:
                                conn.execute(text("ALTER TABLE femisafe_blinkit_addata ADD COLUMN IF NOT EXISTS targeting_type TEXT, ADD COLUMN IF NOT EXISTS match_type TEXT;"))
                                conn.commit()
                                st.success("✅ Fixed!")
                            except Exception as e: st.error(f"Error: {e}")

                with col_fix_2:
                    st.write("**Flipkart: Fix Column Names**")
                    if st.button("Fix Flipkart Columns"):
                        engine = get_db_engine()
                        with engine.connect() as conn:
                            try:
                                conn.execute(text('ALTER TABLE femisafe_flipkart_salesdata RENAME COLUMN "Order Date" TO "order date";'))
                                conn.execute(text('ALTER TABLE femisafe_flipkart_salesdata RENAME COLUMN "Net Revenue" TO "net revenue";'))
                                conn.commit()
                                st.success("✅ Fixed!")
                            except Exception as e: st.error(f"Error (likely already fixed): {e}")

            # =========================================================
            # TAB 5: THE NEW VISUAL TABLE EDITOR 🗂️
            # =========================================================
            with tab5:
                st.subheader("🗂️ Live Database Editor")
                st.markdown("Double-click any cell to edit. Add new rows at the bottom. Select a row and press `Delete` on your keyboard to remove it.")

                selected_edit_table = st.selectbox("Select a table to edit:", all_tables, key="visual_edit_select")

                if selected_edit_table:
                    engine = get_db_engine()
                    try:
                        # Load data
                        df_edit = pd.read_sql(f'SELECT * FROM "{selected_edit_table}" ORDER BY 1', engine)
                        
                        # Find the primary key column (Defaults to 'id' or the first column)
                        pk_col = "id" if "id" in df_edit.columns else df_edit.columns[0]
                        editor_key = f"editor_{selected_edit_table}"
                        
                        # The Interactive Component
                        edited_df = st.data_editor(
                            df_edit, 
                            num_rows="dynamic",
                            use_container_width=True,
                            key=editor_key
                        )

                        # The Save Button
                        if st.button(f"💾 Save Changes to {selected_edit_table}", type="primary"):
                            changes = st.session_state[editor_key]
                            try:
                                with engine.begin() as conn:
                                    # 1. Process Edits
                                    for row_idx, edits in changes["edited_rows"].items():
                                        pk_value = df_edit.iloc[row_idx][pk_col]
                                        for col, new_val in edits.items():
                                            query = text(f'UPDATE "{selected_edit_table}" SET "{col}" = :val WHERE "{pk_col}" = :pk')
                                            conn.execute(query, {"val": new_val, "pk": str(pk_value)})
                                    
                                    # 2. Process Deletions
                                    for row_idx in changes["deleted_rows"]:
                                        pk_value = df_edit.iloc[row_idx][pk_col]
                                        query = text(f'DELETE FROM "{selected_edit_table}" WHERE "{pk_col}" = :pk')
                                        conn.execute(query, {"pk": str(pk_value)})
                                        
                                    # 3. Process Additions
                                    for new_row in changes["added_rows"]:
                                        cols = ", ".join([f'"{k}"' for k in new_row.keys()])
                                        placeholders = ", ".join([f":{k}" for k in new_row.keys()])
                                        query = text(f'INSERT INTO "{selected_edit_table}" ({cols}) VALUES ({placeholders})')
                                        conn.execute(query, new_row)
                                        
                                st.success(f"🎉 Successfully synced all changes to `{selected_edit_table}`!")
                                time.sleep(1)
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"⚠️ Database Error: {e}")
                                
                    except Exception as e:
                        st.error(f"Cannot load table for editing: {e}")

# =======================================================
# 🚪 LOGOUT BUTTON (Rendered absolutely last in the sidebar)
# =======================================================
with st.sidebar:
    st.markdown('<div style="margin-top: 40vh;"></div>', unsafe_allow_html=True)
    st.markdown("---")
    
    if st.button("🚪 Logout"):
        # 🛑 THE FIX: Set the flag so the app ignores the cookie while deleting
        st.session_state["logout_triggered"] = True
        st.session_state["password_correct"] = False
        cookie_manager.delete("femisafe_auth") 
        time.sleep(0.5) 
        st.rerun()