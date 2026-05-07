#!/bin/bash
# upgrade_2.sh - IMMUNITY (Governor, Telemetry, Dashboard)
echo "🛡 DEPLOYING IMMUNE SYSTEM..."

# 1. TELEMETRY
cat << 'EOF' > services/core/telemetry.py
import time
from database import AsyncSessionLocal
from models import RunLog, ToolStats
from sqlalchemy import select

async def log_action(session_id, agent, tool, input_data, output_data, status, start_time):
    duration = (time.time() - start_time) * 1000
    try:
        async with AsyncSessionLocal() as db:
            log = RunLog(session_id=str(session_id), agent_role=agent, tool_used=tool, input_summary=str(input_data)[:500], output_summary=str(output_data)[:500], status=status, duration_ms=duration)
            db.add(log)
            res = await db.execute(select(ToolStats).where(ToolStats.tool_name == tool))
            stats = res.scalar_one_or_none()
            if not stats:
                stats = ToolStats(tool_name=tool, calls_count=0, errors_count=0, avg_duration_ms=0.0)
                db.add(stats)
            tot = (stats.avg_duration_ms * stats.calls_count) + duration
            stats.calls_count += 1
            stats.avg_duration_ms = tot / stats.calls_count
            if status != "success": 
                stats.errors_count += 1
                stats.last_error = str(output_data)[:200]
            await db.commit()
    except Exception as e: print(f"Telemetry Error: {e}")
EOF

# 2. GOVERNOR
echo "👮 Updating Governor..."
cat << 'EOF' > services/governor/requirements.txt
docker
psutil
redis
httpx
python-dotenv
EOF

cat << 'EOF' > services/governor/main.py
import time, os, docker, psutil, redis, httpx
from datetime import datetime

DOCKER_CLIENT = docker.from_env()
REDIS_CLIENT = redis.from_url(os.getenv("CELERY_BROKER_URL"))
TELEGRAM_URL = os.getenv("TELEGRAM_URL")
CPU_THRESHOLD = int(os.getenv("CPU_THRESHOLD", 90))

def notify(msg):
    try: httpx.post(f"{TELEGRAM_URL}/notify", json={"message": f"🏥 **System Doctor:**\n{msg}"}, timeout=5)
    except: pass

def manage_resources():
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    
    if mem > 90: REDIS_CLIENT.set("STATUS_CRITICAL", "1", ex=60)
    else: REDIS_CLIENT.delete("STATUS_CRITICAL")

    if cpu > CPU_THRESHOLD:
        REDIS_CLIENT.set("STATUS_HEAVY_LOAD", "1", ex=30)
    else:
        REDIS_CLIENT.delete("STATUS_HEAVY_LOAD")

if __name__ == "__main__":
    print("👮 Governor Online.")
    while True:
        try: manage_resources()
        except: pass
        time.sleep(10)
EOF

# 3. DASHBOARD
echo "🖥 Updating Dashboard..."
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

cat << 'EOF' > services/dashboard/app.py
import streamlit as st
import pandas as pd
import redis, boto3, os, requests
from sqlalchemy import create_engine, text
from streamlit_ace import st_ace

st.set_page_config(layout="wide", page_title="Technocratic OS", page_icon="🧠")

if 'auth' not in st.session_state: st.session_state.auth = False
def check_pw():
    if st.session_state.auth: return True
    if st.text_input("Password", type="password") == "admin":
        st.session_state.auth = True
        st.rerun()
    return False
if not check_pw(): st.stop()

# Safe Connections
try: DB = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:5432/{os.getenv('POSTGRES_DB')}"; pg = create_engine(DB)
except: pg = None
try: r = redis.from_url(os.getenv("CELERY_BROKER_URL"))
except: r = None
try: s3 = boto3.client('s3', endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT')}", aws_access_key_id=os.getenv('MINIO_ACCESS_KEY'), aws_secret_access_key=os.getenv('MINIO_SECRET_KEY'))
except: s3 = None

t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Analytics", "📜 Logs", "🎯 Strategy", "🧬 DNA", "🚦 Status", "📂 Files"])

# ANALYTICS TAB
with t1:
    st.header("Reliability")
    if st.button("Refresh Stats"): st.rerun()
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM tool_stats ORDER BY calls_count DESC", pg)
            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else: st.info("No stats yet.")
        except: st.warning("Stats DB not ready.")

with t2:
    st.header("Logs")
    if st.button("Refresh Logs"): st.rerun()
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM run_logs ORDER BY created_at DESC LIMIT 20", pg)
            if not df.empty:
                for i, row in df.iterrows():
                    with st.expander(f"{row['created_at']} - {row['agent_role']} ({row['status']})"):
                        st.code(row['output_summary'])
        except: st.warning("No logs yet")

with t3:
    st.header("Projects")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM goals", pg)
            if not df.empty:
                roots = df[df['parent_id'].isnull()]
                for i, root in roots.iterrows():
                    with st.expander(f"{root['title']} ({root['progress']*100:.0f}%)"):
                        st.write(root['description'])
                        if st.button("Execute", key=f"x_{root['id']}"):
                            requests.post("http://core:8000/chat", json={"session_id":"admin","content":f"Execute {root['title']}"})
        except: pass

with t4:
    st.header("DNA")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM system_prompts", pg)
            if not df.empty:
                role = st.selectbox("Role", df['key'])
                val = df[df['key']==role]['content'].values
                st.text_area("Prompt", val[0] if len(val)>0 else "", height=300)
        except: pass

with t5:
    if r:
        try:
            raw = r.get("SYSTEM_PAUSED")
            paused = raw.decode('utf-8')=="1" if raw else False
            st.metric("Paused", "YES" if paused else "NO")
            if st.button("Toggle Pause"):
                if paused: r.delete("SYSTEM_PAUSED")
                else: r.set("SYSTEM_PAUSED", "1")
        except: st.error("Redis Error")

with t6:
    if s3:
        try:
            b = s3.list_buckets().get('Buckets', [])
            if b:
                bn = st.selectbox("Bucket", [x['Name'] for x in b])
                o = s3.list_objects_v2(Bucket=bn).get('Contents', [])
                if o: st.dataframe(pd.DataFrame([{"Key":x['Key'], "Size":x['Size']} for x in o]))
        except: pass
EOF

echo "✅ IMMUNE SYSTEM INSTALLED."
