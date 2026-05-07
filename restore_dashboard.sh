#!/bin/bash
echo "🖥 RESTORING ADVANCED DASHBOARD (MISSION CONTROL v2)..."

cat << 'EOF' > services/dashboard/app.py
import streamlit as st
import pandas as pd
import redis, boto3, os, requests
from sqlalchemy import create_engine, text
from streamlit_ace import st_ace

st.set_page_config(layout="wide", page_title="AI-OS Mission Control", page_icon="🚀")

# --- AUTH ---
if 'auth' not in st.session_state: st.session_state.auth = False
def check_pw():
    if st.session_state.auth: return True
    if st.text_input("Password", type="password") == "admin":
        st.session_state.auth = True
        st.rerun()
    return False
if not check_pw(): st.stop()

# --- CONNECTORS (ROBUST) ---
# 1. Postgres (Fix for 'None' host error)
try:
    pg_user = os.getenv('POSTGRES_USER', 'ns_admin')
    pg_pass = os.getenv('POSTGRES_PASSWORD', 'ns_secure_pass')
    pg_db = os.getenv('POSTGRES_DB', 'ns_core_db')
    pg_host = os.getenv('POSTGRES_HOST')
    
    # Фолбэк, если переменная не прокинулась
    if not pg_host or pg_host == "None": pg_host = "ns_postgres"

    DB_URL = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:5432/{pg_db}"
    pg = create_engine(DB_URL)
except Exception as e:
    pg = None
    st.sidebar.error(f"DB Config Error: {e}")

# 2. Redis
try:
    r = redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://ns_redis:6379/0"))
except: r = None

# 3. MinIO
try:
    s3 = boto3.client('s3', 
        endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT', 'ns_minio:9000')}",
        aws_access_key_id=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'), 
        aws_secret_access_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    )
except: s3 = None

CORE_URL = os.getenv("CORE_URL", "http://ns_core:8000")

# --- UI LAYOUT ---
st.title("🧠 Technocratic OS: Mission Control")

tabs = st.tabs(["📜 Live Logs", "🎯 Strategy", "🧬 DNA / Minds", "🚦 System Status", "📂 Files", "🔧 Skill Editor"])

# === TAB 1: LOGS ===
with tabs[0]:
    col1, col2 = st.columns([1, 6])
    if col1.button("🔄 Refresh"): st.rerun()
    
    if pg:
        try:
            df = pd.read_sql("SELECT created_at, agent_role, tool_used, status, duration_ms, input_summary, output_summary FROM run_logs ORDER BY created_at DESC LIMIT 50", pg)
            if not df.empty:
                for i, row in df.iterrows():
                    icon = "🟢" if row['status'] == "success" else "🔴"
                    title = f"{icon} [{row['created_at'].strftime('%H:%M:%S')}] **{row['agent_role']}** used `{row['tool_used']}` ({row['duration_ms']:.0f}ms)"
                    with st.expander(title):
                        st.text("INPUT:")
                        st.code(row['input_summary'], language="json")
                        st.text("OUTPUT:")
                        st.code(row['output_summary'])
            else:
                st.info("No logs found. System is waiting for tasks.")
        except Exception as e:
            st.warning(f"Logs table not ready: {e}")
    else:
        st.error("DB Not Connected")

# === TAB 2: STRATEGY ===
with tabs[1]:
    st.subheader("Active Projects")
    if col1.button("Refresh Goals"): st.rerun()
    
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM goals ORDER BY created_at DESC", pg)
            if not df.empty:
                roots = df[df['parent_id'].isnull()]
                for i, root in roots.iterrows():
                    prog = float(root['progress']) if root['progress'] else 0.0
                    status_emoji = "✅" if root['status'] == 'completed' else "🚧"
                    
                    with st.expander(f"{status_emoji} {root['title']} ({prog*100:.0f}%)"):
                        st.write(f"**Description:** {root['description']}")
                        st.write(f"**Status:** {root['status']}")
                        
                        c1, c2 = st.columns(2)
                        if c1.button("⚡ Execute Step", key=f"exec_{root['id']}"):
                            try:
                                requests.post(f"{CORE_URL}/chat", json={"session_id":"admin","content":f"Work on goal: {root['title']}"})
                                st.success("Task sent to Supervisor")
                            except: st.error("Core Offline")
                        
                        # Subtasks
                        kids = df[df['parent_id'] == root['id']]
                        if not kids.empty:
                            st.dataframe(kids[['title', 'status', 'progress']], use_container_width=True)
            else:
                st.info("Goal Database is empty. Tell the bot: 'Create a goal: ...'")
        except: st.warning("Goal table not initialized.")

