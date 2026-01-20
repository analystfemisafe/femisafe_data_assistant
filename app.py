import streamlit as st
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text

# ------------------------------------------------------
# 1. PAGE SETUP
# ------------------------------------------------------
st.set_page_config(page_title="FemiSafe Analytics", layout="wide")

# ------------------------------------------------------
# 2. HELPER FUNCTIONS
# ------------------------------------------------------
def get_engine():
    try:
        # Looks for [postgres] in .streamlit/secrets.toml
        return create_engine(st.secrets["postgres"]["url"])
    except Exception as e:
        return None

# ------------------------------------------------------
# 3. SIDEBAR NAVIGATION
# ------------------------------------------------------
st.sidebar.markdown("""
<style>
.selector-buttons { display: flex; gap: 10px; }
.selector-buttons button { flex: 1; }
</style>
""", unsafe_allow_html=True)

st.sidebar.markdown("### Navigation Mode")

# Initialize Session State
if "nav_mode" not in st.session_state:
    st.session_state.nav_mode = "Primary"

# --- TOP BUTTONS (Primary / Secondary) ---
col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Primary"):
        st.session_state.nav_mode = "Primary"
with col2:
    if st.button("Secondary"):
        st.session_state.nav_mode = "Secondary"

# --- SPECIAL BUTTONS (Data Assistant / Admin) ---
st.sidebar.markdown("---")
if st.sidebar.button("📊 Data Assistant", use_container_width=True):
    st.session_state.nav_mode = "Data Assistant"

if st.sidebar.button("⚙️ Admin Panel", use_container_width=True):
    st.session_state.nav_mode = "Admin Panel"

# Get Current Mode
mode = st.session_state.nav_mode

# ------------------------------------------------------
# 4. PAGE LOGIC (THE IF/ELIF CHAIN)
# ------------------------------------------------------

# --- PRIMARY DASHBOARDS ---
if mode == "Primary":
    st.sidebar.subheader("Primary Dashboards")
    primary_choice = st.sidebar.selectbox(
        "Choose Report",
        ["Overall Sales Overview", "Statewise Trends", "Product Performance", 
         "Special Primary Charts", "Target 3 Months", "Dynamic Table"]
    )

    if primary_choice == "Overall Sales Overview":
        from pages.primary.overall_sales_overview import page as overall_page
        overall_page()
    elif primary_choice == "Statewise Trends":
        from pages.primary.statewise_sku_trends import page as state_page
        state_page()
    elif primary_choice == "Product Performance":
        from pages.primary.product_performance import page as product_page
        product_page()
    elif primary_choice == "Special Primary Charts":
        from pages.primary.special_primary_charts import page as special_page
        special_page()
    elif primary_choice == "Target 3 Months":
        from pages.primary.target_3_months import page as target_page
        target_page()
    elif primary_choice == "Dynamic Table":
        from pages.primary.dynamic_table import page as dynamic_page
        dynamic_page()

