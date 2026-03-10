import streamlit as st
import pandas as pd
import psycopg2
from sqlalchemy import create_engine
import os  # 👈 Added os to read Railway variables

def get_engine():
    """
    Creates a SQLAlchemy engine using credentials from Railway Variables.
    Used for writing data (to_sql).
    """
    try:
        # Pulls the database link directly from Railway's secure vault
        db_url = os.environ.get("DATABASE_URL")
        
        if not db_url:
            st.error("❌ DATABASE_URL is not set in Railway variables.")
            return None
            
        return create_engine(db_url)
    except Exception as e:
        st.error(f"❌ Database Engine Error: {e}")
        return None

def get_data(query):
    """
    Connects to Postgres DB and fetches data using a raw SQL query.
    Used for reading data (read_sql).
    """
    try:
        # Pulls the database link directly from Railway's secure vault
        db_url = os.environ.get("DATABASE_URL")
        
        if not db_url:
            st.error("❌ DATABASE_URL is not set in Railway variables.")
            return pd.DataFrame()
        
        # Connect using the URL
        conn = psycopg2.connect(db_url)
        
        # Execute Query
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
        
    except Exception as e:
        # If the query fails, return an empty DataFrame so the app doesn't crash
        st.error(f"❌ Database Query Error: {e}")
        return pd.DataFrame()