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
                    from decimal import Decimal

                    # Normalize result → list of tuples
                    if isinstance(result, str):
                        try:
                            import ast
                            result = ast.literal_eval(result)
                        except Exception:
                            result = [(result,)]

                    if isinstance(result, list) and all(isinstance(x, str) for x in result):
                        result = [("".join(result), )]

                    # Clean decimals
                    cleaned = []
                    for row in result:
                        cleaned_row = []
                        for x in row:
                            if isinstance(x, Decimal):
                                cleaned_row.append(float(x))
                            elif isinstance(x, str) and re.match(r"Decimal\('([\d\.]+)'\)", x):
                                import re
                                cleaned_row.append(float(re.findall(r"Decimal\('([\d\.]+)'\)", x)[0]))
                            else:
                                cleaned_row.append(x)
                        cleaned.append(tuple(cleaned_row))

                    result = cleaned

                    # -------------- DISPLAY LOGIC --------------
                    if len(result) == 1 and len(result[0]) == 1:
                        value = result[0][0]

                        if isinstance(value, (int, float)):
                            formatted = f"₹{value:,.2f}"
                        else:
                            formatted = str(value)

                        st.markdown(
                            f"""
                            <div style='
                                background-color:#2d2d2d;
                                color:white;
                                border-radius:10px;
                                padding:20px;
                                text-align:center;
                                font-size:1.6rem;
                                font-weight:bold;
                            '>{formatted}</div>
                            """,
                            unsafe_allow_html=True
                        )

                    else:
                        df = pd.DataFrame(result)
                        st.dataframe(df, use_container_width=True)

            except Exception as e:
                st.error(f"⚠️ Error running query: {e}")
