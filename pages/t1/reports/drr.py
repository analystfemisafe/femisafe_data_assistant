import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime, timedelta
import numpy as np
import textwrap

# Import DB Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    import os
    def get_db_engine(): return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 🛠️ HELPER: PRODUCT NAME NORMALIZER
# ---------------------------------------------------------
def normalize_product(name):
    name = str(name).lower()
    if "razor" in name: return "Razors"
    if "nipple" in name or "pasties" in name: return "Nipple Pasties"
    if "pimple" in name or "patch" in name: return "Pimple Patch"
    if "liner" in name: return "Panty Liners"
    if "sweat" in name or "pad" in name: return "Sweat Pad"
    if "lotion" in name: return "Magnesium Lotion"
    if "wash" in name: return "Intimate Wash"
    if "rollon" in name or "roll-on" in name: return "Underarm Rollon"
    if "cup" in name and "wash" not in name: return "Menstrual Cups"
    if "cramp" in name: return "Period Cramp Rollon"
    if "lubricant" in name: return "Lubricants"
    if "cup wash" in name: return "Cup Wash"
    if "period panties" in name or "panty" in name: return "Period Panties"
    if "sterilizer" in name: return "Sterilizers"
    if "energizer" in name: return "Period Energizer"
    if "aloe" in name or "gel" in name: return "Aloe Gel"
    return name.title()

# ---------------------------------------------------------
# 🔍 SMART COLUMN DETECTOR
# ---------------------------------------------------------
def get_valid_product_col(engine, table_name):
    try:
        query = text(f"SELECT * FROM {table_name} LIMIT 0")
        with engine.connect() as conn:
            result = conn.execute(query)
            actual_columns = list(result.keys())
        
        candidates = [
            'product_name', 'product_title', 'title', 'product', 
            'product_title_at_time', 'product_title_at_time_of_sale', 
            'lineitem_name', 'item_name', 'description'
        ]
        
        for candidate in candidates:
            if candidate in actual_columns:
                return candidate
        return f"ERROR: Found columns {actual_columns}"
    except Exception as e:
        return f"ERROR: {str(e)}"