# --- SECONDARY DASHBOARDS ---
elif mode == "Secondary":
    st.sidebar.subheader("Select Channel")
    channel_choice = st.sidebar.radio("Channel", ["Amazon", "Blinkit", "Shopify", "Flipkart", "Swiggy"])

    # Define Options based on Channel
    if channel_choice == "Blinkit":
        report_options = ["Sales Dashboard", "Productwise Performance", "Citywise Performance", "Ad Spend Report", "Organic Share", "Aging Report", "Weekly Sales Analysis"]
    elif channel_choice == "Amazon":
        report_options = ["Sales Dashboard", "Productwise Sales", "Ad Spend Report", "Organic Share"]
    elif channel_choice == "Shopify":
        report_options = ["Sales Dashboard", "Productwise Sales", "Citywise Performance"]
    elif channel_choice == "Swiggy":
        report_options = ["Sales Dashboard", "Productwise Sales", "Citywise Performance", "Ad Spend Report", "Organic Share"]
    elif channel_choice == "Flipkart":
        report_options = ["Sales Dashboard", "Ad Spend Report"]
    else:
        report_options = ["Sales Dashboard"]

    report_choice = st.sidebar.selectbox("Select Report", report_options)

    # Note: Ensure these files exist in your folder structure
    if channel_choice == "Amazon":
        if report_choice == "Sales Dashboard": from pages.secondary.amazon.sales_dashboard import page as pg
        elif report_choice == "Productwise Sales": from pages.secondary.amazon.productwise_sales import page as pg
        elif report_choice == "Ad Spend Report": from pages.secondary.amazon.ad_spend_report import page as pg
        elif report_choice == "Organic Share": from pages.secondary.amazon.organic_share import page as pg
        else: pg = lambda: st.write("Page under construction")
        pg()

    elif channel_choice == "Blinkit":
        if report_choice == "Sales Dashboard": from pages.secondary.blinkit.blinkit_sales_dashboard import page as pg
        elif report_choice == "Productwise Performance": from pages.secondary.blinkit.blinkit_productwise_performance import page as pg
        elif report_choice == "Citywise Performance": from pages.secondary.blinkit.blinkit_citywise_performance import page as pg
        elif report_choice == "Ad Spend Report": from pages.secondary.blinkit.blinkit_ad_spend_report import page as pg
        elif report_choice == "Organic Share": from pages.secondary.blinkit.blinkit_organic_share import page as pg
        elif report_choice == "Aging Report": from pages.secondary.blinkit.blinkit_aging_report import page as pg
        elif report_choice == "Weekly Sales Analysis": from pages.secondary.blinkit.blinkit_weekly_sales_analysis import page as pg
        else: pg = lambda: st.write("Page under construction")
        pg()

    elif channel_choice == "Shopify":
        if report_choice == "Sales Dashboard": from pages.secondary.shopify.sales_dashboard import page as pg
        else: from pages.secondary.shopify.ad_report import page as pg
        pg()

    elif channel_choice == "Flipkart":
        if report_choice == "Sales Dashboard": from pages.secondary.flipkart.sales_dashboard import page as pg
        else: from pages.secondary.flipkart.ad_report import page as pg
        pg()
        
    elif channel_choice == "Swiggy":
        if report_choice == "Sales Dashboard": from pages.secondary.swiggy.sales_dashboard import page as pg
        else: from pages.secondary.swiggy.ad_report import page as pg
        pg()

# --- DATA ASSISTANT ---
elif mode == "Data Assistant":
    from pages.data_assistant.data_assistant import page as data_page
    data_page()
