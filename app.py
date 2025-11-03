import streamlit as st
import pandas as pd
import psycopg2
import numpy as np

# LangChain imports
from langchain_community.utilities import SQLDatabase
from langchain_community.llms import Ollama
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser




# ======================================
# App Title
# ======================================
st.set_page_config(page_title="FemiSafe Analytics", layout="wide")
st.markdown("""
<style>
.sidebar-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: #white;
    margin-bottom: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# ======================================
# Sidebar Navigation
# ======================================
# Move Title to Sidebar
st.sidebar.markdown("<div class='sidebar-title'>📊 FemiSafe Analytical Portal</div>", unsafe_allow_html=True)
st.sidebar.title("Navigation Menu")

main_sections = [
    "Overall Dashboards",
    "Amazon",
    "Blinkit",
    "Swiggy",
    "Data Query"
]

main_choice = st.sidebar.radio("Main Section", main_sections)

# ======================================
# Subsections per main section
# ======================================
sub_choice = None

if main_choice == "Overall Dashboards":
    st.sidebar.subheader("Sections")
    sub_choice = st.sidebar.selectbox("Select Dashboard", ["Overall Sales Overview", "Performance Trends", "Category Split"])

elif main_choice == "Amazon":
    st.sidebar.subheader("Reports")
    sub_choice = st.sidebar.selectbox("Select Report", ["Sales Report", "Ad Report", "MTD Report"])

elif main_choice == "Blinkit":
    st.sidebar.subheader("Reports")
    sub_choice = st.sidebar.selectbox("Select Report", ["Sales Dashboard", "SKU Sales Report", "City Sales Report", "Ad Report", "MTD Report"])

elif main_choice == "Swiggy":
    st.sidebar.subheader("Reports")
    sub_choice = st.sidebar.selectbox("Select Report", ["Sales Report", "Ad Report", "Stock Report", "MTD Report"])

elif main_choice == "V. Data Query":
    sub_choice = None  # Direct section, no dropdown

# ======================================
# Database Connection
# ======================================
@st.cache_data
def get_data():
    conn = psycopg2.connect(
        dbname="femisafe_test_db",
        user="ayish",                      
        password="YourStrongPassword123",  
        host="localhost",
        port="5432"
    )
    query = """
        SELECT 
            month,
            SUM(revenue) AS revenue,
            SUM(sku_units) AS units
        FROM femisafe_sales                
        GROUP BY month
        ORDER BY month;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# ======================================
# Page Display
# ======================================
# ================OVERALL DASHBOARD======================
if main_choice == "Overall Dashboards" and sub_choice == "Overall Sales Overview":
    df = get_data()
    
    # Sort and handle logic
    df = df.sort_values('month')
    if len(df) < 1:
        st.warning("No data available.")
    else:
        total_revenue = df['revenue'].sum()
        total_units = df['units'].sum()

        # Filter September data
        sept_data = df[df['month'].str.lower() == 'september']
        september_revenue = sept_data['revenue'].sum()
        september_units = sept_data['units'].sum()

        month_name = "September"
        
        # Card styling
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
        label_style = "font-size: 0.9rem; margin-top: 4px; color: #e0e0e0; font-weight: 500;"
        units_style = "font-size: 0.9rem; margin-top: 2px; color: #cfcfcf;"

        st.markdown("<div class='sidebar-title'>FemiSafe Sales Overview", unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"""
            <div style="{card_style}">
                <p style="{number_style}">₹{september_revenue:,.0f}</p>
                <p style="{units_style}">{int(september_units):,} units</p>
                <p style="{label_style}">{month_name} Revenue</p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="{card_style}">
                <p style="{number_style}">₹{total_revenue:,.0f}</p>
                <p style="{units_style}">{int(total_units):,} units</p>
                <p style="{label_style}">Total Revenue (All Months)</p>
            </div>
            """, unsafe_allow_html=True)
# =================//OVERALL DASHBOARD=====================

elif main_choice == "Blinkit":
    st.markdown("<div class='sidebar-title'>Blinkit Sales Overview", unsafe_allow_html=True)
    
    # ===================== Get Blinkit Data =====================
    @st.cache_data
    def get_blinkit_data():
        conn = psycopg2.connect(
            dbname="femisafe_test_db",
            user="ayish",
            password="ajtp@511Db",
            host="localhost",
            port="5432"
        )
        query = """
            SELECT 
                order_date,
                sku,
                feeder_wh,
                net_revenue,
                quantity
            FROM femisafe_blinkit_salesdata;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    if sub_choice == "Sales Dashboard":

        df_blinkit = get_blinkit_data()
        df_blinkit['order_date'] = pd.to_datetime(df_blinkit['order_date'], errors='coerce')
        df_blinkit['month'] = df_blinkit['order_date'].dt.strftime('%B')

        total_revenue = df_blinkit['net_revenue'].sum()
        total_units = df_blinkit['quantity'].sum()

        latest_month = df_blinkit['order_date'].max().strftime('%B')
        latest_data = df_blinkit[df_blinkit['month'] == latest_month]

        latest_revenue = latest_data['net_revenue'].sum()
        latest_units = latest_data['quantity'].sum()

        # ===================== Card Styling =====================
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
        label_style = "font-size: 0.9rem; margin-top: 4px; color: #e0e0e0; font-weight: 500;"
        units_style = "font-size: 0.9rem; margin-top: 2px; color: #cfcfcf;"

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div style="{card_style}">
                <p style="{number_style}">₹{latest_revenue:,.0f}</p>
                <p style="{units_style}">{int(latest_units):,} units</p>
                <p style="{label_style}">{latest_month} Revenue</p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="{card_style}">
                <p style="{number_style}">₹{total_revenue:,.0f}</p>
                <p style="{units_style}">{int(total_units):,} units</p>
                <p style="{label_style}">Total Revenue (All Months)</p>
            </div>
            """, unsafe_allow_html=True)

        # ===================== Chart Section =====================
        import plotly.graph_objects as go

        # Filter last 30 days
        df_blinkit_30 = df_blinkit[df_blinkit['order_date'] >= (df_blinkit['order_date'].max() - pd.Timedelta(days=30))]

        # Group by date
        df_daily = df_blinkit_30.groupby('order_date', as_index=False).agg({
            'net_revenue': 'sum',
            'quantity': 'sum'
        })

        # Plotly chart
        fig = go.Figure()

        # Revenue line (left axis) — smooth curve
        fig.add_trace(go.Scatter(
            x=df_daily['order_date'],
            y=df_daily['net_revenue'],
            mode='lines',
            name='Net Sales (in INR)',
            line=dict(color='purple', width=3, shape='spline'),  # 🔹 Smooth curve
            hovertemplate='%{x|%d %b}<br>Sales (₹): %{y:,.0f}<extra></extra>'
        ))

        # Units line (right axis) — smooth curve
        fig.add_trace(go.Scatter(
            x=df_daily['order_date'],
            y=df_daily['quantity'],
            mode='lines',
            name='Net Sales (in Units)',
            line=dict(color='green', width=3, shape='spline'),  # 🔹 Smooth curve
            yaxis='y2',
            hovertemplate='%{x|%d %b}<br>Units Sold: %{y:,}<extra></extra>'
        ))

        fig.update_layout(
        title=dict(
            text="📈 Blinkit Sales (Last 30 Days)",
            font=dict(color="black", size=18)   # ✅ Chart title black
        ),
        xaxis=dict(
            tickfont=dict(color="black"),
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",  # light gridlines
            gridwidth=0.5
        ),
        yaxis=dict(
            title=dict(text="Net Sales (INR)", font=dict(color="purple")),
            tickfont=dict(color="purple"),
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 3.0)",
            gridwidth=0.5
        ),

        yaxis2=dict(
            title=dict(text="No. of Units Sold", font=dict(color="green")),
            tickfont=dict(color="green"), 
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.3)",  # light gridlines 
            overlaying="y",
            side="right"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(color="black")       # ✅ Legend text black
        ),
        font=dict(color="black"),          # ✅ All remaining text black (title, axes)
        template="plotly_white",
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        plot_bgcolor="white",              # ✅ Chart area background white
        paper_bgcolor="white"              # ✅ Outer background white
        )

        st.plotly_chart(fig, use_container_width=True)
    ###########################SKUWISE SALES REPORT#####################################
    elif sub_choice == "SKU Sales Report":
        st.markdown("### 📦 SKU-wise Sales Report (Last 7 Days Comparison)")

        # ===================== Get Blinkit Data =====================
        df = get_blinkit_data()
        df['order_date'] = pd.to_datetime(df['order_date'])
        df['date'] = df['order_date'].dt.date

        # Get latest, D-1, and D-7
        latest_date = df['date'].max()
        d1_date = latest_date - pd.Timedelta(days=1)
        d7_date = latest_date - pd.Timedelta(days=7)

        # Filter only relevant dates
        df_filtered = df[df['date'].isin([d7_date, d1_date, latest_date])]

        # Aggregate
        grouped = df_filtered.groupby(['sku', 'feeder_wh', 'date']).agg({
            'net_revenue': 'sum',
            'quantity': 'sum'
        }).reset_index()

        # Pivot wider
        pivot = grouped.pivot_table(
            index=['sku', 'feeder_wh'],
            columns='date',
            values=['net_revenue', 'quantity'],
            fill_value=0
        ).reset_index()

        # Flatten columns
        pivot.columns = [f"{i}_{j.strftime('%b%d')}" if j != '' else i for i, j in pivot.columns]
        pivot = pivot.rename(columns={
            'net_revenue_': 'net_revenue',
            'quantity_': 'quantity'
        })

        # Reorder columns
        pivot = pivot[['sku', 'feeder_wh',
                    f'quantity_{d7_date.strftime("%b%d")}', f'net_revenue_{d7_date.strftime("%b%d")}',
                    f'quantity_{d1_date.strftime("%b%d")}', f'net_revenue_{d1_date.strftime("%b%d")}',
                    f'quantity_{latest_date.strftime("%b%d")}', f'net_revenue_{latest_date.strftime("%b%d")}']]

        # Delta columns
        pivot['Units Delta'] = pivot[f'quantity_{latest_date.strftime("%b%d")}'] - pivot[f'quantity_{d7_date.strftime("%b%d")}']
        pivot['Revenue Delta'] = pivot[f'net_revenue_{latest_date.strftime("%b%d")}'] - pivot[f'net_revenue_{d7_date.strftime("%b%d")}']

        # Subtotals per SKU
        subtotal_rows = []
        for sku, group in pivot.groupby('sku', group_keys=False):
            subtotal = pd.DataFrame({
                'sku': [sku],
                'feeder_wh': [f"{sku} Total"],
                f'quantity_{d7_date.strftime("%b%d")}': [group[f'quantity_{d7_date.strftime("%b%d")}'].sum()],
                f'net_revenue_{d7_date.strftime("%b%d")}': [group[f'net_revenue_{d7_date.strftime("%b%d")}'].sum()],
                f'quantity_{d1_date.strftime("%b%d")}': [group[f'quantity_{d1_date.strftime("%b%d")}'].sum()],
                f'net_revenue_{d1_date.strftime("%b%d")}': [group[f'net_revenue_{d1_date.strftime("%b%d")}'].sum()],
                f'quantity_{latest_date.strftime("%b%d")}': [group[f'quantity_{latest_date.strftime("%b%d")}'].sum()],
                f'net_revenue_{latest_date.strftime("%b%d")}': [group[f'net_revenue_{latest_date.strftime("%b%d")}'].sum()],
            })

            subtotal['Units Delta'] = subtotal[f'quantity_{latest_date.strftime("%b%d")}'] - subtotal[f'quantity_{d7_date.strftime("%b%d")}']
            subtotal['Revenue Delta'] = subtotal[f'net_revenue_{latest_date.strftime("%b%d")}'] - subtotal[f'net_revenue_{d7_date.strftime("%b%d")}']

            prev = subtotal[f'net_revenue_{d7_date.strftime("%b%d")}'].iloc[0]
            curr = subtotal[f'net_revenue_{latest_date.strftime("%b%d")}'].iloc[0]
            subtotal['Growth %'] = 0 if prev == 0 else round(((curr - prev) / prev) * 100, 2)

            group['Growth %'] = ""  # Blank for non-subtotal rows
            subtotal_rows.append(pd.concat([group, subtotal], ignore_index=True))

        final_df = pd.concat(subtotal_rows, ignore_index=True)

        # Convert quantities to whole numbers
        for col in final_df.columns:
            if "quantity" in col:
                final_df[col] = final_df[col].astype(int)

        # =============== SORTING SECTION ===============
        final_df['sku_total_units'] = final_df.groupby('sku')[f'quantity_{latest_date.strftime("%b%d")}'].transform('sum')
        final_df['feeder_total_units'] = final_df.groupby(['sku', 'feeder_wh'])[f'quantity_{latest_date.strftime("%b%d")}'].transform('sum')

        final_df = final_df.sort_values(
            by=['sku_total_units', 'feeder_total_units'],
            ascending=[False, False]
        )

        final_df = final_df.drop(columns=['sku_total_units', 'feeder_total_units'], errors='ignore')

        # =============== GRAND TOTAL (Exclude Subtotal Rows) ===============
        grand_source = final_df[~final_df['feeder_wh'].str.contains('Total', na=False)]

        grand_total = pd.DataFrame({
            'sku': ['Grand Total'],
            'feeder_wh': [''],
            f'quantity_{d7_date.strftime("%b%d")}': [grand_source[f'quantity_{d7_date.strftime("%b%d")}'].sum()],
            f'net_revenue_{d7_date.strftime("%b%d")}': [grand_source[f'net_revenue_{d7_date.strftime("%b%d")}'].sum()],
            f'quantity_{d1_date.strftime("%b%d")}': [grand_source[f'quantity_{d1_date.strftime("%b%d")}'].sum()],
            f'net_revenue_{d1_date.strftime("%b%d")}': [grand_source[f'net_revenue_{d1_date.strftime("%b%d")}'].sum()],
            f'quantity_{latest_date.strftime("%b%d")}': [grand_source[f'quantity_{latest_date.strftime("%b%d")}'].sum()],
            f'net_revenue_{latest_date.strftime("%b%d")}': [grand_source[f'net_revenue_{latest_date.strftime("%b%d")}'].sum()],
            'Units Delta': [grand_source['Units Delta'].sum()],
            'Revenue Delta': [grand_source['Revenue Delta'].sum()],
            'Growth %': [round(
                ((grand_source[f'net_revenue_{latest_date.strftime("%b%d")}'].sum() - 
                grand_source[f'net_revenue_{d7_date.strftime("%b%d")}'].sum()) /
                grand_source[f'net_revenue_{d7_date.strftime("%b%d")}'].sum()) * 100, 2)]
        })
        final_df = pd.concat([final_df, grand_total], ignore_index=True)

        # =============== FORMATTING ===============
        for c in final_df.columns:
            if 'net_revenue' in c:
                final_df[c] = final_df[c].apply(lambda x: f"₹{x:,.0f}")
            elif c in ['Growth %']:
                final_df[c] = final_df[c].apply(lambda x: f"{x:+.2f}%" if x != "" else "")
            elif c in ['Units Delta', 'Revenue Delta']:
                final_df[c] = final_df[c].apply(lambda x: f"{int(x):,}")

        # =============== HIGHLIGHTING ===============
        def highlight_rows(row):
            feeder_wh_col = ('Feeder WH', '')
            sku_col = ('SKU', '')

            row_style = [''] * len(row)

            # Row-level background first
            if 'Total' in str(row.get(feeder_wh_col, '')):
                row_style = ['background-color: #2e2e2e; color: white; font-weight: bold'] * len(row)
            elif 'Grand Total' in str(row.get(sku_col, '')):
                row_style = ['background-color: #444; color: white; font-weight: bold'] * len(row)

            return row_style


        def highlight_growth(val):
            """Cell-level formatter for Growth % only"""
            try:
                v = float(str(val).replace('%', '').replace('+', '').strip())
                if v < 0:
                    return 'background-color: #ffcccc; color: black; font-weight: bold;'  # light red
                else:
                    return 'background-color: #ccffcc; color: black; font-weight: bold;'  # light green
            except Exception:
                return ''

        # =============== BUILD MULTI-LEVEL HEADERS ===============
        from datetime import datetime

        date_labels = {
            d7_date.strftime("%b%d"): d7_date.strftime("%B %d"),
            d1_date.strftime("%b%d"): d1_date.strftime("%B %d"),
            latest_date.strftime("%b%d"): latest_date.strftime("%B %d"),
        }

        multi_columns = pd.MultiIndex.from_tuples([
            ('SKU', ''), 
            ('Feeder WH', ''),
            (date_labels[d7_date.strftime("%b%d")], 'Units'),
            (date_labels[d7_date.strftime("%b%d")], 'Net Rev'),
            (date_labels[d1_date.strftime("%b%d")], 'Units'),
            (date_labels[d1_date.strftime("%b%d")], 'Net Rev'),
            (date_labels[latest_date.strftime("%b%d")], 'Units'),
            (date_labels[latest_date.strftime("%b%d")], 'Net Rev'),
            ('Delta', 'Units Delta'),
            ('Delta', 'Revenue Delta'),
            ('Delta', 'Growth %')
        ])

        final_df.columns = multi_columns
        st.dataframe(
            final_df.style
                .apply(highlight_rows, axis=1)
                .applymap(highlight_growth, subset=[('Delta', 'Growth %')]),
            use_container_width=True
        )
