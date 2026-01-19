import streamlit as st
import pandas as pd
import psycopg2
from sqlalchemy import create_engine

def get_engine():
    """
    Creates a SQLAlchemy engine using credentials from secrets.toml.
    Used for writing data (to_sql).
    """
    try:
        # Looks for the [postgres] section in .streamlit/secrets.toml
        db_config = st.secrets["postgres"]
        return create_engine(db_config["url"])
    except Exception as e:
        st.error(f"❌ Database Engine Error: {e}")
        return None

def get_data(query):
    """
    Connects to Neon DB and fetches data using a raw SQL query.
    Used for reading data (read_sql).
    """
    try:
        # Looks for the [postgres] section in .streamlit/secrets.toml
        db_config = st.secrets["postgres"]
        
        # Connect using the URL
        conn = psycopg2.connect(db_config["url"])
        
        # Execute Query
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
        
    except Exception as e:
        # If the query fails, return an empty DataFrame so the app doesn't crash
        st.error(f"❌ Database Query Error: {e}")
        return pd.DataFrame()