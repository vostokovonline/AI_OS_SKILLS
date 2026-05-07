#!/bin/bash
echo "🖥 UPGRADING DASHBOARD TO v4.0 (TREASURY & CHAT)..."

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
docker
graphviz
EOF

cat << 'EOF' > services/dashboard/app.py
import streamlit as st
import pandas as pd
import redis, boto3, os, requests, docker
from sqlalchemy import create_engine, text
from streamlit_ace import st_ace
import plotly.express as px

st.set_page_config(layout="wide", page_title="AI-OS War Room", page_icon="🛡")

# --- CSS ---
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #111; }
    .stMetric { background-color: #222; border: 1px solid #444; }
</style>
""", unsafe_allow_html=True)

# --- AUTH ---
if 'auth' not in st.session_state: st.session_state.auth = False
def check_pw():
    if st.session_state.auth: return True
    if st.sidebar.text_input("🔑 Access Key", type="password") == "admin":
        st.session_state.auth = True
        st.rerun()
    return False
if not check_pw(): st.stop()

# --- CONNECTORS ---
try:
    user = os.getenv('POSTGRES_USER', 'ns_admin')
    pwd = os.getenv('POSTGRES_PASSWORD', 'ns_secure_pass')
    host = "ns_postgres" # Hardcoded internal name
    db = os.getenv('POSTGRES_DB', 'ns_core_db')
    pg = create_engine(f"postgresql://{user}:{pwd}@{host}:5432/{db}")
except: pg = None

try: r = redis.from_url("redis://ns_redis:6379/0")
except: r = None

try: dk = docker.from_env()
except: dk = None

CORE_URL = "http://ns_core:8000"

# --- SIDEBAR ---
with st.sidebar:
    st.header("🛸 System Status")
    
    # Docker Check
    if dk:
        try:
            containers = dk.containers.list()
            running = len([c for c in containers if "ns_" in c.name])
            st.metric("Active Modules", f"{running}/17")
        except Exception as e:
            st.error("Docker Socket Access Denied")
    
    # Queue Check
    if r:
        q = r.llen("default")
        st.metric("Task Queue", q)
        
        paused = r.get("SYSTEM_PAUSED")
        if paused:
            st.error("🛑 SYSTEM PAUSED")
            if st.button("▶️ RESUME"):
                r.delete("SYSTEM_PAUSED")
                st.rerun()
        else:
            st.success("🟢 SYSTEM RUNNING")

# --- TABS ---
t_chat, t_logs, t_strat, t_treasury, t_files = st.tabs(["💬 Direct Link", "📜 Logs", "🎯 Strategy", "💰 Treasury", "📂 Files"])

# === TAB 1: DIRECT CHAT ===
with t_chat:
    st.subheader("Neural Interface")
    
    # Chat History
    if "messages" not in st.session_state: st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Command the OS..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Direct API Call
                    res = requests.post(f"{CORE_URL}/chat", json={"session_id": "dashboard_chat", "content": prompt})
                    response = res.json().get("content", "Error")
                except Exception as e:
                    response = f"Connection Error: {e}"
            
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

# === TAB 2: LOGS (Enhanced) ===
with t_logs:
    st.subheader("Telemetry Stream")
    if st.button("Refresh Logs"): st.rerun()
    if pg:
        df = pd.read_sql("SELECT * FROM run_logs ORDER BY created_at DESC LIMIT 50", pg)
        if not df.empty:
            # Stats
            errs = len(df[df['status']!='success'])
            st.metric("Errors (Last 50)", errs, delta=-errs if errs>0 else 0)
            
            for i, row in df.iterrows():
                icon = "🟢" if row['status']=='success' else "🔴"
                with st.expander(f"{icon} {row['agent_role']} -> {row['tool_used']} ({row['duration_ms']:.0f}ms)"):
                    c1, c2 = st.columns(2)
                    c1.code(row['input_summary'], language="json")
                    c2.code(row['output_summary'])

# === TAB 3: STRATEGY ===
with t_strat:
    st.subheader("Active Goals")
    if pg:
        df = pd.read_sql("SELECT * FROM goals WHERE status='active'", pg)
        if not df.empty:
            for i, row in df.iterrows():
                st.info(f"**{row['title']}**")
                st.caption(row['description'])
                if st.button("Execute Step", key=f"g_{i}"):
                    requests.post(f"{CORE_URL}/chat", json={"session_id":"admin", "content":f"Work on {row['title']}"})
                    st.toast("Agent Deployed")

# === TAB 4: TREASURY (Cost Monitor) ===
with t_treasury:
    st.header("Resource Consumption")
    # Simulation of cost tracking (Real implementation needs LiteLLM logs)
    if pg:
        # Count tool usage
        usage = pd.read_sql("SELECT tool_used, COUNT(*) as count, AVG(duration_ms) as avg_time FROM run_logs GROUP BY tool_used", pg)
        if not usage.empty:
            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("#### Tool Usage Distribution")
                fig = px.pie(usage, values='count', names='tool_used')
                st.plotly_chart(fig, use_container_width=True)
            
            with c2:
                st.markdown("#### Performance (Avg Time ms)")
                st.bar_chart(usage.set_index('tool_used')['avg_time'])

# === TAB 5: FILES ===
with t_files:
    try:
        s3 = boto3.client('s3', endpoint_url="http://ns_minio:9000", aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin")
        buckets = s3.list_buckets()['Buckets']
        bn = st.selectbox("Bucket", [b['Name'] for b in buckets])
        if bn:
            objs = s3.list_objects_v2(Bucket=bn).get('Contents', [])
            if objs:
                st.dataframe(pd.DataFrame([{"File": x['Key'], "Size": x['Size']} for x in objs]))
    except: st.warning("MinIO connecting...")

EOF

echo "✅ DASHBOARD v4.0 (WAR ROOM) INSTALLED."
echo "👉 Rebuilding..."
docker compose up -d --build dashboard
