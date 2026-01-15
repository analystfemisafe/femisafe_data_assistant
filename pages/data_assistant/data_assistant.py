import streamlit as st
from langchain_community.utilities import SQLDatabase

def page():

    st.title("🔍 Data Query Assistant")

    # -----------------------------
    # STEP 1: CONNECT TO DATABASE
    # -----------------------------
    db = SQLDatabase.from_uri("postgresql://ayish:ajtp%40511Db@localhost:5432/femisafe_test_db")

    # -----------------------------
    # STEP 2: LOAD LOCAL LLAMA3
    # -----------------------------
    from langchain_ollama import ChatOllama
    llm = ChatOllama(model="llama3")

    # -----------------------------
    # STEP 3: SQL-ONLY PROMPT
    # -----------------------------
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

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
    - When aggregating, always GROUP BY non-aggregated columns.

    Question: {question}
    SQLQuery:
    """)

    chain = prompt | llm | StrOutputParser()

    # -----------------------------
    # STEP 4: NATURAL LANGUAGE INPUT
    # -----------------------------
    user_query = st.text_input(
        "Ask your question (e.g. 'Total Revenue from Flipkart in September')"
    )

    if st.button("Run Query"):
        if user_query:

            # -------------- GENERATE SQL QUERY --------------
            with st.spinner("Thinking..."):
                table_info = db.get_table_info()
                response = chain.invoke({
                    "question": user_query,
                    "table_info": table_info
                })

            st.expander("🔍 See generated SQL query").code(response)

            # -------------- EXECUTE SQL QUERY --------------
            try:
                result = db.run(response)

                if not result:
                    st.warning("No data returned for this query.")
                else:
                    st.success("✅ Query executed successfully!")

                    import pandas as pd
                    import re
                    import ast
                    from decimal import Decimal

                    # Normalize result
                    if isinstance(result, str):
                        try:
                            result = ast.literal_eval(result)
                        except Exception:
                            result = [(result,)]

                    if isinstance(result, list) and all(isinstance(x, str) for x in result):
                        result = [(" ".join(result), )]

                    # Ensure result is a list of tuples
                    if not isinstance(result, list):
                        result = [(result,)]
                    elif result and not isinstance(result[0], (tuple, list)):
                        result = [(result,)]

                    # Convert decimals & clean values
                    cleaned = []
                    for row in result:
                        new_row = []
                        for val in row:
                            if isinstance(val, Decimal):
                                new_row.append(float(val))

                            elif isinstance(val, str) and re.match(r"Decimal\('([\d\.]+)'\)", val):
                                num = re.findall(r"Decimal\('([\d\.]+)'\)", val)[0]
                                new_row.append(float(num))

                            else:
                                new_row.append(val)
                        cleaned.append(tuple(new_row))

                    result = cleaned

                    # ------- DISPLAY LOGIC --------

                    # CASE 1: Single numeric value
                    if len(result) == 1 and len(result[0]) == 1:
                        value = result[0][0]

                        if isinstance(value, (int, float)):
                            formatted = f"{value:,.2f}"
                        else:
                            formatted = str(value)

                        st.markdown(
                            f"""
                            <div style='
                                background-color:#2d2d2d;
                                color:white;
                                border-radius:12px;
                                padding:20px;
                                text-align:center;
                                font-size:2rem;
                                font-weight:bold;
                            '>{formatted}</div>
                            """,
                            unsafe_allow_html=True
                        )

                    # CASE 2: Single row with multiple values → Key-value table
                    elif len(result) == 1:
                        row = result[0]
                        df = pd.DataFrame([row])
                        df = df.T.reset_index()
                        df.columns = ["Field", "Value"]
                        st.table(df)

                    # CASE 3: Multi-row table
                    else:
                        df = pd.DataFrame(result)
                        st.dataframe(df, use_container_width=True)

            except Exception as e:
                st.error(f"⚠️ Error running query: {e}")
