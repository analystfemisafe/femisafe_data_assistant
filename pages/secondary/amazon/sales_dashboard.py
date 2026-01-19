import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine, text

def page():
    st.title("📦 Amazon Sales Dashboard (Live Data)")

    # ---------------------------------------------------------
    # 1. LOAD DATA
    # ---------------------------------------------------------
    @st.cache_data(ttl=600)
    def load_data():
        try:
            db_url = st.secrets["postgres"]["url"]
            engine = create_engine(db_url)
            with engine.connect() as conn:
                query = text("SELECT * FROM femisafe_amazon_salesdata")
                df = pd.read_sql(query, conn)
            return df
        except Exception as e:
            st.error(f"⚠️ Database Connection Failed: {e}")
            return pd.DataFrame()

    df = load_data()

    if df.empty:
        st.warning("⚠️ No data found.")
        return

    # ---------------------------------------------------------
    # 2. DATA CLEANING (Updated Fix) 🛠️
    # ---------------------------------------------------------
    try:
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
        df['date'] = pd.to_datetime(df['date'], errors='coerce')

        # Identify Revenue Column
        rev_col = None
        if 'ordered_product_sales' in df.columns:
            rev_col = 'ordered_product_sales'
        elif 'gross_revenue' in df.columns:
            rev_col = 'gross_revenue'

        # CLEAN REVENUE (Regex: Keep only digits and dots)
        if rev_col:
            df['revenue'] = df[rev_col].astype(str).str.replace(r'[^\d.]', '', regex=True)
            df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce').fillna(0)
        else:
            df['revenue'] = 0

        # CLEAN UNITS
        if 'units_ordered' in df.columns:
            df['units_ordered'] = df['units_ordered'].astype(str).str.replace(r'[^\d.]', '', regex=True)
            df['units_ordered'] = pd.to_numeric(df['units_ordered'], errors='coerce').fillna(0)
        
        # CLEAN SESSIONS
        if 'sessions_total' in df.columns:
            df['sessions_total'] = df['sessions_total'].astype(str).str.replace(r'[^\d.]', '', regex=True)
            df['sessions_total'] = pd.to_numeric(df['sessions_total'], errors='coerce').fillna(0)

    except Exception as e:
        st.error(f"⚠️ Data Error: {e}")
        return

    # ---------------------------------------------------------
    # 3. METRICS
    # ---------------------------------------------------------
    total_rev = df['revenue'].sum()
    total_units = df['units_ordered'].sum() if 'units_ordered' in df.columns else 0
    total_sessions = df['sessions_total'].sum() if 'sessions_total' in df.columns else 0
    conversion_rate = (total_units / total_sessions * 100) if total_sessions > 0 else 0

    st.markdown("### 📊 Performance Overview")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("💰 Total Sales", f"₹{total_rev:,.0f}")
    kpi2.metric("📦 Units Ordered", f"{int(total_units):,}")
    kpi3.metric("👀 Total Sessions", f"{int(total_sessions):,}")
    kpi4.metric("⚡ Conversion Rate", f"{conversion_rate:.2f}%")

    st.divider()

    # ---------------------------------------------------------
    # 4. CHARTS
    # ---------------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Sales Trend")
        if total_rev > 0:
            daily_sales = df.groupby('date')['revenue'].sum().reset_index()
            fig = go.Figure(go.Scatter(x=daily_sales['date'], y=daily_sales['revenue'], mode='lines+markers', line=dict(color='#FF9900')))
            fig.update_layout(height=350, template='plotly_white')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No revenue data available.")

    with col2:
        st.subheader("🏆 Top Products (Units)")
        if 'title' in df.columns:
            top = df.groupby('title')['units_ordered'].sum().reset_index().sort_values('units_ordered', ascending=False).head(5)
            top['short'] = top['title'].astype(str).str[:40] + "..."
            fig = go.Figure(go.Bar(x=top['units_ordered'], y=top['short'], orientation='h', marker_color='#232F3E'))
            fig.update_layout(height=350, template='plotly_white')
            st.plotly_chart(fig, use_container_width=True)