import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text, inspect
import google.generativeai as genai
import os
import datetime

# -----------------------------
# 1. SETUP & CONFIG
# -----------------------------

try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

def get_gemini_model():
    """Initialize Gemini Model using Direct API"""
    try:
        api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
        if not api_key:
            st.error("❌ Google API Key is missing.")
            return None
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-2.5-flash')
    except Exception as e:
        st.error(f"⚠️ Failed to load Gemini: {e}")
        return None

# -----------------------------
# 2. INTELLIGENCE LAYER (UPDATED RULES)
# -----------------------------

@st.cache_data(ttl=3600)
def get_database_schema():
    """Scans the database and organizes tables by Primary vs Secondary."""
    engine = get_db_engine()
    if not engine: return ""
    
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    primary_schema = ""
    secondary_schema = ""
    
    # Define table categories
    secondary_tables = [
        "femisafe_blinkit_salesdata", "femisafe_blinkit_addata",
        "femisafe_amazon_salesdata", "femisafe_amazon_addata",
        "femisafe_swiggy_salesdata", "femisafe_swiggy_addata",
        "femisafe_flipkart_salesdata", "femisafe_shopify_salesdata"
    ]
    
    for table in table_names:
        if "femisafe" not in table.lower(): continue
            
        columns = [f"{col['name']} ({col['type']})" for col in inspector.get_columns(table)]
        col_str = ", ".join(columns)
        
        if table == "femisafe_sales":
            primary_schema += f"- PRIMARY TABLE (HISTORICAL): {table}\n  Columns: {col_str}\n\n"
        elif table in secondary_tables:
            secondary_schema += f"- SECONDARY TABLE (RECENT/LIVE): {table}\n  Columns: {col_str}\n\n"
            
    return primary_schema + secondary_schema

def generate_sql_query(question, schema_context, model):
    """Generates SQL with STRICT routing logic for Primary vs Secondary tables."""
    
    # Get current date for context
    today = datetime.date.today()
    current_month = today.strftime("%B %Y")
    last_month = (today.replace(day=1) - datetime.timedelta(days=1)).strftime("%B %Y")
    
    prompt = f"""
    You are an expert PostgreSQL Data Analyst.
    Current Date: {today} (Month: {current_month})
    
    DATABASE SCHEMA:
    {schema_context}

    STRICT DATA ROUTING RULES:
    1. **HISTORICAL DATA (Last Month or Older)**: 
       - If the user asks for data from "{last_month}" or older (e.g., "last month", "last year", "2024"), you MUST use the primary table: `femisafe_sales`.
       - DO NOT use the secondary tables for historical queries.

    2. **RECENT DATA (Current Month/Week)**: 
       - If the user asks for "Current Month", "This Week", "Today", or "Recent" data, you MUST use the secondary tables: 
         (`femisafe_blinkit_salesdata`, `femisafe_amazon_salesdata`, `femisafe_swiggy_salesdata`, `femisafe_flipkart_salesdata`, `femisafe_shopify_salesdata`).

    3. **COMBINED DATA (Trends/All Time)**:
       - If the query spans BOTH history and now (e.g., "Trend for last 6 months" or "Total sales all time"), you must construct a query that UNION ALLs `femisafe_sales` with the relevant secondary tables.

    GENERAL SQL RULES:
    - Return ONLY the raw SQL query. No markdown.
    - Use "double quotes" for column names with spaces.
    - Use ILIKE for case-insensitive text matching.
    - Limit to 50 rows unless specified.

    USER QUESTION: "{question}"
    
    SQL QUERY:
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.replace("```sql", "").replace("```", "").strip()
    except Exception as e:
        return f"ERROR_GENERATING_SQL: {str(e)}"

def explain_data(question, df, model):
    data_summary = df.to_string(index=False, max_rows=10)
    prompt = f"User Question: '{question}'\nData: {data_summary}\nSummarize this in 1 sentence."
    try:
        return model.generate_content(prompt).text
    except:
        return "Here is the data."

# -----------------------------
# 3. PAGE UI
# -----------------------------
def page():
    st.title("🤖 AI Data Assistant")
    st.caption("I automatically route queries: `femisafe_sales` for history, separate tables for recent data.")

    if "messages" not in st.session_state: st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "data" in msg: st.dataframe(msg["data"])
            if "chart" in msg and msg["chart"]: st.plotly_chart(msg["chart"], use_container_width=True)

    if prompt := st.chat_input("Ex: 'Revenue last month' (History) or 'Revenue this week' (Recent)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            model = get_gemini_model()
            engine = get_db_engine()
            
            if model and engine:
                with st.spinner("Routing Query..."):
                    schema = get_database_schema()
                    sql_query = generate_sql_query(prompt, schema, model)
                
                if "ERROR" in sql_query:
                    st.error("I couldn't process that request.")
                    return

                with st.expander("View Generated SQL (Check Routing)"):
                    st.code(sql_query, language="sql")
                
                with st.spinner("Fetching Data..."):
                    try:
                        with engine.connect() as conn:
                            df = pd.read_sql(text(sql_query), conn)
                        
                        if df.empty:
                            st.warning("No data found.")
                        else:
                            summary = explain_data(prompt, df, model)
                            st.markdown(summary)
                            st.dataframe(df)

                            chart = None
                            if len(df) > 1:
                                num = df.select_dtypes(include=['number']).columns
                                date = [c for c in df.columns if 'date' in c.lower()]
                                cat = df.select_dtypes(include=['object', 'category']).columns
                                
                                if date and num: chart = px.line(df, x=date[0], y=num[0])
                                elif cat and num: chart = px.bar(df, x=cat[0], y=num[0])
                                if chart: st.plotly_chart(chart, use_container_width=True)

                            st.session_state.messages.append({"role": "assistant", "content": summary, "data": df, "chart": chart})

                    except Exception as e:
                        st.error(f"SQL Error: {e}")