#######################///SKUWISE SALES REPORT###################
######################CITYWISE SALES REPORT##############################
    elif sub_choice == "City Sales Report":
        st.markdown("### 🏙️ City-wise Sales Report (Last 7 Days Comparison)")

        # ===================== Get Blinkit Data =====================
        df = get_blinkit_data()
        df['order_date'] = pd.to_datetime(df['order_date'])
        df['date'] = df['order_date'].dt.date

        # Get latest, D-1, and D-7
        latest_date = df['date'].max()
        d1_date = latest_date - pd.Timedelta(days=1)
        d7_date = latest_date - pd.Timedelta(days=7)

        # Filter only relevant dates
        df_filtered = df[df['date'].isin([d7_date, d1_date, latest_date])]

        # Aggregate
        grouped = df_filtered.groupby(['feeder_wh', 'sku', 'date']).agg({
            'net_revenue': 'sum',
            'quantity': 'sum'
        }).reset_index()

        # Pivot wider
        pivot = grouped.pivot_table(
            index=['feeder_wh', 'sku'],
            columns='date',
            values=['net_revenue', 'quantity'],
            fill_value=0
        ).reset_index()

        # Flatten columns
        pivot.columns = [f"{i}_{j.strftime('%b%d')}" if j != '' else i for i, j in pivot.columns]
        pivot = pivot.rename(columns={
            'net_revenue_': 'net_revenue',
            'quantity_': 'quantity'
        })

        # Reorder columns
        pivot = pivot[['feeder_wh', 'sku',
                    f'quantity_{d7_date.strftime("%b%d")}', f'net_revenue_{d7_date.strftime("%b%d")}',
                    f'quantity_{d1_date.strftime("%b%d")}', f'net_revenue_{d1_date.strftime("%b%d")}',
                    f'quantity_{latest_date.strftime("%b%d")}', f'net_revenue_{latest_date.strftime("%b%d")}']]

        # Delta columns
        pivot['Units Delta'] = pivot[f'quantity_{latest_date.strftime("%b%d")}'] - pivot[f'quantity_{d7_date.strftime("%b%d")}']
        pivot['Revenue Delta'] = pivot[f'net_revenue_{latest_date.strftime("%b%d")}'] - pivot[f'net_revenue_{d7_date.strftime("%b%d")}']

        # Subtotals per Feeder WH
        subtotal_rows = []
        for feeder, group in pivot.groupby('feeder_wh', group_keys=False):
            subtotal = pd.DataFrame({
                'feeder_wh': [feeder],
                'sku': [f"{feeder} Total"],
                f'quantity_{d7_date.strftime("%b%d")}': [group[f'quantity_{d7_date.strftime("%b%d")}'].sum()],
                f'net_revenue_{d7_date.strftime("%b%d")}': [group[f'net_revenue_{d7_date.strftime("%b%d")}'].sum()],
                f'quantity_{d1_date.strftime("%b%d")}': [group[f'quantity_{d1_date.strftime("%b%d")}'].sum()],
                f'net_revenue_{d1_date.strftime("%b%d")}': [group[f'net_revenue_{d1_date.strftime("%b%d")}'].sum()],
                f'quantity_{latest_date.strftime("%b%d")}': [group[f'quantity_{latest_date.strftime("%b%d")}'].sum()],
                f'net_revenue_{latest_date.strftime("%b%d")}': [group[f'net_revenue_{latest_date.strftime("%b%d")}'].sum()],
            })

            subtotal['Units Delta'] = subtotal[f'quantity_{latest_date.strftime("%b%d")}'] - subtotal[f'quantity_{d7_date.strftime("%b%d")}']
            subtotal['Revenue Delta'] = subtotal[f'net_revenue_{latest_date.strftime("%b%d")}'] - subtotal[f'net_revenue_{d7_date.strftime("%b%d")}']

            prev = subtotal[f'net_revenue_{d7_date.strftime("%b%d")}'].iloc[0]
            curr = subtotal[f'net_revenue_{latest_date.strftime("%b%d")}'].iloc[0]
            subtotal['Growth %'] = 0 if prev == 0 else round(((curr - prev) / prev) * 100, 2)

            group['Growth %'] = ""  # Blank for non-subtotal rows
            subtotal_rows.append(pd.concat([group, subtotal], ignore_index=True))

        final_df = pd.concat(subtotal_rows, ignore_index=True)

        # Convert quantities to whole numbers
        for col in final_df.columns:
            if "quantity" in col:
                final_df[col] = final_df[col].astype(int)

        # =============== SORTING: feeder by subtotal desc, sku by units desc ===============
        # name of latest quantity column (same used elsewhere)
        latest_q_col = f'quantity_{latest_date.strftime("%b%d")}'  # e.g. 'quantity_Oct29'

        # Ensure latest quantity column is numeric (in case it's been formatted earlier)
        final_df[latest_q_col] = pd.to_numeric(final_df[latest_q_col], errors='coerce').fillna(0).astype(int)

        # identify subtotal rows we created earlier (we used sku == "<feeder> Total")
        is_subtotal = final_df['sku'].astype(str).str.contains('Total', na=False)

        # source_rows = only feeder->sku rows (exclude subtotal rows) — used to compute real totals
        source_rows = final_df[~is_subtotal].copy()

        # 1) feeder totals (sum of latest units) and order feeders descending by that
        feeder_totals = source_rows.groupby('feeder_wh', dropna=False)[latest_q_col].sum().reset_index()
        feeder_totals = feeder_totals.sort_values(by=latest_q_col, ascending=False)

        # 2) sku totals inside feeders (sum of latest units) — used to sort SKUs inside each feeder
        sku_totals = source_rows.groupby(['feeder_wh', 'sku'], dropna=False)[latest_q_col].sum().reset_index()
        sku_totals = sku_totals.rename(columns={latest_q_col: f'{latest_q_col}_sku_total'})

        # 3) build ordered list: for each feeder (by feeder_totals order) append sorted skus then subtotal
        ordered_parts = []
        for feeder in feeder_totals['feeder_wh'].tolist():
            # rows for this feeder excluding subtotal rows
            feeder_rows = source_rows[source_rows['feeder_wh'] == feeder].copy()

            # attach sku_total to allow robust sorting (merge on sku)
            feeder_rows = feeder_rows.merge(
                sku_totals[sku_totals['feeder_wh'] == feeder][['sku', f'{latest_q_col}_sku_total']],
                on='sku',
                how='left'
            )

            # sort SKUs inside feeder by sku_total descending (if missing sku_total, treat as 0)
            feeder_rows[f'{latest_q_col}_sku_total'] = feeder_rows[f'{latest_q_col}_sku_total'].fillna(0).astype(int)
            feeder_rows = feeder_rows.sort_values(by=f'{latest_q_col}_sku_total', ascending=False)

            # drop helper sku_total column
            feeder_rows = feeder_rows.drop(columns=[f'{latest_q_col}_sku_total'], errors='ignore')

            ordered_parts.append(feeder_rows)

            # find the subtotal row we created earlier for this feeder (sku contains "Total")
            subtotal_mask = (final_df['feeder_wh'] == feeder) & final_df['sku'].astype(str).str.contains('Total', na=False)
            feeder_subtotal = final_df[subtotal_mask].copy()

            # if a subtotal row exists, append it; otherwise build a subtotal row from feeder_rows sums
            if not feeder_subtotal.empty:
                ordered_parts.append(feeder_subtotal)
            else:
                # fallback: construct subtotal
                built = pd.DataFrame({
                    'feeder_wh': [feeder],
                    'sku': [f"{feeder} Total"],
                    latest_q_col: [feeder_rows[latest_q_col].sum()],
                    # copy other date cols if present (safely)
                })
                # try to fill other expected numeric cols from feeder_rows sums if they exist in final_df
                numeric_cols = [c for c in final_df.columns if isinstance(c, str) and ('quantity_' in c or 'net_revenue_' in c or c in ['Units Delta', 'Revenue Delta'])]
                for nc in numeric_cols:
                    built[nc] = [feeder_rows[nc].sum() if nc in feeder_rows.columns else 0]
                # Growth % for fallback
                d7_col = f'net_revenue_{d7_date.strftime("%b%d")}'
                dcur_col = f'net_revenue_{latest_date.strftime("%b%d")}'
                prev = built.get(d7_col, pd.Series([0])).iloc[0]
                curr = built.get(dcur_col, pd.Series([0])).iloc[0]
                built['Growth %'] = 0 if prev == 0 else round(((curr - prev) / prev) * 100, 2)

                ordered_parts.append(built)

        # 4) concat ordered parts into new final_df (preserves desired order)
        ordered_df = pd.concat(ordered_parts, ignore_index=True)

        # 5) append grand total at the end (compute from source_rows to avoid double-counting subtotal rows)
        grand_source = source_rows  # excludes subtotal rows
        grand_total = pd.DataFrame({
            'feeder_wh': ['Grand Total'],
            'sku': [''],
            f'quantity_{d7_date.strftime("%b%d")}': [grand_source[f'quantity_{d7_date.strftime("%b%d")}'].sum()],
            f'net_revenue_{d7_date.strftime("%b%d")}': [grand_source[f'net_revenue_{d7_date.strftime("%b%d")}'].sum()],
            f'quantity_{d1_date.strftime("%b%d")}': [grand_source[f'quantity_{d1_date.strftime("%b%d")}'].sum()],
            f'net_revenue_{d1_date.strftime("%b%d")}': [grand_source[f'net_revenue_{d1_date.strftime("%bb%d")}' if False else f'net_revenue_{d1_date.strftime("%b%d")}'].sum()],
            f'quantity_{latest_date.strftime("%b%d")}': [grand_source[f'quantity_{latest_date.strftime("%b%d")}'].sum()],
            f'net_revenue_{latest_date.strftime("%b%d")}': [grand_source[f'net_revenue_{latest_date.strftime("%b%d")}'].sum()],
            'Units Delta': [grand_source['Units Delta'].sum() if 'Units Delta' in grand_source.columns else 0],
            'Revenue Delta': [grand_source['Revenue Delta'].sum() if 'Revenue Delta' in grand_source.columns else 0],
            'Growth %': [round(
                ((grand_source[f'net_revenue_{latest_date.strftime("%b%d")}'].sum() -
                grand_source[f'net_revenue_{d7_date.strftime("%b%d")}'].sum()) /
                (grand_source[f'net_revenue_{d7_date.strftime("%b%d")}'].sum() if grand_source[f'net_revenue_{d7_date.strftime("%b%d")}'].sum() != 0 else 1)
                ) * 100, 2)]
        })

        # ensure ordered_df has same columns as final_df (add missing cols with blanks)
        for col in final_df.columns:
            if col not in ordered_df.columns:
                ordered_df[col] = ""  # fill missing with blanks

        ordered_df = ordered_df[final_df.columns]  # preserve original column order
        final_df = pd.concat([ordered_df, grand_total], ignore_index=True)

        # =============== FORMATTING ===============
        for c in final_df.columns:
            if 'net_revenue' in c:
                final_df[c] = final_df[c].apply(lambda x: f"₹{x:,.0f}")
            elif c in ['Growth %']:
                final_df[c] = final_df[c].apply(lambda x: f"{x:+.2f}%" if x != "" else "")
            elif c in ['Units Delta', 'Revenue Delta']:
                final_df[c] = final_df[c].apply(lambda x: f"{int(x):,}")

        # =============== HIGHLIGHTING ===============
        def highlight_rows(row):
            feeder_wh_col = ('Feeder WH', '')
            sku_col = ('SKU', '')

            row_style = [''] * len(row)

            if 'Total' in str(row.get(sku_col, '')):
                row_style = ['background-color: #2e2e2e; color: white; font-weight: bold'] * len(row)
            elif 'Grand Total' in str(row.get(feeder_wh_col, '')):
                row_style = ['background-color: #444; color: white; font-weight: bold'] * len(row)

            return row_style

        def highlight_growth(val):
            try:
                v = float(str(val).replace('%', '').replace('+', '').strip())
                if v < 0:
                    return 'background-color: #ffcccc; color: black; font-weight: bold;'
                else:
                    return 'background-color: #ccffcc; color: black; font-weight: bold;'
            except Exception:
                return ''

        # =============== MULTI-LEVEL HEADERS ===============
        date_labels = {
            d7_date.strftime("%b%d"): d7_date.strftime("%B %d"),
            d1_date.strftime("%b%d"): d1_date.strftime("%B %d"),
            latest_date.strftime("%b%d"): latest_date.strftime("%B %d"),
        }

        multi_columns = pd.MultiIndex.from_tuples([
            ('Feeder WH', ''), 
            ('SKU', ''),
            (date_labels[d7_date.strftime("%b%d")], 'Units'),
            (date_labels[d7_date.strftime("%b%d")], 'Net Rev'),
            (date_labels[d1_date.strftime("%b%d")], 'Units'),
            (date_labels[d1_date.strftime("%b%d")], 'Net Rev'),
            (date_labels[latest_date.strftime("%b%d")], 'Units'),
            (date_labels[latest_date.strftime("%b%d")], 'Net Rev'),
            ('Delta', 'Units Delta'),
            ('Delta', 'Revenue Delta'),
            ('Delta', 'Growth %')
        ])

        final_df.columns = multi_columns
        st.dataframe(
            final_df.style
                .apply(highlight_rows, axis=1)
                .applymap(highlight_growth, subset=[('Delta', 'Growth %')]),
            use_container_width=True
        )
