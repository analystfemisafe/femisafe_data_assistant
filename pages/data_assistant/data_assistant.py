import os
import streamlit as st
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI

def page():
    st.title("🔎 Data Query Assistant")
    st.markdown("Ask questions about your sales data in plain English!")

    # ---------------------------------------------------------
    # 1. UNIVERSAL SECRET LOADER (Database & AI Key)
    # ---------------------------------------------------------
    try:
        # Try loading from Streamlit secrets (Local Laptop)
        db_url = st.secrets["postgres"]["url"]
        openai_api_key = st.secrets.get("OPENAI_API_KEY")
    except (FileNotFoundError, KeyError):
        # If that fails, load from Render Environment Variables
        db_url = os.environ.get("DATABASE_URL")
        openai_api_key = os.environ.get("OPENAI_API_KEY")

    # Error handling if secrets are missing
    if not db_url:
        st.error("❌ Database URL is missing. Check your Render Environment Variables (DATABASE_URL).")
        st.stop()
        
    if not openai_api_key:
        st.warning("⚠️ OpenAI API Key is missing.")
        # Optional: Allow manual entry if key is missing in env vars
        openai_api_key = st.text_input("Enter OpenAI API Key manually:", type="password")
        if not openai_api_key:
            st.info("Please enter a key to continue.")
            return

    # ---------------------------------------------------------
    # 2. CONNECT TO DATABASE
    # ---------------------------------------------------------
    try:
        db = SQLDatabase.from_uri(db_url)
    except Exception as e:
        st.error(f"⚠️ Database Connection Failed: {e}")
        return

    # ---------------------------------------------------------
    # 3. SETUP AI AGENT
    # ---------------------------------------------------------
    try:
        llm = ChatOpenAI(
            temperature=0, 
            model="gpt-3.5-turbo", 
            openai_api_key=openai_api_key
        )
        
        agent_executor = create_sql_agent(
            llm=llm,
            db=db,
            agent_type="openai-tools",
            verbose=True
        )
    except Exception as e:
        st.error(f"❌ Error setting up AI Agent: {e}")
        return

    # ---------------------------------------------------------
    # 4. CHAT INTERFACE
    # ---------------------------------------------------------
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ex: 'What is the total revenue from Amazon?'"):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = agent_executor.run(prompt)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"Error: {e}")