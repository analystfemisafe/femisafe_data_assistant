import streamlit as st
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI

def page():
    st.title("🔎 Data Query Assistant")
    st.markdown("Ask questions about your sales data in plain English!")

    # ---------------------------------------------------------
    # 1. GET SECRETS (Database & AI)
    # ---------------------------------------------------------
    try:
        # Connect to NEON (Cloud) instead of Localhost
        db_url = st.secrets["postgres"]["url"]
    except KeyError:
        st.error("❌ Database URL not found in secrets.toml")
        return

    # Check for OpenAI Key (Required for the AI to talk)
    openai_api_key = st.secrets.get("OPENAI_API_KEY")
    if not openai_api_key:
        st.warning("⚠️ OpenAI API Key missing! Please add it to .streamlit/secrets.toml")
        # specific input for testing if key is missing
        openai_api_key = st.text_input("Or enter OpenAI API Key here:", type="password")
        if not openai_api_key:
            return

    # ---------------------------------------------------------
    # 2. CONNECT TO NEON DATABASE
    # ---------------------------------------------------------
    try:
        # This connects to your Cloud Database
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