#########################//CITYWISE SALES REPORT###############



elif main_choice == "Data Query":

    st.title("🔍 Data Query Assistant")

    # Step 1: Connect to PostgreSQL
    db = SQLDatabase.from_uri("postgresql://ayish:ajtp%40511Db@localhost:5432/femisafe_test_db")

    # Step 2: Load Ollama (local Llama3)
    llm = Ollama(model="llama3")

    # Step 3: Define a strict SQL-only prompt
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema.output_parser import StrOutputParser

    prompt = ChatPromptTemplate.from_template("""
    You are an expert SQL assistant.
    Convert the user's natural language question into a valid SQL query for PostgreSQL.

    RULES:
    - Output ONLY the executable SQL (no explanation, markdown, or comments).
    - The table name is femisafe_sales.
    - Columns include: revenue, month, channels, order_date, sku_units, etc.
    - When filtering by month, use the 'month' column directly. Example:
      WHERE month = 'September'
    - Be careful with string values — always wrap them in single quotes.
    - When aggregating (like total revenue, total units, etc.), always use GROUP BY for non-aggregated columns (e.g., channels, SKUs).


    Question: {question}
    SQLQuery:
    """)

    chain = prompt | llm | StrOutputParser()

    # Step 4: Natural language input
    user_query = st.text_input("Ask your question (e.g. 'Show me September sterilizer consumption')")

    if st.button("Run Query"):
        if user_query:
            with st.spinner("Thinking..."):
                table_info = db.get_table_info()  # ✅ fetch schema dynamically
                response = chain.invoke({
                    "question": user_query,
                    "table_info": table_info
                })

            with st.expander("🔍 See generated SQL query"):
                st.code(response)


            try:
                # Execute the generated SQL query
                result = db.run(response)

                # Display result
                if result:
                    st.success("✅ Query executed successfully!")
                    st.write(result)
                else:
                    st.warning("No data returned for this query.")

            except Exception as e:
                st.error(f"⚠️ Error running query: {e}")

