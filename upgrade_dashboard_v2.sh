#!/bin/bash
echo "🖥 UPGRADING DASHBOARD TO v2.0 (MISSION CONTROL)..."

# 1. Обновляем зависимости
cat << 'EOF' > services/dashboard/requirements.txt
streamlit
pandas
neo4j
redis
boto3
plotly
streamlit-agraph
streamlit-ace
python-dotenv
sqlalchemy
psycopg2-binary
requests
EOF

# 2. Обновляем код приложения
cat << 'EOF' > services/dashboard/app.py
import streamlit as st
import pandas as pd
import redis, boto3, os, requests, time, json
from sqlalchemy import create_engine, text
from datetime import datetime

st.set_page_config(layout="wide", page_title="AI-OS Mission Control", page_icon="🎛️")

# --- CSS HACKS ---
st.markdown("""
<style>
    .stMetric { background-color: #0E1117; padding: 10px; border-radius: 5px; border: 1px solid #333; }
    .stSuccess { color: #00FF00 !important; }
    .stError { color: #FF0000 !important; }
</style>
""", unsafe_allow_html=True)

# --- CONNECTIONS ---
@st.cache_resource
def get_db_engine():
    try:
        url = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:5432/{os.getenv('POSTGRES_DB')}"
        return create_engine(url)
    except: return None

@st.cache_resource
def get_redis():
    try: return redis.from_url(os.getenv("CELERY_BROKER_URL"))
    except: return None

pg = get_db_engine()
r = get_redis()
CORE_URL = "http://core:8000"
LITELLM_URL = "http://litellm:4000"

# --- SIDEBAR STATUS ---
with st.sidebar:
    st.header("🔌 Connectivity")
    
    # 1. DB Check
    if pg:
        try:
            with pg.connect() as conn: conn.execute(text("SELECT 1"))
            st.success("Postgres: ONLINE")
        except: st.error("Postgres: OFFLINE")
    else: st.error("Postgres: CONFIG ERROR")

    # 2. Redis Check
    if r:
        try:
            r.ping()
            st.success("Redis: ONLINE")
            q_len = r.llen("default")
            st.metric("Queue Size", q_len)
        except: st.error("Redis: OFFLINE")
    
    # 3. Core Check
    try:
        res = requests.get(f"{CORE_URL}/docs", timeout=1)
        if res.status_code == 200: st.success("Core API: ONLINE")
        else: st.warning(f"Core API: {res.status_code}")
    except: st.error("Core API: UNREACHABLE")

    # 4. LiteLLM Check
    try:
        res = requests.get(f"{LITELLM_URL}/health", timeout=1)
        if res.status_code == 200: st.success("LiteLLM: ONLINE")
        else: st.error("LiteLLM: ERROR")
    except: st.error("LiteLLM: UNREACHABLE")
    
    if st.button("♻️ Force Refresh"):
        st.cache_data.clear()
        st.rerun()

# --- TABS ---
tabs = st.tabs(["📜 Live Logs", "🎯 Strategy & Goals", "🛠 Manual Override", "🧠 Models & DNA", "📂 Files"])

# === TAB 1: LIVE LOGS (DIAGNOSTICS) ===
with tabs[0]:
    st.subheader("System Activity (RunLogs)")
    
    if pg:
        col1, col2 = st.columns([1, 4])
        with col1:
            limit = st.select_slider("Rows", options=[20, 50, 100, 500])
        
        # Auto-refresh logic could go here
        
        try:
            query = f"SELECT created_at, agent_role, tool_used, status, duration_ms, output_summary FROM run_logs ORDER BY created_at DESC LIMIT {limit}"
            logs_df = pd.read_sql(query, pg)
            
            if not logs_df.empty:
                # Color code status
                def color_status(val):
                    color = '#ff4b4b' if val != 'success' else '#00cc96'
                    return f'color: {color}'

                st.dataframe(
                    logs_df.style.map(color_status, subset=['status']),
                    use_container_width=True,
                    height=500
                )
            else:
                st.info("Log table is empty. No tools executed yet.")
        except Exception as e:
            st.error(f"Error fetching logs: {e}")