# === TAB 3: DNA ===
with tabs[2]:
    st.subheader("Agent Personalities (System Prompts)")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM system_prompts", pg)
            if not df.empty:
                role = st.selectbox("Select Agent Role", df['key'])
                current_val = df[df['key']==role]['content'].values[0]
                new_val = st.text_area("System Prompt", current_val, height=300)
                
                if st.button("💾 Update DNA"):
                    with pg.begin() as conn:
                        conn.execute(text("UPDATE system_prompts SET content = :c WHERE key = :k"), {"c": new_val, "k": role})
                    st.success(f"Updated {role}!")
                    st.rerun()
            else:
                st.warning("DNA Table empty. Core restart required to bootstrap.")
        except: st.warning("DNA table missing.")

# === TAB 4: STATUS ===
with tabs[3]:
    st.subheader("Governor & Resources")
    if r:
        try:
            raw_paused = r.get("SYSTEM_PAUSED")
            is_paused = raw_paused.decode('utf-8') == "1" if raw_paused else False
            
            raw_heavy = r.get("STATUS_HEAVY_LOAD")
            is_heavy = raw_heavy.decode('utf-8') == "1" if raw_heavy else False

            col1, col2 = st.columns(2)
            col1.metric("System Paused", "YES" if is_paused else "NO", delta_color="inverse")
            col2.metric("Heavy Load", "YES" if is_heavy else "NO", delta_color="inverse")
            
            if st.button("🚨 Toggle Emergency Pause"):
                if is_paused: r.delete("SYSTEM_PAUSED")
                else: r.set("SYSTEM_PAUSED", "1")
                st.rerun()
                
            st.divider()
            st.write("Queues:")
            st.write(f"- Tasks Pending: **{r.llen('default')}**")
        except Exception as e: st.error(f"Redis Error: {e}")

# === TAB 5: FILES ===
with tabs[4]:
    if s3:
        try:
            buckets = s3.list_buckets().get('Buckets', [])
            if buckets:
                bn = st.selectbox("Bucket", [x['Name'] for x in buckets])
                objs = s3.list_objects_v2(Bucket=bn).get('Contents', [])
                if objs:
                    files_df = pd.DataFrame([{"File": x['Key'], "Size (KB)": round(x['Size']/1024, 2)} for x in objs])
                    st.dataframe(files_df, use_container_width=True)
                else:
                    st.info("Bucket is empty.")
            else:
                st.warning("No buckets found.")
        except Exception as e: st.error(f"S3 Error: {e}")

# === TAB 6: SKILLS ===
with tabs[5]:
    st.subheader("Skill Editor (Python)")
    d = "/app/skills"
    if os.path.exists(d):
        files = [x for x in os.listdir(d) if x.endswith(".py")]
        if files:
            f = st.selectbox("Select Skill", files)
            if f:
                path = f"{d}/{f}"
                with open(path, "r") as fl: c = fl.read()
                nc = st_ace(c, language="python", theme="monokai", height=500)
                if st.button("💾 Save Code"):
                    with open(path, "w") as fl: fl.write(nc)
                    st.success("Skill updated!")
        else:
            st.info("No skills created yet. Ask the Coder to create one.")
    else:
        st.error("Skills volume not mounted.")
EOF

echo "✅ DASHBOARD RESTORED."
echo "👉 Rebuilding container..."
docker compose up -d --build --force-recreate dashboard
