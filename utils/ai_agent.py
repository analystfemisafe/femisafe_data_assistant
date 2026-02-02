import os
import pandas as pd
import google.generativeai as genai
from sqlalchemy import text, inspect
import streamlit as st

# Configure Gemini
try:
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
except:
    pass

def get_schema_info(engine):
    """
    Scans the database and returns a string describing all tables and columns.
    This gives the AI the 'Context' it needs to write correct SQL.
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    schema_text = ""
    for table in table_names:
        # focus only on sales data tables to save context window
        if "femisafe" in table:
            columns = [col['name'] for col in inspector.get_columns(table)]
            schema_text += f"- Table: {table}\n  Columns: {', '.join(columns)}\n"
            
    return schema_text

def ask_data_assistant(question, engine):
    """
    1. Generates SQL based on the question & schema.
    2. Runs the SQL.
    3. If it fails, asks AI to fix it.
    4. Returns the DataFrame and the Explanation.
    """
    
    # 1. Get Schema Context
    schema_context = get_schema_info(engine)
    
    # 2. Define the Prompt
    prompt = f"""
    You are an expert PostgreSQL Data Analyst. 
    Your goal is to answer the user's question by writing a VALID SQL query.
    
    Database Schema:
    {schema_context}
    
    Rules:
    1. Return ONLY the SQL query. No markdown, no explanation, no ```sql tags.
    2. Use PostgreSQL syntax (e.g. use "double quotes" for column names with spaces).
    3. The date columns are usually named 'date' or 'order_date'. Check schema carefully.
    4. Ignore case sensitivity issues by using ILIKE if needed.
    5. LIMIT results to 50 unless asked otherwise.
    
    User Question: "{question}"
    SQL Query:
    """
    
    model = genai.GenerativeModel('gemini-pro')
    
    try:
        # Step A: Generate SQL
        response = model.generate_content(prompt)
        sql_query = response.text.strip().replace("```sql", "").replace("```", "")
        
        # Step B: Run SQL
        with engine.connect() as conn:
            result = pd.read_sql(text(sql_query), conn)
        
        # Step C: Summarize Answer
        summary_prompt = f"""
        User asked: "{question}"
        SQL Query used: "{sql_query}"
        Data Result: 
        {result.to_string(index=False)}
        
        Provide a concise, human-friendly answer summarizing this data. 
        If the data is a table, just say "Here is the data requested."
        """
        summary_response = model.generate_content(summary_prompt)
        explanation = summary_response.text
        
        return {
            "success": True,
            "data": result,
            "sql": sql_query,
            "answer": explanation
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "sql": sql_query if 'sql_query' in locals() else "Failed to generate"
        }