# === TAB 2: STRATEGY (GOAL MANAGEMENT) ===
with tabs[2]: # Swapped for manual override first? No, keep order
    st.subheader("Interactive Goal Tree")
    
    if pg:
        # 1. Manual Creation Form
        with st.expander("➕ Create New Goal Manually", expanded=False):
            with st.form("new_goal"):
                new_title = st.text_input("Goal Title")
                new_desc = st.text_area("Description")
                submitted = st.form_submit_button("Create Goal")
                if submitted and new_title:
                    try:
                        with pg.begin() as conn:
                            import uuid
                            uid = uuid.uuid4()
                            conn.execute(text("INSERT INTO goals (id, title, description, status, progress, created_at) VALUES (:id, :t, :d, 'active', 0.0, NOW())"), {"id": uid, "t": new_title, "d": new_desc})
                        st.success("Goal created directly in DB!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"DB Error: {e}")

        # 2. View Goals
        try:
            goals_df = pd.read_sql("SELECT * FROM goals ORDER BY created_at DESC", pg)
            if not goals_df.empty:
                for i, row in goals_df.iterrows():
                    col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
                    with col1:
                        st.markdown(f"### {row['title']}")
                        st.caption(row['description'])
                    with col2:
                        st.progress(float(row['progress'] or 0.0))
                    with col3:
                        st.badge(row['status'])
                    with col4:
                        if st.button("⚡ Run", key=f"run_{row['id']}"):
                            try:
                                requests.post(f"{CORE_URL}/chat", json={"session_id":"admin", "content":f"Execute goal: {row['title']}"})
                                st.toast("Task sent to agent!")
                            except: st.error("Failed to trigger agent")
                        if st.button("🗑️ Del", key=f"del_{row['id']}"):
                            with pg.begin() as conn:
                                conn.execute(text("DELETE FROM goals WHERE id = :id"), {"id": row['id']})
                            st.rerun()
                    st.divider()
            else:
                st.info("No goals found.")
        except Exception as e:
            st.error(f"Error reading goals: {e}")

# === TAB 3: MANUAL OVERRIDE (DEBUG) ===
with tabs[2]:
    st.subheader("Direct Interface")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Core Chat API**")
        user_input = st.text_input("Send command to Core directly:")
        if st.button("Send"):
            if user_input:
                try:
                    res = requests.post(f"{CORE_URL}/chat", json={"session_id": "dashboard", "content": user_input})
                    st.write(res.json())
                except Exception as e:
                    st.error(str(e))
    
    with col2:
        st.markdown("**Redis Queue Injector**")
        if st.button("Inject Ping Task"):
            # This requires celery access, simplified here
            st.warning("Use Core Chat API for now.")

# === TAB 4: MODELS & DNA ===
with tabs[3]:
    st.subheader("Brain Configuration")
    
    # Check what models LiteLLM actually sees
    st.markdown("#### Available Models (LiteLLM)")
    if st.button("Check Models"):
        try:
            res = requests.get(f"{LITELLM_URL}/v1/models", headers={"Authorization": "Bearer sk-1234"})
            st.json(res.json())
        except Exception as e:
            st.error(f"LiteLLM Error: {e}")

    st.markdown("#### System DNA (Prompts)")
    if pg:
        prompts = pd.read_sql("SELECT * FROM system_prompts", pg)
        st.dataframe(prompts, use_container_width=True)

# === TAB 5: FILES ===
with tabs[4]:
    st.subheader("File System")
    # ... (Standard S3 listing code) ...
    st.info("MinIO Browser available at http://localhost:9001")
EOF

echo "✅ DASHBOARD v2.0 INSTALLED."
echo "👉 Restarting dashboard container..."
docker compose restart dashboard
