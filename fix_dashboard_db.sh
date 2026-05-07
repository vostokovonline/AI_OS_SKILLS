#!/bin/bash
echo "🖥 FIXING DASHBOARD DATABASE CONNECTION..."

# Перезаписываем app.py с жесткой привязкой к ns_postgres
cat << 'EOF' > services/dashboard/app.py
import streamlit as st
import pandas as pd
import redis, boto3, os, requests
from sqlalchemy import create_engine, text
from streamlit_ace import st_ace

st.set_page_config(layout="wide", page_title="Technocratic OS", page_icon="🧠")

# --- AUTH ---
if 'auth' not in st.session_state: st.session_state.auth = False
def check_pw():
    if st.session_state.auth: return True
    if st.text_input("Password", type="password") == "admin":
        st.session_state.auth = True
        st.rerun()
    return False
if not check_pw(): st.stop()

# --- ROBUST CONNECTION SETUP ---

# 1. Postgres (FIXED: Hardcoded fallback to 'ns_postgres')
try:
    pg_user = os.getenv('POSTGRES_USER', 'ns_admin')
    pg_pass = os.getenv('POSTGRES_PASSWORD', 'ns_secure_pass')
    pg_db = os.getenv('POSTGRES_DB', 'ns_core_db')
    
    # Если переменная пуста, используем имя контейнера
    pg_host = os.getenv('POSTGRES_HOST')
    if not pg_host or pg_host == "None":
        pg_host = "ns_postgres"

    DB_URL = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:5432/{pg_db}"
    pg = create_engine(DB_URL)
    
    # Test connection
    with pg.connect() as conn:
        pass
except Exception as e:
    pg = None
    st.sidebar.error(f"⚠️ DB Error: {e}")

# 2. Redis
try:
    r = redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://ns_redis:6379/0"))
    r.ping()
except:
    r = None
    st.sidebar.warning("Redis disconnected")

# 3. MinIO
try:
    s3 = boto3.client('s3', 
        endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT', 'ns_minio:9000')}",
        aws_access_key_id=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'), 
        aws_secret_access_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    )
except:
    s3 = None
    
CORE_URL = os.getenv("CORE_URL", "http://ns_core:8000")

# --- TABS ---
t1, t2, t3, t4, t5, t6 = st.tabs(["📜 Logs", "🎯 Strategy", "🧬 DNA", "🚦 Status", "📂 Files", "🔧 Skills"])

# TAB 1: LIVE LOGS
with t1:
    st.header("System Telemetry")
    if st.button("🔄 Refresh Logs"): st.rerun()
    
    if pg:
        try:
            # Проверяем наличие таблицы
            logs_df = pd.read_sql("SELECT created_at, agent_role, tool_used, status, duration_ms, input_summary, output_summary FROM run_logs ORDER BY created_at DESC LIMIT 50", pg)
            
            if not logs_df.empty:
                for i, row in logs_df.iterrows():
                    status_icon = "🟢" if row['status'] == "success" else "🔴"
                    role = row['agent_role'] or "SYSTEM"
                    tool = row['tool_used'] or "action"
                    
                    with st.expander(f"{status_icon} [{row['created_at'].strftime('%H:%M:%S')}] {role} -> {tool}"):
                        st.code(f"Input: {row['input_summary']}", language="json")
                        st.code(f"Output: {row['output_summary']}")
                        st.caption(f"Duration: {row['duration_ms']:.0f}ms")
            else:
                st.info("No logs found yet.")
        except Exception as e:
            st.warning(f"Log table error (DB might be initializing): {e}")
    else:
        st.error("Database connection failed.")

# TAB 2: STRATEGY
with t2:
    st.header("Projects")
    if st.button("Refresh Strategy"): st.rerun()
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM goals", pg)
            if not df.empty:
                roots = df[df['parent_id'].isnull()]
                for i, root in roots.iterrows():
                    prog = float(root['progress']) if root['progress'] else 0.0
                    with st.expander(f"{root['title']} ({prog*100:.0f}%)"):
                        st.write(root['description'])
                        if st.button("⚡ Execute", key=f"x_{root['id']}"):
                            try:
                                requests.post(f"{CORE_URL}/chat", json={"session_id":"admin","content":f"Execute project: {root['title']}"})
                                st.success("Task sent to Core")
                            except: st.error("Core offline")
                        
                        kids = df[df['parent_id'] == root['id']]
                        if not kids.empty: st.dataframe(kids[['title', 'status', 'progress']])
            else:
                st.info("No projects active.")
        except: pass

# TAB 3: DNA
with t3:
    st.header("System DNA")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM system_prompts", pg)
            if not df.empty:
                role = st.selectbox("Role", df['key'])
                val = df[df['key']==role]['content'].values
                txt = st.text_area("Prompt", val[0] if len(val)>0 else "", height=300)
                if st.button("Update DNA"):
                     with pg.begin() as conn:
                        conn.execute(text("UPDATE system_prompts SET content = :c WHERE key = :k"), {"c": txt, "k": role})
                     st.success("Updated!")
                     st.rerun()
        except: pass

# TAB 4: STATUS
with t4:
    if r:
        try:
            raw = r.get("SYSTEM_PAUSED")
            paused = raw.decode('utf-8')=="1" if raw else False
            st.metric("Paused", "YES" if paused else "NO")
            if st.button("Toggle Pause"):
                if paused: r.delete("SYSTEM_PAUSED")
                else: r.set("SYSTEM_PAUSED", "1")
                st.rerun()
        except: pass

# TAB 5: FILES
with t5:
    if s3:
        try:
            b = s3.list_buckets().get('Buckets', [])
            if b:
                bn = st.selectbox("Bucket", [x['Name'] for x in b])
                o = s3.list_objects_v2(Bucket=bn).get('Contents', [])
                if o: st.dataframe(pd.DataFrame([{"Key":x['Key'], "Size":x['Size']} for x in o]))
        except: pass

# TAB 6: SKILLS
with t6:
    d = "/app/skills"
    if os.path.exists(d):
        f = st.selectbox("File", [x for x in os.listdir(d) if x.endswith(".py")])
        if f:
            c = open(f"{d}/{f}").read()
            nc = st_ace(c, language="python")
            if st.button("Save"): open(f"{d}/{f}", "w").write(nc)
EOF

echo "✅ DASHBOARD FIXED. Rebuilding..."
docker compose up -d --build --force-recreate dashboard
