#!/bin/bash
echo "🛠 FIXING DASHBOARD MINIO CONNECTION..."

# Перезаписываем app.py с безопасной логикой подключения
cat << 'EOF' > services/dashboard/app.py
import streamlit as st
import pandas as pd
import redis, boto3, os, requests
from sqlalchemy import create_engine, text
from streamlit_ace import st_ace

st.set_page_config(layout="wide", page_title="AI-OS Mission Control", page_icon="🧠")

# --- AUTH ---
if 'auth' not in st.session_state: st.session_state.auth = False
def check_pw():
    if st.session_state.auth: return True
    if st.text_input("Password", type="password") == "admin":
        st.session_state.auth = True
        st.rerun()
    return False
if not check_pw(): st.stop()

# --- CONNECTIONS ---

# 1. Postgres
try:
    pg_user = os.getenv('POSTGRES_USER', 'ns_admin')
    pg_pass = os.getenv('POSTGRES_PASSWORD', 'ns_secure_pass')
    pg_db = os.getenv('POSTGRES_DB', 'ns_core_db')
    pg_host = os.getenv('POSTGRES_HOST')
    # Fallback to service name 'postgres' if env is missing
    if not pg_host or pg_host == "None": pg_host = "postgres" 

    DB_URL = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:5432/{pg_db}"
    pg = create_engine(DB_URL)
    with pg.connect() as conn: pass
except Exception as e:
    pg = None
    st.sidebar.error(f"DB Error: {e}")

# 2. Redis
try:
    # Use service name 'redis' instead of container name 'ns_redis' just in case
    redis_host = os.getenv('REDIS_HOST', 'redis')
    r = redis.from_url(f"redis://{redis_host}:6379/0")
    r.ping()
except:
    r = None
    st.sidebar.warning("Redis disconnected")

# 3. MinIO (FIXED)
try:
    # Get from env OR fallback to 'minio:9000' (Service name, NO UNDERSCORES)
    minio_url = os.getenv('MINIO_ENDPOINT', 'minio:9000')
    
    # Ensure protocol schema
    if not minio_url.startswith("http"):
        minio_url = f"http://{minio_url}"
        
    s3 = boto3.client('s3', 
        endpoint_url=minio_url,
        aws_access_key_id=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'), 
        aws_secret_access_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    )
    # Check connection
    s3.list_buckets()
except Exception as e:
    s3 = None
    # Don't show error in sidebar to avoid clutter, will show in tab
    print(f"MinIO connection failed: {e}")

CORE_URL = os.getenv("CORE_URL", "http://core:8000")

# --- UI ---
st.title("🧠 Technocratic OS")

t1, t2, t3, t4, t5 = st.tabs(["📜 Logs", "🎯 Strategy", "🧬 DNA", "🚦 Status", "📂 Files"])

# TAB 1: LOGS
with t1:
    st.header("Live Telemetry")
    if st.button("Refresh"): st.rerun()
    if pg:
        try:
            df = pd.read_sql("SELECT created_at, agent_role, tool_used, status, output_summary FROM run_logs ORDER BY created_at DESC LIMIT 50", pg)
            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else: st.info("No logs found.")
        except: st.warning("Logs table missing.")

# TAB 2: STRATEGY
with t2:
    st.header("Active Projects")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM goals", pg)
            if not df.empty:
                for i, row in df.iterrows():
                    st.success(f"{row['title']} ({row['status']})")
            else: st.info("No active goals.")
        except: pass

# TAB 3: DNA
with t3:
    st.header("Agent Persona")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM system_prompts", pg)
            if not df.empty:
                st.dataframe(df)
        except: pass

# TAB 4: STATUS
with t4:
    if r:
        raw = r.get("SYSTEM_PAUSED")
        paused = raw.decode('utf-8')=="1" if raw else False
        st.metric("System Paused", "YES" if paused else "NO")
        if st.button("Toggle Pause"):
            if paused: r.delete("SYSTEM_PAUSED")
            else: r.set("SYSTEM_PAUSED", "1")
            st.rerun()

# TAB 5: FILES
with t5:
    st.header("File Storage")
    if s3:
        try:
            buckets = s3.list_buckets().get('Buckets', [])
            if buckets:
                bn = st.selectbox("Bucket", [x['Name'] for x in buckets])
                if bn:
                    objs = s3.list_objects_v2(Bucket=bn).get('Contents', [])
                    if objs:
                        st.dataframe(pd.DataFrame([{"File":x['Key'], "Size":x['Size']} for x in objs]))
                    else: st.info("Bucket is empty.")
            else: st.warning("No buckets found.")
        except Exception as e: st.error(f"S3 Error: {e}")
    else:
        st.error("MinIO Connection Failed (Check logs)")
EOF

echo "✅ DASHBOARD PATCHED."
echo "👉 Rebuilding..."
docker compose up -d --build --force-recreate dashboard
