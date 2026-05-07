#!/bin/bash
echo "🖥 UPGRADING DASHBOARD TO v2.1 (HYBRID UI)..."

# 1. Зависимости
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

# 2. Код приложения
cat << 'EOF' > services/dashboard/app.py
import streamlit as st
import pandas as pd
import redis, boto3, os, requests, time, json
from sqlalchemy import create_engine, text
from streamlit_ace import st_ace

st.set_page_config(layout="wide", page_title="AI-OS Command Center", page_icon="🧠")

# --- CSS STYLING ---
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0E1117; border-right: 1px solid #333; }
    .stMetric { background-color: #1E1E1E; padding: 10px; border-radius: 5px; border: 1px solid #444; }
    h1, h2, h3 { color: #00FF99; }
    .status-ok { color: #00FF00; font-weight: bold; }
    .status-err { color: #FF0000; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- AUTH ---
if 'auth' not in st.session_state: st.session_state.auth = False
def check_pw():
    if st.session_state.auth: return True
    pwd = st.sidebar.text_input("🔑 Access Key", type="password")
    if pwd == "admin": 
        st.session_state.auth = True
        st.rerun()
    return False

# --- CONNECTION HELPERS ---
@st.cache_resource
def get_db():
    try:
        url = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:5432/{os.getenv('POSTGRES_DB')}"
        return create_engine(url)
    except: return None

@st.cache_resource
def get_redis():
    try: return redis.from_url(os.getenv("CELERY_BROKER_URL"))
    except: return None

@st.cache_resource
def get_s3():
    try:
        return boto3.client('s3', 
            endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT')}",
            aws_access_key_id=os.getenv('MINIO_ACCESS_KEY'), 
            aws_secret_access_key=os.getenv('MINIO_SECRET_KEY')
        )
    except: return None

# Init connections
pg = get_db()
r = get_redis()
s3 = get_s3()

CORE_URL = "http://core:8000"
LITELLM_URL = "http://litellm:4000"

# --- SIDEBAR (SYSTEM HEALTH) ---
with st.sidebar:
    st.title("🛰 SYSTEM STATUS")
    
    if not check_pw(): st.stop()
    
    st.divider()
    
    # Health Checks
    def check_service(name, url):
        try:
            res = requests.get(url, timeout=0.5)
            if res.status_code < 500: return "✅ ONLINE"
            return f"❌ ERR {res.status_code}"
        except: return "❌ OFFLINE"

    # 1. Core
    core_status = check_service("Brain", f"{CORE_URL}/docs")
    st.markdown(f"**Core API:** {core_status}")

    # 2. LLM Gateway
    llm_status = check_service("LiteLLM", f"{LITELLM_URL}/health")
    st.markdown(f"**AI Model:** {llm_status}")

    # 3. Database
    db_status = "✅ ONLINE"
    try:
        with pg.connect() as conn: conn.execute(text("SELECT 1"))
    except: db_status = "❌ OFFLINE"
    st.markdown(f"**Memory DB:** {db_status}")

    # 4. Redis
    redis_status = "✅ ONLINE"
    q_len = 0
    try: 
        r.ping()
        q_len = r.llen("default")
    except: redis_status = "❌ OFFLINE"
    st.markdown(f"**Nervous Sys:** {redis_status}")
    
    st.divider()
    st.markdown("### 🔥 Load Metrics")
    
    # Redis Flags
    if r:
        paused = r.get("SYSTEM_PAUSED")
        heavy = r.get("STATUS_HEAVY_LOAD")
        
        c1, c2 = st.columns(2)
        c1.metric("Paused", "YES" if paused else "NO")
        c2.metric("Queue", q_len)
        
        if paused:
            st.error("⚠️ GOVERNOR LOCK ACTIVE")
            if st.button("🔓 FORCE UNLOCK"):
                r.delete("SYSTEM_PAUSED")
                st.rerun()

    st.divider()
    if st.button("🔄 Refresh State"): st.cache_data.clear(); st.rerun()

# --- MAIN CONTENT ---

# TABS
t_logs, t_strat, t_dna, t_files, t_skills = st.tabs(["📜 Live Logs", "🎯 Strategy", "🧬 DNA", "📂 Files", "🔧 Skill Editor"])

# === TAB 1: LOGS ===
with t_logs:
    st.header("🧠 Stream of Consciousness")
    col1, col2 = st.columns([1, 5])
    if col1.button("Refresh Logs"): st.rerun()
    
    if pg:
        try:
            df = pd.read_sql("SELECT created_at, agent_role, tool_used, status, duration_ms, input_summary, output_summary FROM run_logs ORDER BY created_at DESC LIMIT 50", pg)
            if not df.empty:
                for i, row in df.iterrows():
                    icon = "🟢" if row['status'] == "success" else "🔴"
                    title = f"{icon} [{row['created_at'].strftime('%H:%M:%S')}] **{row['agent_role']}** → `{row['tool_used']}`"
                    with st.expander(title):
                        st.caption(f"Duration: {row['duration_ms']:.0f}ms")
                        st.code(f"INPUT: {row['input_summary']}")
                        st.code(f"OUTPUT: {row['output_summary']}")
            else:
                st.info("System is idle. No logs yet.")
        except: st.warning("Logs table not found.")

# === TAB 2: STRATEGY ===
with t_strat:
    st.header("Project Management")
    
    # Manual Input
    with st.expander("⚡ Rapid Command"):
        cmd = st.text_input("Enter command for Supervisor:")
        if st.button("Send Command"):
            try:
                requests.post(f"{CORE_URL}/chat", json={"session_id":"admin", "content":cmd})
                st.toast("Command Sent!")
            except: st.error("Failed to send.")

    if pg:
        try:
            df = pd.read_sql("SELECT * FROM goals ORDER BY created_at DESC", pg)
            if not df.empty:
                roots = df[df['parent_id'].isnull()]
                for i, root in roots.iterrows():
                    prog = float(root['progress'] or 0.0)
                    with st.expander(f"{root['title']} ({prog*100:.0f}%)"):
                        st.write(root['description'])
                        c1, c2 = st.columns(2)
                        if c1.button("▶️ Execute", key=f"ex_{root['id']}"):
                            requests.post(f"{CORE_URL}/chat", json={"session_id":"admin", "content":f"Work on: {root['title']}"})
                            st.toast("Agent activated.")
                        
                        kids = df[df['parent_id'] == root['id']]
                        if not kids.empty: st.dataframe(kids[['title', 'status', 'progress']])
            else:
                st.info("No active goals.")
        except: pass

# === TAB 3: DNA ===
with t_dna:
    st.header("Agent Personalities")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM system_prompts", pg)
            if not df.empty:
                role = st.selectbox("Select Agent", df['key'])
                val = df[df['key']==role]['content'].values[0]
                new_val = st.text_area("System Prompt", val, height=400)
                if st.button("Save DNA"):
                    with pg.begin() as conn:
                        conn.execute(text("UPDATE system_prompts SET content = :c WHERE key = :k"), {"c": new_val, "k": role})
                    st.success("DNA Updated!")
        except: pass

# === TAB 4: FILES ===
with t_files:
    if s3:
        try:
            buckets = [b['Name'] for b in s3.list_buckets().get('Buckets', [])]
            bn = st.selectbox("Bucket", buckets)
            if bn:
                objs = s3.list_objects_v2(Bucket=bn).get('Contents', [])
                if objs:
                    data = [{"File": x['Key'], "Size": f"{x['Size']/1024:.1f} KB"} for x in objs]
                    st.dataframe(pd.DataFrame(data), use_container_width=True)
                else: st.info("Empty bucket.")
        except: st.warning("MinIO connecting...")

# === TAB 5: SKILLS ===
with t_skills:
    st.header("Code Editor")
    d = "/app/skills"
    if os.path.exists(d):
        files = [f for f in os.listdir(d) if f.endswith(".py")]
        if files:
            f = st.selectbox("File", files)
            if f:
                path = f"{d}/{f}"
                with open(path, "r") as fl: c = fl.read()
                nc = st_ace(c, language="python", theme="monokai", height=600)
                if st.button("Save Code"):
                    with open(path, "w") as fl: fl.write(nc)
                    st.success("Saved!")
        else: st.info("No skills yet.")
EOF

echo "✅ DASHBOARD v2.1 INSTALLED."
echo "👉 Restarting dashboard container..."
docker compose up -d --build --force-recreate dashboard
