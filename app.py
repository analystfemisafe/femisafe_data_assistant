import streamlit as st
import pandas as pd
from sqlalchemy import text, inspect
import os
import io

# ------------------------------------------------------
# 1. PAGE SETUP
# ------------------------------------------------------
st.set_page_config(page_title="FemiSafe Analytics", layout="wide", page_icon="📊")

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
    if st.button("⚙️ Admin Panel", use_container_width=True): st.session_state.nav_mode = "Admin Panel"

mode = st.session_state.nav_mode 

# ------------------------------------------------------
# 4. PAGE ROUTING
# ------------------------------------------------------
if mode == "Primary":
    st.sidebar.subheader("Primary Dashboards")
    primary_choice = st.sidebar.selectbox("Choose Report",
        ["Overall Sales Overview", "Statewise Trends", "Product Performance", 
         "Special Primary Charts", "Target 3 Months", "Dynamic Table"])

    if primary_choice == "Overall Sales Overview": from pages.primary.overall_sales_overview import page; page()
    elif primary_choice == "Statewise Trends": from pages.primary.statewise_sku_trends import page; page()
    elif primary_choice == "Product Performance": from pages.primary.product_performance import page; page()
    elif primary_choice == "Special Primary Charts": from pages.primary.special_primary_charts import page; page()
    elif primary_choice == "Target 3 Months": from pages.primary.target_3_months import page; page()
    elif primary_choice == "Dynamic Table": from pages.primary.dynamic_table import page; page()

# ------------------------------------------------------
# 📉 T-1 SUMMARY (UPDATED LINKS)
# ------------------------------------------------------
elif mode == "T-1":
    st.sidebar.subheader("T-1 Analysis")
    t1_channel = st.sidebar.radio("Select Vertical", ["Sales Summary", "Ads Performance"])
    
    if t1_channel == "Sales Summary":
        t1_report = st.sidebar.selectbox("Choose Report", ["DRR (Daily Run Rate)", "Blinkit Product-wise", "Blinkit City-wise"])
        
        if t1_report == "DRR (Daily Run Rate)": 
            from pages.t1.reports.drr import show_drr; show_drr()
            
        elif t1_report == "Blinkit Product-wise": 
            # 👇 LINKED TO SECONDARY PAGE
            from pages.secondary.blinkit.blinkit_productwise_performance import page
            page()
            
        elif t1_report == "Blinkit City-wise": 
            # 👇 LINKED TO SECONDARY PAGE
            from pages.secondary.blinkit.blinkit_citywise_performance import page
            page()
            
    elif t1_channel == "Ads Performance":
        t1_report = st.sidebar.selectbox("Choose Report", ["Ad Overview", "Campaign Analysis"])
        if t1_report == "Ad Overview": from pages.t1.ad_performance import page; page()
        else: st.info("🚧 Report under construction")

