import os
import streamlit as st
from sqlalchemy import create_engine

# =========================================================
# 🔌 CENTRAL DATABASE MANAGER
# Handles connection pooling to save compute hours
# =========================================================

@st.cache_resource
def get_db_engine():
    """
    Creates a single database engine that is reused across the entire app.
    This prevents opening new connections on every button click.
    """
    try:
        # 🛑 COMPLETELY REMOVED st.secrets TO FIX RAILWAY ERROR
        # Exclusively use the Cloud Environment Variable
        db_url = os.environ.get("DATABASE_URL")
        
        if not db_url:
            st.error("❌ Database URL not found. Check Railway Environment Variables.")
            return None

        # Create engine with connection pooling settings
        engine = create_engine(
            db_url,
            pool_size=5,        
            max_overflow=10,    
            pool_timeout=30,    
            pool_recycle=1800,
            # ⬇️ CRITICAL FIX FOR POOLED TRANSACTION MODE
            # This disables prepared statements, which prevents errors with the pooler.
            connect_args={"prepare_threshold": None} 
        )
        return engine

    except Exception as e:
        st.error(f"⚠️ Failed to create DB Engine: {e}")
        return None