import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text, inspect
import google.generativeai as genai
import os
import time

# -----------------------------
# 1. SETUP & CONFIG
# -----------------------------
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    @st.cache_resource
    def get_db_engine(): return create_engine(os.environ.get("DATABASE_URL"))

def get_gemini_model():
    """Initialize Gemini Model"""
    try:
        api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
        if not api_key: return None, "Missing Google API Key."
        
        genai.configure(api_key=api_key)
        
        # 🟢 SWITCHED TO 2.0 FLASH (Better Limits than 2.5)
        return genai.GenerativeModel('gemini-2.0-flash'), None
    except Exception as e:
        return None, str(e)

# -----------------------------
# 2. INTELLIGENCE LAYER (With Retry Logic)
# -----------------------------
@st.cache_data(ttl=3600)
def get_database_schema():
    engine = get_db_engine()
    if not engine: return ""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    schema_text = ""
    for table in table_names:
        if "femisafe" in table.lower():
            schema_text += f"Table: {table}\n"
    return schema_text

def generate_content_with_retry(model, prompt, retries=3):
    """Tries to call Gemini. If quota exceeded, waits and tries again."""
    for attempt in range(retries):
        try:
            return model.generate_content(prompt)
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                wait_time = (attempt + 1) * 5  # Wait 5s, then 10s...
                time.sleep(wait_time)
                continue # Try again
            else:
                raise e # Real error, don't ignore
    raise Exception("Daily AI Quota Exceeded. Please try again tomorrow.")

# -----------------------------
# 3. PAGE UI
# -----------------------------
def page():
    st.title("🤖 AI Data Assistant")
    st.caption("Powered by Gemini 2.0 Flash (Stable)")

    if "messages" not in st.session_state: st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "data" in msg: st.dataframe(msg["data"])
            if "chart" in msg and msg["chart"]: st.plotly_chart(msg["chart"], use_container_width=True)

    if prompt := st.chat_input("Ex: 'Revenue last month' or 'Amazon sales today'"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.write(prompt)

        with st.chat_message("assistant"):
            model, err = get_gemini_model()
            if err:
                st.error(f"❌ Setup Error: {err}")
                return

            with st.spinner("Thinking..."):
                try:
                    schema = get_database_schema()
                    full_prompt = f"""
                    You are a SQL Expert. Convert this question to a PostgreSQL query.
                    Schema: {schema}
                    Question: {prompt}
                    Return ONLY the SQL. No markdown.
                    """
                    
                    # 🛡️ CALL WITH RETRY LOGIC
                    response = generate_content_with_retry(model, full_prompt)
                    sql_query = response.text.replace("```sql", "").replace("```", "").strip()
                    
                    # Show SQL for transparency
                    with st.expander("View SQL"):
                        st.code(sql_query, language="sql")
                    
                    # Run Query
                    engine = get_db_engine()
                    with engine.connect() as conn:
                        df = pd.read_sql(text(sql_query), conn)
                    
                    if df.empty:
                        msg = "I ran the query, but no data was found."
                        st.warning(msg)
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                    else:
                        # Generate Summary
                        summary_prompt = f"Summarize this data table in 1 sentence related to: {prompt}\nData:\n{df.to_string(max_rows=5)}"
                        summary_res = generate_content_with_retry(model, summary_prompt)
                        summary = summary_res.text

                        st.markdown(summary)
                        st.dataframe(df)
                        
                        # Save
                        st.session_state.messages.append({"role": "assistant", "content": summary, "data": df})

                except Exception as e:
                    if "Quota" in str(e):
                        st.error("⏳ AI is busy (Quota Limit). Please wait 30 seconds and try again.")
                    else:
                        st.error(f"❌ Error: {str(e)}")