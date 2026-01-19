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
# 4. SMART ADMIN PANEL (Auto-Detects Tables)
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
            # Now the dropdown shows REAL tables
            selected_table = st.selectbox("Select Target Table", all_tables)
            
            uploaded_file = st.file_uploader(f"Upload CSV for `{selected_table}`", type=["csv"])
            
            if uploaded_file:
                df = pd.read_csv(uploaded_file)
                st.write("Preview:", df.head(3))
                
                # --- AUTO-MAPPING LOGIC ---
                # This tries to be smart about columns regardless of table name
                clean_table_name = selected_table.lower()
                
                if "shopify" in clean_table_name:
                    st.info(f"🔄 Detected Shopify Table: `{selected_table}`")
                    # Shopify Mapping
                    rename_map = {
                        'Day': 'day', 'Sale ID': 'sale_id', 'Order name': 'order_name',
                        'Product title at time of sale': 'product_title_at_time',
                        'Gross sales': 'gross_sales', 'Total sales': 'total_sales',
                        'Net sales': 'net_sales', 'Units Sold': 'units_sold',
                        'Revenue': 'revenue', 'Product': 'product', 'Order Date': 'order_date'
                    }
                    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

                elif "amazon" in clean_table_name:
                    st.info(f"🔄 Detected Amazon Table: `{selected_table}`")
                    # Amazon Mapping
                    rename_map = {
                        '(Parent) ASIN': 'parent_asin', 'Title': 'title',
                        'Ordered Product Sales': 'ordered_product_sales',
                        'Ordered Product Sales - B2B': 'ordered_product_sales_b2b',
                        'Units Ordered': 'units_ordered', 'Date': 'date'
                    }
                    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
                
                # --- UPLOAD BUTTON ---
                if st.button("🚀 Confirm Upload"):
                    engine = get_engine()
                    if engine:
                        try:
                            df.to_sql(selected_table, engine, if_exists='append', index=False)
                            st.success(f"✅ Uploaded to `{selected_table}`!")
                        except Exception as e:
                            st.error(f"Upload failed: {e}")

        # --- TAB 2: INSPECTOR ---
        with tab2:
            st.subheader("👀 Database Inspector")
            inspect_table = st.selectbox("Choose Table to View", all_tables, key="inspect")
            
            if st.button(f"Load Data for {inspect_table}"):
                engine = get_engine()
                with engine.connect() as conn:
                    # We use quotes just in case the name has capitals
                    query = text(f'SELECT * FROM "{inspect_table}" LIMIT 50;')
                    try:
                        df_view = pd.read_sql(query, conn)
                        st.dataframe(df_view)
                    except Exception as e:
                        st.error(f"Error reading table: {e}")