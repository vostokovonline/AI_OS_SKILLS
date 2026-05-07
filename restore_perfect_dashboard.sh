#!/bin/bash
echo "💎 RESTORING ULTIMATE DASHBOARD (Hybrid v5.0)..."

# 1. ЗАВИСИМОСТИ
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

# 2. КОД ПРИЛОЖЕНИЯ (Полный фарш)
cat << 'EOF' > services/dashboard/app.py
import streamlit as st
import pandas as pd
import redis, boto3, os, requests, docker
from sqlalchemy import create_engine, text
from streamlit_ace import st_ace
import plotly.express as px

st.set_page_config(layout="wide", page_title="AI-OS Command Node", page_icon="🧿")

# --- CSS STYLES ---
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0E1117; border-right: 1px solid #333; }
    .status-box { padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid #333; background: #191919; }
    .online { color: #00FF00; font-weight: bold; }
    .offline { color: #FF0000; font-weight: bold; }
    .paused { color: #FFAA00; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- AUTH ---
if 'auth' not in st.session_state: st.session_state.auth = False
def check_pw():
    if st.session_state.auth: return True
    if st.sidebar.text_input("🔑 Access Code", type="password") == "admin":
        st.session_state.auth = True
        st.rerun()
    return False

# --- CONNECTIONS ---
@st.cache_resource
def get_conns():
    conns = {}
    
    # 1. Docker
    try: conns['docker'] = docker.from_env()
    except: conns['docker'] = None

    # 2. Postgres
    try:
        user = os.getenv('POSTGRES_USER', 'ns_admin')
        pwd = os.getenv('POSTGRES_PASSWORD', 'ns_secure_pass')
        host = "ns_postgres" # Hardcoded internal
        db = os.getenv('POSTGRES_DB', 'ns_core_db')
        conns['pg'] = create_engine(f"postgresql://{user}:{pwd}@{host}:5432/{db}")
    except: conns['pg'] = None

    # 3. Redis
    try: conns['redis'] = redis.from_url("redis://ns_redis:6379/0")
    except: conns['redis'] = None

    # 4. S3
    try:
        conns['s3'] = boto3.client('s3', endpoint_url="http://ns_minio:9000", aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin")
    except: conns['s3'] = None
    
    return conns

c = get_conns()
CORE_URL = "http://ns_core:8000"
LITELLM_URL = "http://ns_litellm:4000"

# --- SIDEBAR (STATUS PANEL) ---
with st.sidebar:
    st.title("🛰 SYSTEM STATUS")
    if not check_pw(): st.stop()
    
    st.divider()
    
    # Ping Services
    def ping(name, url):
        try:
            return "🟢 ONLINE" if requests.get(url, timeout=0.5).status_code < 500 else "🔴 ERROR"
        except: return "🔴 OFFLINE"

    st.markdown(f"**Brain (Core):** {ping('Core', f'{CORE_URL}/docs')}")
    st.markdown(f"**LLM Gateway:** {ping('LLM', f'{LITELLM_URL}/health')}")
    
    # Docker Status
    if c['docker']:
        try:
            running = len([x for x in c['docker'].containers.list() if 'ns_' in x.name])
            st.markdown(f"**Containers:** 🟢 {running} Active")
        except: st.markdown("**Containers:** 🔴 Socket Error")
    
    # Redis Governor
    if c['redis']:
        try:
            paused = c['redis'].get("SYSTEM_PAUSED")
            status = "🟡 PAUSED" if paused else "🟢 RUNNING"
            st.markdown(f"**Governor:** {status}")
            
            if paused:
                if st.button("▶️ RESUME SYSTEM"):
                    c['redis'].delete("SYSTEM_PAUSED")
                    st.rerun()
            else:
                if st.button("⏸️ PAUSE SYSTEM"):
                    c['redis'].set("SYSTEM_PAUSED", "1")
                    st.rerun()
            
            q_len = c['redis'].llen("default")
            st.metric("Task Queue", q_len)
        except: st.error("Redis Error")

    st.divider()
    if st.button("♻️ Refresh All"): st.cache_resource.clear(); st.rerun()

# --- MAIN UI ---
tabs = st.tabs(["💬 Chat", "🎯 Strategy", "📜 Logs", "🧬 Skills", "💰 Treasury", "📂 Files", "🚦 Docker"])

# === 1. CHAT ===
with tabs[0]:
    st.subheader("Neural Interface")
    if "messages" not in st.session_state: st.session_state.messages = []
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("Command the OS..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    res = requests.post(f"{CORE_URL}/chat", json={"session_id": "dash", "content": prompt})
                    reply = res.json().get("content", "Error")
                except Exception as e: reply = f"Connection Failed: {e}"
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

# === 2. STRATEGY (V3 Logic) ===
with tabs[1]:
    st.subheader("Project Management")
    if c['pg']:
        try:
            df = pd.read_sql("SELECT * FROM goals ORDER BY created_at DESC", c['pg'])
            if not df.empty:
                roots = df[df['parent_id'].isnull()]
                for i, root in roots.iterrows():
                    prog = float(root['progress'] or 0.0)
                    with st.expander(f"🚩 {root['title']} ({prog*100:.0f}%) - {root['status']}"):
                        st.write(root['description'])
                        
                        # Controls
                        col1, col2 = st.columns(2)
                        if col1.button("⚡ Execute", key=f"ex_{root['id']}"):
                            requests.post(f"{CORE_URL}/chat", json={"session_id":"admin", "content":f"Work on goal: {root['title']}"})
                            st.toast("Agent dispatched!")
                        
                        # Subtasks
                        kids = df[df['parent_id'] == root['id']]
                        if not kids.empty:
                            st.dataframe(kids[['title', 'status', 'progress']], use_container_width=True)
            else: st.info("No active projects.")
        except: st.warning("Database not ready.")

# === 3. LOGS ===
with tabs[2]:
    col1, col2 = st.columns([5, 1])
    col2.button("🔄", on_click=st.rerun)
    if c['pg']:
        try:
            df = pd.read_sql("SELECT created_at, agent_role, tool_used, status, output_summary FROM run_logs ORDER BY created_at DESC LIMIT 50", c['pg'])
            for i, row in df.iterrows():
                color = "🟢" if row['status']=="success" else "🔴"
                with st.expander(f"{color} {row['created_at'].strftime('%H:%M:%S')} | {row['agent_role']} -> {row['tool_used']}"):
                    st.code(row['output_summary'])
        except: pass

# === 4. SKILLS (IDE) ===
with tabs[3]:
    st.subheader("Skill Editor")
    d = "/app/skills"
    if os.path.exists(d):
        files = [x for x in os.listdir(d) if x.endswith(".py")]
        if files:
            f = st.selectbox("File", files)
            path = f"{d}/{f}"
            with open(path, "r") as fl: content = fl.read()
            
            new_code = st_ace(value=content, language="python", theme="monokai", height=600)
            if st.button("💾 Save Changes"):
                with open(path, "w") as fl: fl.write(new_code)
                st.success("File saved.")
        else: st.info("No skills generated yet.")
    else: st.error("Volume not mounted.")

# === 5. TREASURY ===
with tabs[4]:
    st.subheader("Resource Usage")
    if c['pg']:
        try:
            df = pd.read_sql("SELECT tool_used, COUNT(*) as count FROM run_logs GROUP BY tool_used", c['pg'])
            if not df.empty:
                st.bar_chart(df.set_index("tool_used"))
        except: pass

# === 6. FILES ===
with tabs[5]:
    if c['s3']:
        try:
            buckets = c['s3'].list_buckets().get('Buckets', [])
            b = st.selectbox("Bucket", [x['Name'] for x in buckets])
            if b:
                objs = c['s3'].list_objects_v2(Bucket=b).get('Contents', [])
                if objs:
                    st.dataframe(pd.DataFrame([{"File":x['Key'], "Size":x['Size']} for x in objs]))
        except: pass

# === 7. DOCKER MONITOR ===
with tabs[6]:
    st.subheader("Container Health")
    if c['docker']:
        try:
            stats = []
            for cont in c['docker'].containers.list():
                if "ns_" in cont.name:
                    stats.append({"Name": cont.name, "Status": cont.status, "Image": cont.image.tags[0] if cont.image.tags else "local"})
            st.dataframe(pd.DataFrame(stats))
        except: st.error("Socket Error")
EOF

echo "✅ DASHBOARD RESTORED TO PERFECT STATE."
echo "👉 Rebuilding..."
docker compose up -d --build --force-recreate dashboard
