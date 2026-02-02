import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import text

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine(): return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 🛠️ HELPER: MANUAL ROW PARSING
# ---------------------------------------------------------
def clean_flipkart_df(df):
    if df.empty: return df

    # 1. Normalize Headers
    df.columns = df.columns.str.strip().str.lower()
    
    # 2. Rename Columns
    rename_map = {
        "order date": "date", "date": "date",
        "gmv": "gross_revenue", "gross_revenue": "gross_revenue",
        "net revenue": "net_revenue", "net_revenue": "net_revenue",
        "final sale units": "units_sold", "units_sold": "units_sold",
        "sku id": "sku", "sku": "sku",
        "product ": "product", "product": "product"
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # 3. Numeric Cleaning
    for col in ['net_revenue', 'units_sold']:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r'[₹,]', '', regex=True), 
                errors='coerce'
            ).fillna(0)
        else:
            df[col] = 0 

    df['units_sold'] = df['units_sold'].astype('int32')

    # 4. Date Parsing
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
        df.dropna(subset=['date'], inplace=True)
    
    return df

# ---------------------------------------------------------
# 🚀 NUCLEAR-PROOF LOADER (Raw Fetch)
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def get_flipkart_data():
    engine = get_db_engine()
    if not engine: return pd.DataFrame()

    try:
        with engine.connect() as conn:
            # Clear previous errors
            try: conn.rollback()
            except: pass

            # 1. RAW EXECUTION (Bypasses Pandas crash)
            result = conn.execute(text('SELECT * FROM femisafe_flipkart_salesdata'))
            
            # 2. MANUALLY FIX DUPLICATE HEADERS
            raw_keys = list(result.keys()) # e.g. ['Date', 'date', 'SKU']
            clean_keys = []
            seen = set()
            
            for key in raw_keys:
                key_clean = str(key).strip()
                if key_clean in seen:
                    # Rename duplicate: 'date' -> 'date_2'
                    clean_keys.append(f"{key_clean}_{len(seen)}")
                else:
                    clean_keys.append(key_clean)
                    seen.add(key_clean)
            
            # 3. BUILD DATAFRAME MANUALLY
            data = result.fetchall()
            df = pd.DataFrame(data, columns=clean_keys)
            
            # 4. CLEAN
            clean_df = clean_flipkart_df(df)
            
            # Filter Last 365 Days
            if not clean_df.empty and 'date' in clean_df.columns:
                last_year = pd.Timestamp.now() - pd.Timedelta(days=365)
                clean_df = clean_df[clean_df['date'] >= last_year]
                
            return clean_df

    except Exception as e:
        st.error(f"⚠️ Data Error: {e}")
        return pd.DataFrame()

# ===========================================================
# PAGE
# ===========================================================
def page():
    st.title("🛍️ Flipkart Sales Dashboard")

    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    df_fk = get_flipkart_data()

    if df_fk.empty:
        st.warning("No Flipkart data available.")
        return

    # KPIs
    total_revenue = df_fk['net_revenue'].sum()
    total_units = df_fk['units_sold'].sum()
    latest_date = df_fk['date'].max()
    latest_month = latest_date.strftime('%B') if not pd.isnull(latest_date) else "Unknown"
    
    latest_data = df_fk[df_fk['month'] == latest_month] if 'month' in df_fk.columns else pd.DataFrame()
    latest_rev_val = latest_data['net_revenue'].sum() if not latest_data.empty else 0

    # Cards
    col1, col2 = st.columns(2)
    col1.metric("Latest Month Revenue", f"₹{latest_rev_val:,.0f}", latest_month)
    col2.metric("Total Units (Year)", f"{int(total_units):,}")

    # Chart
    df_daily = df_fk.groupby('date', as_index=False)[['net_revenue', 'units_sold']].sum()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_daily['date'], y=df_daily['net_revenue'], name='Revenue', line=dict(color='#2874f0')))
    fig.add_trace(go.Scatter(x=df_daily['date'], y=df_daily['units_sold'], name='Units', line=dict(color='#ff9f00'), yaxis='y2'))
    
    fig.update_layout(
        title="Sales Trend", 
        yaxis2=dict(overlaying='y', side='right', showgrid=False),
        template="plotly_dark"
    )
    st.plotly_chart(fig, use_container_width=True)