import os
import streamlit as st
import pandas as pd
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    import os
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

# -----------------------------
# 🚀 OPTIMIZED RESOURCE LOADERS
# -----------------------------

@st.cache_resource
def get_sql_database():
    """Create LangChain SQLDatabase wrapper around our pooled engine"""
    engine = get_db_engine()
    if engine:
        return SQLDatabase(engine)
    return None

@st.cache_resource
def get_llm():
    """Initialize Gemini LLM once and cache it"""
    try:
        try:
            api_key = st.secrets["GOOGLE_API_KEY"]
        except (FileNotFoundError, KeyError):
            api_key = os.environ.get("GOOGLE_API_KEY")

        if not api_key:
            return None

        return ChatGoogleGenerativeAI(
            model="gemini-pro", 
            google_api_key=api_key,
            temperature=0
        )
    except Exception as e:
        st.error(f"⚠️ Failed to load Gemini: {e}")
        return None

# -----------------------------
# PAGE FUNCTION
# -----------------------------
def page():

    st.title("🔍 Data Query Assistant (Optimized)")

    # 1. Load Resources
    db = get_sql_database()
    llm = get_llm()

    if not db:
        st.error("❌ Database connection failed.")
        return
    if not llm:
        st.error("❌ Google API Key not found.")
        return

    # 2. Define Prompt
    # (Kept identical to preserve your specific instructions)
    prompt = ChatPromptTemplate.from_template("""
    You are an expert SQL assistant.
    Convert the user's natural language question into a valid SQL query for PostgreSQL.

    RULES:
    - Output ONLY the executable SQL. Do NOT include markdown formatting (like ```sql).
    - The table name is femisafe_sales (Primary) but check others if needed:
      - femisafe_blinkit_salesdata
      - femisafe_amazon_salesdata
    - Columns generally include: revenue, month, channels, order_date, sku_units, etc.
    - When filtering by month, use the 'month' column directly.
    - Be careful with string values — always wrap them in single quotes.
    - Limit results to 50 unless specified otherwise.

    Question: {question}
    SQLQuery:
    """)

    chain = prompt | llm | StrOutputParser()

    # 3. Input & Execution
    user_query = st.text_input("Ask your question (e.g. 'Total Revenue from Amazon in October')")

    if st.button("Run Query"):
        if user_query:
            with st.spinner("Thinking (Gemini)..."):
                try:
                    # A. Generate SQL
                    # We pass the schema info from the cached DB object
                    table_info = db.get_table_info()
                    response = chain.invoke({"question": user_query, "table_info": table_info})
                    
                    # Clean SQL
                    clean_sql = response.replace("```sql", "").replace("```", "").strip()
                    
                except Exception as e:
                    st.error(f"Error generating query: {e}")
                    return

            # Show generated SQL
            st.expander("🔍 See generated SQL query").code(clean_sql, language="sql")

            # B. Execute SQL (Optimized via Pandas)
            # using pd.read_sql via the engine is much more robust than db.run() + parsing
            try:
                engine = get_db_engine()
                with engine.connect() as conn:
                    # pandas handles types (decimals, dates) automatically
                    df_result = pd.read_sql(clean_sql, conn)

                if df_result.empty:
                    st.warning("Query executed successfully, but returned no data.")
                else:
                    st.success("✅ Query executed successfully!")
                    
                    # C. Smart Display
                    # If single value (e.g. "Total Revenue"), show big number
                    if df_result.shape == (1, 1):
                        val = df_result.iloc[0, 0]
                        fmt = f"{val:,.2f}" if isinstance(val, (int, float)) else str(val)
                        st.metric(label="Result", value=fmt)
                    else:
                        # Otherwise show table
                        st.dataframe(df_result, use_container_width=True)

            except Exception as e:
                st.error(f"⚠️ SQL Execution Error: {e}")