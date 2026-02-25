import streamlit as st
import pandas as pd
import plotly.express as px
import json
from google import genai
import os
from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_exponential

# Import Centralized Engine
try:
    from utils.db_manager import get_db_engine
except ImportError:
    from sqlalchemy import create_engine
    @st.cache_resource
    def get_db_engine():
        return create_engine(os.environ.get("DATABASE_URL"))

# ==========================================
# 🛡️ AI CALL & DEBUG CATCHER
# ==========================================
def send_message_to_gemini(client, prompt):
    try:
        # 🛑 FIX: Switched to the universally stable 2.0 model
        return client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
    except Exception as e:
        # 🛑 FIX: If it fails, print the EXACT reason to the Streamlit screen
        st.error(f"🔍 Detailed Google Error: {str(e)}")
        raise e
# ==========================================
# 🚀 DATA LOADER
# ==========================================
@st.cache_data(ttl=3600)
def get_assistant_data():
    engine = get_db_engine()
    if not engine: return None, "No database connection available."
    
    try:
        with engine.connect() as conn:
            query = text("SELECT month, channels, products, revenue, sku_units FROM femisafe_sales")
            df = pd.read_sql(query, conn)
            
        if df.empty: return None, "No data available in the table."

        df.columns = df.columns.str.strip().str.lower()

        # Clean numbers
        if 'revenue' in df.columns:
            df['revenue'] = pd.to_numeric(df['revenue'].astype(str).str.replace(r'[₹,]', '', regex=True), errors='coerce').fillna(0)
        if 'sku_units' in df.columns:
            df['sku_units'] = pd.to_numeric(df['sku_units'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            df.rename(columns={'sku_units': 'units'}, inplace=True)

        # Aggregate data
        group_cols = [col for col in ['month', 'channels', 'products'] if col in df.columns]
        sum_cols = [col for col in ['revenue', 'units'] if col in df.columns]
        
        df_grouped = df.groupby(group_cols, as_index=False)[sum_cols].sum()
        
        if 'revenue' in df_grouped.columns:
            df_grouped = df_grouped.sort_values(by='revenue', ascending=False)
            
        return df_grouped, df_grouped.to_csv(index=False)
            
    except Exception as e:
        return None, f"Database error: {e}"

# ==========================================
# 🎨 CHART RENDERER
# ==========================================
def render_chart(df, chart_config, chart_key):
    if df is None or df.empty:
        st.warning("No data available to draw this chart.")
        return

    c_type = chart_config.get("chart_type", "bar")
    x_axis = chart_config.get("x_axis", "channels")
    y_axis = chart_config.get("y_axis", "revenue")
    title = chart_config.get("title", f"{y_axis.title()} by {x_axis.title()}")

    if x_axis not in df.columns or y_axis not in df.columns:
        st.error(f"Cannot create chart: Missing columns '{x_axis}' or '{y_axis}'.")
        return

    if c_type == "line":
        fig = px.line(df, x=x_axis, y=y_axis, title=title, markers=True, template="plotly_dark")
    else:
        fig = px.bar(df, x=x_axis, y=y_axis, title=title, color=x_axis, template="plotly_dark")
        
    st.plotly_chart(fig, use_container_width=True, key=chart_key)

# ==========================================
# 🤖 CHATBOT PAGE UI
# ==========================================
def page():
    st.markdown("### ✨ FemiSafe AI Data Assistant")
    st.caption("Powered by Gemini 2.5 Flash - Now with Visual Analytics!")

    try:
        api_key = st.secrets["general"]["GEMINI_API_KEY"]
    except:
        api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        st.error("⚠️ Please add GEMINI_API_KEY to your settings.")
        return

    # Initialize Gemini Client
    if "gemini_client" not in st.session_state:
        st.session_state.gemini_client = genai.Client(api_key=api_key)
        
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Load Data
    df_grouped, data_context = get_assistant_data()

    # Display Chat History
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            if message["is_chart"]:
                render_chart(df_grouped, message["content"], chart_key=f"chart_history_{i}")
            else:
                st.markdown(message["content"])

    # Handle User Input
    user_prompt = st.chat_input("Ask me for a chart! (e.g., Draw a bar chart of revenue by product)")
    
    if user_prompt:
        st.chat_message("user").markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt, "is_chart": False})

        # Bundle up the chat history so the AI remembers the conversation
        history_text = "\n".join([
            f"{'User' if m['role']=='user' else 'AI'}: {m['content'] if not m['is_chart'] else '[Generated Chart]'}" 
            for m in st.session_state.messages[-4:-1]  # Send the last 3 messages
        ])

        # The Indestructible Prompt
        full_prompt = f"""
        You are an expert Data Analyst for FemiSafe. 
        
        LATEST DATA:
        {data_context}
        
        RECENT CHAT HISTORY:
        {history_text}
        
        RULES:
        1. If the user asks a normal question, answer using concise text.
        2. IF the user asks to see a chart or graph, DO NOT write any text. You MUST reply ONLY with a raw JSON object matching this exact structure:
        {{
            "is_chart": true,
            "chart_type": "bar", 
            "x_axis": "month",
            "y_axis": "revenue",
            "title": "Revenue by Month"
        }}
        Valid chart_type options: "bar", "line".
        Valid x_axis options: "channels", "products", "month".
        Valid y_axis options: "revenue", "units".
        Return ONLY the JSON, without markdown blocks.
        
        USER QUESTION: {user_prompt}
        """

        with st.chat_message("assistant"):
            with st.spinner("Analyzing data..."):
                try:
                    # Send the request directly to the client
                    response = send_message_to_gemini(st.session_state.gemini_client, full_prompt)
                    raw_text = response.text.strip()
                    
                    try:
                        clean_json_str = raw_text.replace("```json", "").replace("```", "").strip()
                        chart_config = json.loads(clean_json_str)
                        
                        if chart_config.get("is_chart"):
                            new_key = f"chart_new_{len(st.session_state.messages)}"
                            render_chart(df_grouped, chart_config, chart_key=new_key)
                            
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": chart_config, 
                                "is_chart": True
                            })
                        else:
                            raise ValueError("Not a chart JSON")
                            
                    except (json.JSONDecodeError, ValueError):
                        st.markdown(raw_text)
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": raw_text, 
                            "is_chart": False
                        })
                        
                except Exception as e:
                    st.error(f"⚠️ Server issue: {e}")