# ------------------------------------------------------
# 4. SMART ADMIN PANEL (Updated Mappings)
# ------------------------------------------------------
elif mode == "Admin Panel":
    st.title("⚙️ Admin Panel (Live Database)")
    
    # Function to get ALL table names from Neon
    def get_all_tables():
        engine = get_engine()
        if engine:
            try:
                # Query the system catalog for public tables
                query = text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                with engine.connect() as conn:
                    result = conn.execute(query).fetchall()
                    return [row[0] for row in result]
            except Exception as e:
                st.error(f"Error fetching tables: {e}")
                return []
        return []

    # Fetch the actual tables
    all_tables = get_all_tables()
    
    if not all_tables:
        st.error("⚠️ No tables found in the database!")
    else:
        tab1, tab2 = st.tabs(["📤 Upload Data", "🔍 Database Inspector"])

        # --- TAB 1: UPLOAD DATA ---
        with tab1:
            st.subheader("Upload New Records")
            selected_table = st.selectbox("Select Target Table", all_tables)
            
            uploaded_file = st.file_uploader(f"Upload CSV/Excel for `{selected_table}`", type=["csv", "xlsx"])
            
            if uploaded_file:
                # Load file
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.write("Preview (Raw Headers):", df.head(3))
                
                # --- STEP 1: CLEAN HEADERS (Remove spaces & lowercase) ---
                # This ensures "Ad Spend Data" becomes "ad spend data" for safe matching
                df.columns = [c.strip().lower() for c in df.columns]

                # --- STEP 2: DEFINE MAPPING (Lowercase Keys Only) ---
                clean_table_name = selected_table.lower()
                rename_map = {} 

                # 1. BLINKIT AD DATA MAPPING (Updated)
                if "blinkit" in clean_table_name and "ad" in clean_table_name:
                    st.info(f"🔄 Detected Blinkit Ad Table: `{selected_table}`")
                    rename_map = {
                        "date": "date", 
                        "campaign id": "campaign_id", 
                        "campaign name": "campaign_name",
                        "targeting type": "targeting_type", 
                        "targeting value": "targeting_value",
                        "match type": "match_type", 
                        "most viewed position": "most_viewed_position",
                        "pacing type": "pacing_type", 
                        "cpm": "cpm", 
                        "impressions": "impressions",
                        "clicks": "clicks",
                        
                        # --- NEWLY ADDED MAPPINGS ---
                        "ad spend data": "ad_spend_data",
                        "product name": "product_name",
                        "week": "week",
                        "month": "month",
                        # ----------------------------

                        "direct atc": "direct_atc", 
                        "indirect atc": "indirect_atc",
                        "direct quantities sold": "direct_quantities_sold",
                        "indirect quantities sold": "indirect_quantities_sold",
                        "estimated budget consumed": "estimated_budget_consumed",
                        "direct sales": "direct_sales", 
                        "indirect sales": "indirect_sales",
                        "direct roas": "direct_roas", 
                        "total roas": "total_roas"
                        
                        # "new users acquired" IS REMOVED
                    }

                # 2. BLINKIT SALES DATA MAPPING
                elif "blinkit" in clean_table_name and "sales" in clean_table_name:
                    st.info(f"🔄 Detected Blinkit Sales Table: `{selected_table}`")
                    rename_map = {
                        "order date": "order_date", "sku": "sku", "product name": "product",
                        "feeder warehouse": "feeder_wh", "net revenue": "net_revenue", "quantity": "quantity"
                    }

                # 3. SHOPIFY MAPPING
                elif "shopify" in clean_table_name:
                    st.info(f"🔄 Detected Shopify Table: `{selected_table}`")
                    rename_map = {
                        'day': 'day', 'sale id': 'sale_id', 'order name': 'order_name',
                        'product title at time of sale': 'product_title_at_time',
                        'gross sales': 'gross_sales', 'total sales': 'total_sales',
                        'net sales': 'net_sales', 'units sold': 'units_sold',
                        'revenue': 'revenue', 'product': 'product', 'order date': 'order_date'
                    }

                # 4. AMAZON MAPPING
                elif "amazon" in clean_table_name:
                    st.info(f"🔄 Detected Amazon Table: `{selected_table}`")
                    rename_map = {
                        '(parent) asin': 'parent_asin', 'title': 'title',
                        'ordered product sales': 'ordered_product_sales',
                        'ordered product sales - b2b': 'ordered_product_sales_b2b',
                        'units ordered': 'units_ordered', 'date': 'date'
                    }

                # --- STEP 3: APPLY MAPPING & FILTER ---
                if rename_map:
                    # Rename columns found in the map
                    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
                    
                    # STRICT FILTER: Keep ONLY columns that exist in the DB (the values in our map)
                    valid_db_columns = list(rename_map.values())
                    
                    # Create a final dataframe with only valid columns
                    final_df = df[[col for col in df.columns if col in valid_db_columns]].copy()
                else:
                    # Fallback if no specific map found
                    final_df = df.copy()
                
                # --- STEP 4: DATE FORMAT FIX ---
                date_cols = [col for col in final_df.columns if "date" in col.lower()]
                for col in date_cols:
                    try:
                        final_df[col] = pd.to_datetime(final_df[col], dayfirst=True, errors='coerce')
                    except Exception:
                        pass

                st.write("Ready for Upload (Cleaned):", final_df.head(3))

                # --- UPLOAD BUTTON ---
                if st.button("🚀 Confirm Upload"):
                    engine = get_engine()
                    if engine:
                        try:
                            final_df.to_sql(selected_table, engine, if_exists='append', index=False)
                            st.success(f"✅ Successfully uploaded {len(final_df)} rows to `{selected_table}`!")
                        except Exception as e:
                            st.error(f"Upload failed: {e}")

        # --- TAB 2: INSPECTOR ---
        with tab2:
            st.subheader("👀 Database Inspector")
            inspect_table = st.selectbox("Choose Table to View", all_tables, key="inspect")
            
            if st.button(f"Load Data for {inspect_table}"):
                engine = get_engine()
                with engine.connect() as conn:
                    query = text(f'SELECT * FROM "{inspect_table}" LIMIT 50;')
                    try:
                        df_view = pd.read_sql(query, conn)
                        st.dataframe(df_view)
                    except Exception as e:
                        st.error(f"Error reading table: {e}")