# ------------------------------------------------------
# SECONDARY DASHBOARDS
# ------------------------------------------------------
elif mode == "Secondary":
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
# 5. SMART ADMIN PANEL (New Table Creator)
# ------------------------------------------------------
elif mode == "Admin Panel":
    st.title("⚙️ Admin Panel (Live Database)")
    
    @st.cache_data(ttl=3600)
    def get_all_tables():
        engine = get_db_engine()
        if engine:
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")).fetchall()
                    return [row[0] for row in result]
            except Exception as e:
                st.error(f"Error fetching tables: {e}")
                return []
        return []

    all_tables = get_all_tables()
    
    if not all_tables:
        st.error("⚠️ No tables found!")
    else:
        tab1, tab2 = st.tabs(["📤 Upload Data", "🔍 Database Inspector"])

        with tab1:
            st.subheader("Upload New Records")
            selected_table = st.selectbox("Select Target Table", all_tables)
            
            # --- OPTIONS FOR UPLOAD ---
            col_opt1, col_opt2 = st.columns(2)
            with col_opt1:
                # 👇 THIS IS THE KEY OPTION FOR YOU
                create_table_mode = st.checkbox("⚠️ First Time Upload? (Create Table Schema)", help="Check this if the table in the database is empty and has no columns yet.")
            
            uploaded_file = st.file_uploader(f"Upload CSV/Excel for `{selected_table}`", type=["csv", "xlsx"])
            
            if uploaded_file:
                try:
                    # 1. READ FILE
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)
                    
                    df = df.loc[:, ~df.columns.duplicated()] # Init Dedupe
                    
                    clean_table_name = selected_table.lower()
                    rename_map = {} 

                    # ----------------------------------------
                    # 🧹 SWIGGY CLEANING LOGIC
                    # ----------------------------------------
                    if "swiggy" in clean_table_name and "ad" in clean_table_name:
                        st.info("🧹 Swiggy Mode: Auto-Detecting Headers & Cleaning.")
                        
                        # A. Header Detection
                        if "metrics_date" not in [str(c).lower() for c in df.columns]:
                            try:
                                uploaded_file.seek(0)
                                header_idx = -1
                                for i, line in enumerate(io.TextIOWrapper(uploaded_file, encoding='utf-8')):
                                    if "METRICS_DATE" in line or "CAMPAIGN_NAME" in line:
                                        header_idx = i
                                        break
                                    if i > 30: break 
                                
                                uploaded_file.seek(0)
                                if header_idx >= 0:
                                    df = pd.read_csv(uploaded_file, header=header_idx)
                                else:
                                    df = pd.read_csv(uploaded_file)
                                
                                df = df.loc[:, ~df.columns.duplicated()] 
                            except Exception as e:
                                st.warning(f"Header detect warning: {e}")

                        # B. Drop Garbage
                        df = df.loc[:, ~df.columns.str.contains('^Unnamed', case=False)]
                        df = df.drop(columns=[c for c in df.columns if str(c).startswith("_")], errors='ignore')

                        # C. Keep First 37 Cols (as requested)
                        if len(df.columns) >= 37:
                            df = df.iloc[:, :37]

                        # D. Mapping
                        rename_map = {
                            "METRICS_DATE": "date",
                            "CAMPAIGN_ID": "campaign_id",
                            "CAMPAIGN_NAME": "campaign_name",
                            "TOTAL_BUDGET_BURNT": "estimated_budget_consumed", 
                            "TOTAL_DIRECT_GMV_7_DAYS": "direct_sales",
                            "PRODUCT_NAME": "product_name",
                            "TOTAL_IMPRESSIONS": "impressions",
                            "TOTAL_CLICKS": "clicks",
                            "TOTAL_CTR": "ctr",
                            "TOTAL_ROI": "roas",
                            "Week": "week", "Month": "month", "SKU": "sku"
                        }
                        
                        # Apply Rename
                        df.rename(columns=rename_map, inplace=True)
                        
                        # Clean Numbers
                        cols_to_clean = ["estimated_budget_consumed", "direct_sales", "roas"]
                        for col in cols_to_clean:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[₹,%]', '', regex=True), errors='coerce').fillna(0)

                    # ----------------------------------------
                    # 🧩 OTHER CHANNELS
                    # ----------------------------------------
                    elif "blinkit" in clean_table_name and "ad" in clean_table_name:
                        df.columns = [str(c).strip().lower() for c in df.columns]
                        rename_map = {
                            "campaign id": "campaign_id", "campaign name": "campaign_name",
                            "ad spend data": "ad_spend_data", "product name": "product_name",
                            "estimated budget consumed": "estimated_budget_consumed",
                            "direct sales": "direct_sales", "direct roas": "direct_roas"
                        }
                        df.rename(columns=rename_map, inplace=True)

                    elif "blinkit" in clean_table_name and "sales" in clean_table_name:
                        df.columns = [str(c).strip().lower() for c in df.columns]
                        rename_map = {
                            "order date": "order_date", "product name": "product",
                            "feeder warehouse": "feeder_wh", "net revenue": "net_revenue"
                        }
                        df.rename(columns=rename_map, inplace=True)
                        
                    elif "shopify" in clean_table_name:
                        df.columns = [str(c).strip().lower() for c in df.columns]
                        rename_map = {
                            'product title at time of sale': 'product_title_at_time',
                            'gross sales': 'gross_sales', 'units sold': 'units_sold',
                            'order date': 'order_date'
                        }
                        df.rename(columns=rename_map, inplace=True)

                    elif "amazon" in clean_table_name:
                        df.columns = [str(c).strip().lower() for c in df.columns]
                        rename_map = {
                            '(parent) asin': 'parent_asin',
                            'ordered product sales': 'ordered_product_sales',
                            'units ordered': 'units_ordered'
                        }
                        df.rename(columns=rename_map, inplace=True)

                    # ----------------------------------------
                    # ⚠️ FINAL PREP
                    # ----------------------------------------
                    df = df.loc[:, ~df.columns.duplicated()]

                    # Date Fix
                    for col in df.columns:
                        if "date" in str(col).lower():
                            df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')

                    st.write(f"✅ Ready to upload {len(df)} rows. Columns: {list(df.columns)}")
                    
                    if st.button("🚀 Confirm Upload"):
                        engine = get_db_engine()
                        if engine:
                            try:
                                # 👇 SMART UPLOAD LOGIC
                                if create_table_mode:
                                    # REPLACE: Creates the table structure from scratch
                                    df.to_sql(selected_table, engine, if_exists='replace', index=False)
                                    st.success(f"✅ Table created and {len(df)} rows uploaded to `{selected_table}`!")
                                else:
                                    # APPEND: Adds to existing table (Standard)
                                    df.to_sql(selected_table, engine, if_exists='append', index=False)
                                    st.success(f"✅ Added {len(df)} rows to `{selected_table}`!")
                                    
                            except Exception as e:
                                st.error(f"Upload failed: {e}")
                                
                except Exception as e:
                    st.error(f"Error processing file: {e}")

        with tab2:
            st.subheader("👀 Database Inspector")
            inspect_table = st.selectbox("Choose Table", all_tables, key="inspect")
            if st.button(f"Load Data for {inspect_table}"):
                engine = get_db_engine()
                with engine.connect() as conn:
                    df_view = pd.read_sql(text(f'SELECT * FROM "{inspect_table}" LIMIT 50'), conn)
                    st.dataframe(df_view)