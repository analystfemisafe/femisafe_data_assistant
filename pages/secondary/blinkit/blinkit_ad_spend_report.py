import streamlit as st
import pandas as pd
import psycopg2

# ===================== DATABASE FUNCTIONS =====================

@st.cache_data(ttl=600)
def get_blinkit_addata():
    """Fetch Blinkit Ad Data from DB"""
    conn = psycopg2.connect(
        host="localhost",
        database="femisafe_test_db",
        user="ayish",
        password="ajtp@511Db"
    )
    query = "SELECT * FROM femisafe_blinkit_addata;"
    df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_blinkit_salesdata():
    """Fetch Blinkit Sales Data from DB"""
    conn = psycopg2.connect(
        host="localhost",
        database="femisafe_test_db",
        user="ayish",
        password="ajtp@511Db"
    )
    query = "SELECT * FROM femisafe_blinkit_salesdata;"
    df = pd.read_sql(query, conn)
    conn.close()
    return df



# ===================== MAIN PAGE =====================
def page():

    st.markdown("### 📊 Blinkit Ad Report")

    # Load Data
    df_ad = get_blinkit_addata()
    df_sales = get_blinkit_salesdata()

    df_ad['date'] = pd.to_datetime(df_ad['date'], errors='coerce')
    df_sales['order_date'] = pd.to_datetime(df_sales['order_date'], errors='coerce')

    # ===================== METRIC CARDS =====================

    card_style = """
        background-color: #3a3a3a;
        color: white;
        padding: 25px 10px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        width: 100%;
    """
    number_style = "font-size: 2rem; font-weight: bold; margin: 0;"
    label_style = "font-size: 0.9rem; margin-top: 4px; color: #e0e0e0;"
    units_style = "font-size: 0.9rem; margin-top: 2px; color: #cfcfcf;"

    latest_date = df_ad['date'].max()
    latest_month = df_ad['date'].dt.to_period('M').max()

    # Card Values
    month_spend = df_ad[df_ad['date'].dt.to_period('M') == latest_month]['estimated_budget_consumed'].sum()
    day_spend = df_ad[df_ad['date'] == latest_date]['estimated_budget_consumed'].sum()

    seven_days_ago = latest_date - pd.Timedelta(days=7)
    df_last7 = df_ad[(df_ad['date'] >= seven_days_ago) & (df_ad['date'] <= latest_date)]

    if df_last7['estimated_budget_consumed'].sum() > 0:
        last7_roas = df_last7['direct_sales'].sum() / df_last7['estimated_budget_consumed'].sum()
    else:
        last7_roas = None

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
            <div style="{card_style}">
                <p style="{number_style}">₹{month_spend:,.0f}</p>
                <p style="{units_style}">{latest_month.strftime('%B %Y')}</p>
                <p style="{label_style}">Latest Month Spend</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div style="{card_style}">
                <p style="{number_style}">₹{day_spend:,.0f}</p>
                <p style="{units_style}">{latest_date.strftime('%b %d, %Y')}</p>
                <p style="{label_style}">Latest Day Spend</p>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        roas_display = f"{last7_roas:.2f}×" if last7_roas else "–"
        st.markdown(f"""
            <div style="{card_style}">
                <p style="{number_style}">{roas_display}</p>
                <p style="{units_style}">Last 7 Days</p>
                <p style="{label_style}">Average ROAS</p>
            </div>
        """, unsafe_allow_html=True)



    # ===================== DATA FOR TABLE =====================

    latest_date = df_ad['date'].max()
    prev_date = latest_date - pd.Timedelta(days=1)

    df_ad_last2 = df_ad[df_ad['date'].isin([latest_date, prev_date])]
    df_sales_last2 = df_sales[df_sales['order_date'].isin([latest_date, prev_date])]

    # Aggregate
    ad_summary = df_ad_last2.groupby(['product_name', 'date']).agg({
        'estimated_budget_consumed': 'sum',
        'direct_sales': 'sum'
    }).reset_index()

    sales_summary = df_sales_last2.groupby(['product', 'order_date']).agg({
        'total_gross_bill_amount': 'sum'
    }).reset_index().rename(columns={'order_date': 'date', 'total_gross_bill_amount': 'gross_sales'})

    # Merge
    merged = pd.merge(ad_summary, sales_summary,
                      left_on=['product_name', 'date'],
                      right_on=['product', 'date'],
                      how='left')

    # ROAS Calculations
    merged['direct_roas'] = merged['direct_sales'] / merged['estimated_budget_consumed']
    merged['roas'] = merged['gross_sales'] / merged['estimated_budget_consumed']

    # Pivot
    pivot = merged.pivot(
        index='product_name',
        columns='date',
        values=['estimated_budget_consumed', 'direct_sales', 'gross_sales', 'direct_roas', 'roas']
    )

    pivot.columns = [f"{metric}_{date.strftime('%b %d')}" for metric, date in pivot.columns]
    pivot = pivot.reset_index()

    prev_label = prev_date.strftime("%b %d")
    latest_label = latest_date.strftime("%b %d")

    # Growth %
    pivot['Gross_Sales_Growth_%'] = (
        (pivot[f'gross_sales_{latest_label}'] - pivot[f'gross_sales_{prev_label}']) /
        pivot[f'gross_sales_{prev_label}'] * 100
        if pivot[f'gross_sales_{prev_label}'].sum() != 0 else 0
    )

    pivot['Ad_Spend_Growth_%'] = (
        (pivot[f'estimated_budget_consumed_{latest_label}'] - pivot[f'estimated_budget_consumed_{prev_label}']) /
        pivot[f'estimated_budget_consumed_{prev_label}'] * 100
        if pivot[f'estimated_budget_consumed_{prev_label}'].sum() != 0 else 0
    )

    # Sort
    pivot = pivot.sort_values(by=f'gross_sales_{latest_label}', ascending=False)

    # ===================== Total Row =====================
    total_row = pd.DataFrame([{
        'product_name': 'Total',
        f'estimated_budget_consumed_{prev_label}': pivot[f'estimated_budget_consumed_{prev_label}'].sum(),
        f'direct_sales_{prev_label}': pivot[f'direct_sales_{prev_label}'].sum(),
        f'gross_sales_{prev_label}': pivot[f'gross_sales_{prev_label}'].sum(),
        f'estimated_budget_consumed_{latest_label}': pivot[f'estimated_budget_consumed_{latest_label}'].sum(),
        f'direct_sales_{latest_label}': pivot[f'direct_sales_{latest_label}'].sum(),
        f'gross_sales_{latest_label}': pivot[f'gross_sales_{latest_label}'].sum(),
        'Gross_Sales_Growth_%': pivot['Gross_Sales_Growth_%'].mean(),
        'Ad_Spend_Growth_%': pivot['Ad_Spend_Growth_%'].mean()
    }])

    pivot = pd.concat([pivot, total_row], ignore_index=True)

    # ===================== Display Table =====================
    st.markdown("### 📄 Ad Performance Summary")
    st.dataframe(pivot, use_container_width=True)
