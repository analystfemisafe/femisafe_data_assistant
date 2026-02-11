import streamlit as st
import pandas as pd
from groq import Groq
from sqlalchemy import text

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

# ---------------------------------------------------------
# 🧠 AI BRAIN (Powered by Groq/Llama 3)
# ---------------------------------------------------------
def get_ai_response(prompt):
    """
    Uses Groq (Llama 3) to generate SQL queries.
    """
    # 1. Check for API Key
    if "general" not in st.secrets or "GROQ_API_KEY" not in st.secrets["general"]:
        return "❌ Error: Missing GROQ_API_KEY in .streamlit/secrets.toml"

    client = Groq(api_key=st.secrets["general"]["GROQ_API_KEY"])

    # 2. Define System Instructions & Schema Context
    schema_context = """
    1. femisafe_sales (date, product, net_revenue, units_sold)
    2. femisafe_amazon_salesdata (date, product, net_revenue, units_sold)
    3. femisafe_amazon_addata (date, product, spend_inr, ad_sales)
    4. femisafe_blinkit_salesdata (date, product, revenue)
    """

    system_prompt = f"""
    You are a Postgres SQL Expert for a sales dashboard.
    - Your job is to return ONLY a valid SQL query. 
    - Database Schema: {schema_context}
    
    CRITICAL RULES FOR MATCHING DATA:
    1. **Case Insensitivity:** Always use ILIKE instead of = for text. 
       (Example: USE `product ILIKE '%cup%'` NOT `product = 'Cup'`)
    2. **Dates:** The database uses dates in 'YYYY-MM-DD' format. Ensure you cast string dates if needed.
    3. **Revenue:** If the column is TEXT, cast it: `CAST(REPLACE(net_revenue, ',', '') AS NUMERIC)`.
    4. **Empty Results:** If a user asks for 'Amazon', check both 'Amazon' and 'amazon' (lowercase).
    """

    # 3. Call AI
    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error connecting to Groq: {e}"

# ---------------------------------------------------------
# 🎨 PAGE UI (Required for the App to work)
# ---------------------------------------------------------
def page():
    st.markdown("### 🤖 AI Data Assistant")
    st.caption("⚡ Powered by Groq (Llama 3) - Super Fast & Free")

    # 1. Input Box
    user_query = st.text_input("Ask a question about your data:", placeholder="e.g., Total Amazon revenue last week?")

    # 2. Process Query
    if user_query:
        with st.spinner("Thinking..."):
            
            # A. Get SQL from AI
            sql_query = get_ai_response(user_query)
            
            # B. Check for Errors
            if "Error" in sql_query or "⚠️" in sql_query:
                st.error(sql_query)
                return

            # C. Show the Logic (Optional)
            with st.expander("See generated SQL (Debug)"):
                st.code(sql_query, language="sql")
            
            # D. Run the Query
            try:
                engine = get_db_engine()
                if engine:
                    with engine.connect() as conn:
                        # Use pandas to run the SQL
                        df = pd.read_sql(text(sql_query), conn)
                        
                        if not df.empty:
                            st.success("Here is the data:")
                            st.dataframe(df)
                        else:
                            st.info("Query ran successfully, but returned no data.")
            except Exception as e:
                st.error(f"SQL Execution Error: {e}")