# ---------------------------------------------------------
# 📊 DATA FETCHING
# ---------------------------------------------------------
def get_channel_data(engine, table_name, date_col, rev_col, qty_col, product_col, target_date, clean_numeric=False):
    if "ERROR" in product_col:
        st.error(f"⚠️ Could not find Product Column for `{table_name}`.\n\n{product_col}")
        return pd.DataFrame(columns=['Product', 'Units', 'Revenue'])

    try:
        if clean_numeric:
            qty_sql = f"SUM(CAST(REGEXP_REPLACE(CAST({qty_col} AS TEXT), '[^0-9.]', '', 'g') AS NUMERIC))"
            rev_sql = f"SUM(CAST(REGEXP_REPLACE(CAST({rev_col} AS TEXT), '[^0-9.]', '', 'g') AS NUMERIC))"
        else:
            qty_sql = f"SUM({qty_col})"
            rev_sql = f"SUM({rev_col})"

        query = text(f"""
            SELECT 
                {product_col} as raw_product, 
                {qty_sql} as units, 
                {rev_sql} as revenue
            FROM {table_name}
            WHERE DATE({date_col}) = :target_date
            GROUP BY raw_product
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"target_date": target_date})
            
        if df.empty: 
            return pd.DataFrame(columns=['Product', 'Units', 'Revenue'])

        df['Product'] = df['raw_product'].apply(normalize_product)
        df_grouped = df.groupby('Product')[['units', 'revenue']].sum().reset_index()
        df_grouped.columns = ['Product', 'Units', 'Revenue']
        return df_grouped

    except Exception as e:
        st.error(f"❌ Error in `{table_name}`: {e}")
        return pd.DataFrame(columns=['Product', 'Units', 'Revenue'])

# ---------------------------------------------------------
# 🎨 COLOR LOGIC FOR GROWTH
# ---------------------------------------------------------
def color_growth_cell(val):
    if pd.isna(val) or val == 0:
        return 'color: white'
    
    if val >= 50: bg = '#1e7e34' 
    elif val >= 20: bg = '#28a745'
    elif val > 0: bg = '#2ea44f'
    elif val <= -50: bg = '#bd2130' 
    elif val <= -20: bg = '#dc3545'
    else: bg = '#e65c5c' 
        
    return f'background-color: {bg}; color: white; font-weight: bold;'

# ---------------------------------------------------------
# 🚀 MAIN REPORT FUNCTION
# ---------------------------------------------------------
def show_drr():
    st.markdown("### 📉 Daily Run Rate (DRR) Report")

    engine = get_db_engine()
    if not engine:
        st.error("Database not connected.")
        return

    # 1. Controls
    col_d, col_c = st.columns([2, 5])
    with col_d:
        report_date = st.date_input("Select Report Date", value=datetime.now().date() - timedelta(days=1))
    with col_c:
        st.write("") 
        st.write("")
        show_d1 = st.checkbox("Show Channel D-1 Columns", value=False) # Renamed for clarity

    current_date = report_date
    prev_date = report_date - timedelta(days=1)

    st.info(f"📊 Showing Data For: **{current_date.strftime('%d %b %Y')}**")

    # 2. AUTO-DETECT COLUMNS
    amz_prod_col = get_valid_product_col(engine, "femisafe_amazon_salesdata")
    blk_prod_col = get_valid_product_col(engine, "femisafe_blinkit_salesdata")
    shp_prod_col = get_valid_product_col(engine, "femisafe_shopify_salesdata")

    # 3. Fetch Data
    amz_curr = get_channel_data(engine, "femisafe_amazon_salesdata", "date", "net_revenue", "units_ordered", amz_prod_col, current_date, clean_numeric=True)
    amz_prev = get_channel_data(engine, "femisafe_amazon_salesdata", "date", "net_revenue", "units_ordered", amz_prod_col, prev_date, clean_numeric=True)

    blk_curr = get_channel_data(engine, "femisafe_blinkit_salesdata", "order_date", "net_revenue", "quantity", blk_prod_col, current_date, clean_numeric=False)
    blk_prev = get_channel_data(engine, "femisafe_blinkit_salesdata", "order_date", "net_revenue", "quantity", blk_prod_col, prev_date, clean_numeric=False)

    shp_curr = get_channel_data(engine, "femisafe_shopify_salesdata", "order_date", "revenue", "units_sold", shp_prod_col, current_date, clean_numeric=True)
    shp_prev = get_channel_data(engine, "femisafe_shopify_salesdata", "order_date", "revenue", "units_sold", shp_prod_col, prev_date, clean_numeric=True)

    # 4. Merge Logic
    all_products = sorted(list(set(
        amz_curr['Product'].tolist() + amz_prev['Product'].tolist() +
        blk_curr['Product'].tolist() + blk_prev['Product'].tolist() +
        shp_curr['Product'].tolist() + shp_prev['Product'].tolist()
    )))

    if not all_products:
        st.warning(f"⚠️ No data found for {current_date}.")
        return

    master_df = pd.DataFrame({'Product': all_products})

    def merge_channel(base_df, data_df, prefix):
        merged = pd.merge(base_df, data_df, on='Product', how='left').fillna(0)
        merged.rename(columns={'Units': f'{prefix}_Units', 'Revenue': f'{prefix}_Rev'}, inplace=True)
        return merged

    master_df = merge_channel(master_df, amz_prev, "Amz_D1")
    master_df = merge_channel(master_df, amz_curr, "Amz_Curr")
    master_df = merge_channel(master_df, shp_prev, "Shp_D1")
    master_df = merge_channel(master_df, shp_curr, "Shp_Curr")
    master_df = merge_channel(master_df, blk_prev, "Blk_D1")
    master_df = merge_channel(master_df, blk_curr, "Blk_Curr")

    # 5. Calculations
    def calc_growth(curr, prev):
        return np.where(prev > 0, ((curr - prev) / prev) * 100, 0)

    master_df['Amz_Growth'] = calc_growth(master_df['Amz_Curr_Rev'], master_df['Amz_D1_Rev'])
    master_df['Shp_Growth'] = calc_growth(master_df['Shp_Curr_Rev'], master_df['Shp_D1_Rev'])
    master_df['Blk_Growth'] = calc_growth(master_df['Blk_Curr_Rev'], master_df['Blk_D1_Rev'])

    master_df['Total_Curr_Units'] = master_df['Amz_Curr_Units'] + master_df['Shp_Curr_Units'] + master_df['Blk_Curr_Units']
    master_df['Total_Curr_Rev'] = master_df['Amz_Curr_Rev'] + master_df['Shp_Curr_Rev'] + master_df['Blk_Curr_Rev']
    master_df['Total_D1_Units'] = master_df['Amz_D1_Units'] + master_df['Shp_D1_Units'] + master_df['Blk_D1_Units']
    master_df['Total_D1_Rev'] = master_df['Amz_D1_Rev'] + master_df['Shp_D1_Rev'] + master_df['Blk_D1_Rev']

    total_day_rev = master_df['Total_Curr_Rev'].sum()
    master_df['Share_Pct'] = np.where(total_day_rev > 0, (master_df['Total_Curr_Rev'] / total_day_rev) * 100, 0)

    # Sort
    master_df = master_df.sort_values(by='Total_Curr_Units', ascending=False)

    # 6. Grand Total Row
    total_row = {
        'Product': 'GRAND TOTAL',
        'Amz_D1_Units': master_df['Amz_D1_Units'].sum(), 'Amz_D1_Rev': master_df['Amz_D1_Rev'].sum(),
        'Amz_Curr_Units': master_df['Amz_Curr_Units'].sum(), 'Amz_Curr_Rev': master_df['Amz_Curr_Rev'].sum(),
        'Shp_D1_Units': master_df['Shp_D1_Units'].sum(), 'Shp_D1_Rev': master_df['Shp_D1_Rev'].sum(),
        'Shp_Curr_Units': master_df['Shp_Curr_Units'].sum(), 'Shp_Curr_Rev': master_df['Shp_Curr_Rev'].sum(),
        'Blk_D1_Units': master_df['Blk_D1_Units'].sum(), 'Blk_D1_Rev': master_df['Blk_D1_Rev'].sum(),
        'Blk_Curr_Units': master_df['Blk_Curr_Units'].sum(), 'Blk_Curr_Rev': master_df['Blk_Curr_Rev'].sum(),
        'Total_Curr_Units': master_df['Total_Curr_Units'].sum(), 'Total_Curr_Rev': master_df['Total_Curr_Rev'].sum(),
        'Total_D1_Units': master_df['Total_D1_Units'].sum(), 'Total_D1_Rev': master_df['Total_D1_Rev'].sum(),
        'Share_Pct': 100.0
    }
    total_row['Amz_Growth'] = calc_growth(total_row['Amz_Curr_Rev'], total_row['Amz_D1_Rev'])
    total_row['Shp_Growth'] = calc_growth(total_row['Shp_Curr_Rev'], total_row['Shp_D1_Rev'])
    total_row['Blk_Growth'] = calc_growth(total_row['Blk_Curr_Rev'], total_row['Blk_D1_Rev'])
    
    master_df = pd.concat([master_df, pd.DataFrame([total_row])], ignore_index=True)

    # 7. DYNAMIC FORMATTING & COLUMN SELECTION
    
    if show_d1:
        # FULL VIEW (D-1 for EVERYONE)
        col_order = [
            'Amz_D1_Units', 'Amz_D1_Rev', 'Amz_Curr_Units', 'Amz_Curr_Rev', 'Amz_Growth',
            'Blk_D1_Units', 'Blk_D1_Rev', 'Blk_Curr_Units', 'Blk_Curr_Rev', 'Blk_Growth',
            'Shp_D1_Units', 'Shp_D1_Rev', 'Shp_Curr_Units', 'Shp_Curr_Rev', 'Shp_Growth',
            'Total_Curr_Units', 'Total_Curr_Rev', 'Share_Pct', 'Total_D1_Units', 'Total_D1_Rev'
        ]
        columns = [
            ('AMAZON', 'D-1 Units'), ('AMAZON', 'D-1 Sales'), ('AMAZON', 'Units'), ('AMAZON', 'Sales'), ('AMAZON', 'Growth %'),
            ('BLINKIT', 'D-1 Units'), ('BLINKIT', 'D-1 Sales'), ('BLINKIT', 'Units'), ('BLINKIT', 'Sales'), ('BLINKIT', 'Growth %'),
            ('SHOPIFY', 'D-1 Units'), ('SHOPIFY', 'D-1 Sales'), ('SHOPIFY', 'Units'), ('SHOPIFY', 'Sales'), ('SHOPIFY', 'Growth %'),
            ('TOTAL', 'Units'), ('TOTAL', 'Sales'), ('TOTAL', 'Share %'), ('TOTAL', 'D-1 Units'), ('TOTAL', 'D-1 Sales'),
        ]
        az_idx, bl_idx, sh_idx, tot_idx = 2, 3, 4, 5
        
    else:
        # COMPACT VIEW (But KEEP Total D-1)
        col_order = [
            'Amz_Curr_Units', 'Amz_Curr_Rev', 'Amz_Growth',
            'Blk_Curr_Units', 'Blk_Curr_Rev', 'Blk_Growth',
            'Shp_Curr_Units', 'Shp_Curr_Rev', 'Shp_Growth',
            'Total_Curr_Units', 'Total_Curr_Rev', 'Share_Pct', 'Total_D1_Units', 'Total_D1_Rev' # ⬅️ ADDED BACK
        ]
        columns = [
            ('AMAZON', 'Units'), ('AMAZON', 'Sales'), ('AMAZON', 'Growth %'),
            ('BLINKIT', 'Units'), ('BLINKIT', 'Sales'), ('BLINKIT', 'Growth %'),
            ('SHOPIFY', 'Units'), ('SHOPIFY', 'Sales'), ('SHOPIFY', 'Growth %'),
            ('TOTAL', 'Units'), ('TOTAL', 'Sales'), ('TOTAL', 'Share %'), ('TOTAL', 'D-1 Units'), ('TOTAL', 'D-1 Sales'), # ⬅️ ADDED BACK
        ]
        az_idx, bl_idx, sh_idx, tot_idx = 2, 3, 4, 5
    
    final_df = master_df.set_index('Product')[col_order]
    final_df.columns = pd.MultiIndex.from_tuples(columns)
    
    # Identify Column Types for Styler
    growth_cols = [c for c in columns if 'Growth %' in c[1]]
    num_cols = [c for c in columns if 'Units' in c[1] or 'Sales' in c[1]]
    pct_cols = [c for c in columns if '%' in c[1]]

    # Styler
    styler = final_df.style\
        .format("{:,.0f}", subset=pd.IndexSlice[:, num_cols])\
        .format("{:,.1f}%", subset=pd.IndexSlice[:, pct_cols])\
        .applymap(color_growth_cell, subset=pd.IndexSlice[:, growth_cols])\
        .set_table_attributes('class="custom-table"')

    # Dynamic CSS
    custom_css = textwrap.dedent(f"""
    <style>
        .custom-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: sans-serif;
            font-size: 13px;
        }}
        .custom-table th, .custom-table td {{
            border: 1px solid #444; 
            padding: 8px;
            text-align: center;
        }}
        /* Dynamic Header Coloring */
        .custom-table thead tr:nth-child(1) th:nth-child({az_idx}) {{ background-color: #1f4e78 !important; color: white; }}
        .custom-table thead tr:nth-child(1) th:nth-child({bl_idx}) {{ background-color: #70ad47 !important; color: white; }}
        .custom-table thead tr:nth-child(1) th:nth-child({sh_idx}) {{ background-color: #008080 !important; color: white; }}
        .custom-table thead tr:nth-child(1) th:nth-child({tot_idx}) {{ background-color: #996633 !important; color: white; }}

        .custom-table thead tr:nth-child(2) th {{ background-color: #333; color: #eee; }}
        .custom-table tbody tr th {{ 
            text-align: left; 
            background-color: #262730; 
            color: white; 
        }}
        .custom-table tbody td {{ color: #eee; }}
        .custom-table tbody tr:last-child {{ 
            font-weight: bold; 
            border-top: 2px solid #555; 
        }}
        .custom-table tbody tr:last-child th {{
            background-color: #996633;
            color: white;
        }}
    </style>
    """)

    st.markdown(custom_css, unsafe_allow_html=True)
    st.markdown(styler.to_html(), unsafe_allow_html=True)