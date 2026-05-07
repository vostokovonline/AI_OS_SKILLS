#!/bin/bash
echo "🔌 FIXING DASHBOARD DB CONNECTION..."

cat << 'EOF' > services/dashboard/app.py
import streamlit as st
import pandas as pd
import redis, boto3, os, requests
from sqlalchemy import create_engine, text
from streamlit_ace import st_ace

st.set_page_config(layout="wide", page_title="AI-OS Command Center", page_icon="🧠")

# --- CSS ---
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0E1117; border-right: 1px solid #333; }
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

# --- CONNECTORS ---
@st.cache_resource
def get_db():
    # 1. Получаем учетные данные
    user = os.getenv('POSTGRES_USER', 'ns_admin')
    pwd = os.getenv('POSTGRES_PASSWORD', 'ns_secure_pass')
    db_name = os.getenv('POSTGRES_DB', 'ns_core_db')
    
    # 2. ВАЖНО: Жестко задаем имя хоста контейнера
    # Это решает проблему "could not translate host name"
    host = "ns_postgres" 
    
    url = f"postgresql://{user}:{pwd}@{host}:5432/{db_name}"
    return create_engine(url)

@st.cache_resource
def get_redis():
    # Используем имя контейнера ns_redis
    return redis.from_url("redis://ns_redis:6379/0")

@st.cache_resource
def get_s3():
    return boto3.client('s3', 
        endpoint_url="http://ns_minio:9000",
        aws_access_key_id=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'), 
        aws_secret_access_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    )

pg = get_db()
r = get_redis()
s3 = get_s3()

CORE_URL = "http://ns_core:8000"
LITELLM_URL = "http://ns_litellm:4000"

# --- SIDEBAR STATUS ---
with st.sidebar:
    st.title("🛰 SYSTEM STATUS")
    if not check_pw(): st.stop()
    st.divider()

    # DB CHECK
    try:
        with pg.connect() as conn: conn.execute(text("SELECT 1"))
        st.markdown("💾 Memory DB: :green[**ONLINE**]")
    except Exception as e:
        st.markdown("💾 Memory DB: :red[**OFFLINE**]")
        with st.expander("Show DB Error"):
            st.code(str(e)) # Покажем точную ошибку пользователю

    # REDIS CHECK
    try:
        r.ping()
        st.markdown("⚡ Nervous Sys: :green[**ONLINE**]")
    except:
        st.markdown("⚡ Nervous Sys: :red[**OFFLINE**]")

    # API CHECK
    try:
        if requests.get(f"{CORE_URL}/docs", timeout=1).status_code == 200:
            st.markdown("🧠 Core Brain: :green[**ONLINE**]")
        else: st.markdown("🧠 Core Brain: :orange[**WARN**]")
    except: st.markdown("🧠 Core Brain: :red[**OFFLINE**]")
    
    st.divider()
    if r:
        paused = r.get("SYSTEM_PAUSED")
        st.metric("System Paused", "YES" if paused else "NO")
        if st.button("Toggle Pause"):
            if paused: r.delete("SYSTEM_PAUSED")
            else: r.set("SYSTEM_PAUSED", "1")
            st.rerun()

# --- TABS ---
t_logs, t_strat, t_dna, t_files, t_skills = st.tabs(["📜 Logs", "🎯 Strategy", "🧬 DNA", "📂 Files", "🔧 Skills"])

with t_logs:
    st.header("Live Logs")
    if st.button("Refresh"): st.rerun()
    if pg:
        try:
            df = pd.read_sql("SELECT created_at, agent_role, tool_used, status, output_summary FROM run_logs ORDER BY created_at DESC LIMIT 50", pg)
            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else: st.info("No logs found.")
        except: st.warning("Logs table not found.")

with t_strat:
    st.header("Strategy")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM goals", pg)
            if not df.empty:
                for i, row in df.iterrows():
                    st.success(f"{row['title']} ({row['status']})")
            else: st.info("No goals.")
        except: st.warning("Goals table not found.")

with t_dna:
    st.header("DNA Editor")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM system_prompts", pg)
            if not df.empty:
                role = st.selectbox("Role", df['key'])
                val = df[df['key']==role]['content'].values[0]
                st.text_area("Prompt", val, height=200)
        except: pass

with t_files:
    if s3:
        try:
            b = s3.list_buckets().get('Buckets', [])
            if b:
                bn = st.selectbox("Bucket", [x['Name'] for x in b])
                o = s3.list_objects_v2(Bucket=bn).get('Contents', [])
                if o: st.write(o)
        except: st.error("MinIO Error")

with t_skills:
    d = "/app/skills"
    if os.path.exists(d):
        files = os.listdir(d)
        st.write(files)
EOF

echo "✅ DASHBOARD PATCHED."
echo "👉 Rebuilding..."
docker compose up -d --build --force-recreate dashboard
