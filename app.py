import streamlit as st
import pandas as pd
import psycopg2


st.set_page_config(page_title="FemiSafe Analytics", layout="wide")

# ------------------------------------------------------
# STYLING
# ------------------------------------------------------
st.sidebar.markdown("""
<style>
.selector-buttons {
    display: flex;
    gap: 10px;
}
.selector-buttons button {
    flex: 1;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------
# TOP BUTTONS (PRIMARY vs SECONDARY)
# ------------------------------------------------------
st.sidebar.markdown("### Navigation Mode")

col1, col2 = st.sidebar.columns(2)

# Session state to store which mode is active
if "nav_mode" not in st.session_state:
    st.session_state.nav_mode = "Primary"

with col1:
    if st.button("Primary"):
        st.session_state.nav_mode = "Primary"

with col2:
    if st.button("Secondary"):
        st.session_state.nav_mode = "Secondary"


# ------------------------------------------------------
# LONG BUTTON: DATA ASSISTANT
# ------------------------------------------------------

if st.sidebar.button("📊 Data Assistant", use_container_width=True):
    st.session_state.nav_mode = "Data Assistant"


# Current mode
mode = st.session_state.nav_mode


# ------------------------------------------------------
# PRIMARY SECTION
# ------------------------------------------------------
if mode == "Primary":

    st.sidebar.subheader("Primary Dashboards")

    primary_choice = st.sidebar.selectbox(
        "Choose Report",
        [
            "Overall Sales Overview",
            "Statewise Trends",
            "Product Performance",
            "Special Primary Charts"
        ]
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


# ------------------------------------------------------
# SECONDARY SECTION
# ------------------------------------------------------
elif mode == "Secondary":

    st.sidebar.subheader("Select Channel")

    channel_choice = st.sidebar.radio(
        "Channel",
        ["Amazon", "Blinkit", "Shopify", "Flipkart", "Swiggy"]
    )

    # ---------------- Dynamic Report Options ----------------
    if channel_choice == "Blinkit":
        report_options = [
            "Sales Dashboard",
            "Productwise Performance",
            "Citywise Performance",
            "Ad Spend Report",
            "Organic Share",
            "Aging Report"
        ]
    else:
        report_options = [
            "Sales Dashboard",
            "Ad Report"
        ]

    report_choice = st.sidebar.selectbox("Select Report", report_options)

    # ---------------- AMAZON ----------------
    if channel_choice == "Amazon":
        if report_choice == "Sales Dashboard":
            from pages.secondary.amazon.sales_dashboard import page as pg
        else:
            from pages.secondary.amazon.ad_report import page as pg
        pg()

    # ---------------- BLINKIT ----------------
    elif channel_choice == "Blinkit":

        if report_choice == "Sales Dashboard":
            from pages.secondary.blinkit.blinkit_sales_dashboard import page as pg

        elif report_choice == "Productwise Performance":
            from pages.secondary.blinkit.blinkit_productwise_performance import page as pg

        elif report_choice == "Citywise Performance":
            from pages.secondary.blinkit.blinkit_citywise_performance import page as pg

        elif report_choice == "Ad Spend Report":
            from pages.secondary.blinkit.blinkit_ad_spend_report import page as pg

        elif report_choice == "Organic Share":
            from pages.secondary.blinkit.blinkit_organic_share import page as pg

        elif report_choice == "Aging Report":
            from pages.secondary.blinkit.blinkit_aging_report import page as pg

        pg()

    # ---------------- SHOPIFY ----------------
    elif channel_choice == "Shopify":
        if report_choice == "Sales Dashboard":
            from pages.secondary.shopify.sales_dashboard import page as pg
        else:
            from pages.secondary.shopify.ad_report import page as pg
        pg()

    # ---------------- FLIPKART ----------------
    elif channel_choice == "Flipkart":
        if report_choice == "Sales Dashboard":
            from pages.secondary.flipkart.sales_dashboard import page as pg
        else:
            from pages.secondary.flipkart.ad_report import page as pg
        pg()

    # ---------------- SWIGGY ----------------
    elif channel_choice == "Swiggy":
        if report_choice == "Sales Dashboard":
            from pages.secondary.swiggy.sales_dashboard import page as pg
        else:
            from pages.secondary.swiggy.ad_report import page as pg
        pg()

elif mode == "Data Assistant":
    from pages.data_assistant.data_assistant import page as data_page
    data_page()
