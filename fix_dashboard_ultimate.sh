#!/bin/bash
echo "🔥 FIXING DASHBOARD PERMISSIONS & UPDATING TO V4..."

# 1. FIX HOST PERMISSIONS (На хосте WSL)
# Разрешаем всем читать сокет докера (решает проблему доступа)
echo "🔒 Relaxing Docker Socket permissions on host..."
sudo chmod 666 /var/run/docker.sock

# 2. REWRITE DOCKER COMPOSE (Гарантируем volume и user: root)
# Мы обновляем только секцию dashboard, но для надежности перепишем файл,
# сохранив остальные сервисы. (Здесь полная версия файла с фиксом Dashboard)

cat << 'EOF' > docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: ns_postgres
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports: ["5432:5432"]
    volumes: ["./infra/postgres_data:/var/lib/postgresql/data"]
    networks: ["ns_network"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: ns_redis
    restart: always
    ports: ["6379:6379"]
    networks: ["ns_network"]

  minio:
    image: minio/minio:latest
    container_name: ns_minio
    restart: always
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    ports: ["9000:9000", "9001:9001"]
    volumes: ["./infra/minio_data:/data"]
    networks: ["ns_network"]

  etcd:
    image: quay.io/coreos/etcd:v3.5.0
    container_name: ns_etcd
    restart: always
    environment: ["ALLOW_NONE_AUTHENTICATION=yes"]
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls=http://0.0.0.0:2379
    networks: ["ns_network"]

  milvus:
    image: milvusdb/milvus:v2.3.0
    container_name: ns_milvus
    restart: always
    command: milvus run standalone
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
      MINIO_ACCESS_KEY_ID: ${MINIO_ACCESS_KEY}
      MINIO_SECRET_ACCESS_KEY: ${MINIO_SECRET_KEY}
    depends_on: ["etcd", "minio"]
    ports: ["19530:19530"]
    deploy: { resources: { limits: { memory: 2G } } }
    networks: ["ns_network"]

  neo4j:
    image: neo4j:5.12
    container_name: ns_neo4j
    restart: always
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_dbms_memory_heap_initial__size: 512m
      NEO4J_dbms_memory_heap_max__size: 1G
      NEO4J_dbms_memory_pagecache_size: 512M
    ports: ["7474:7474", "7687:7687"]
    volumes: ["./infra/neo4j_data/data:/data", "./infra/neo4j_data/logs:/logs"]
    deploy: { resources: { limits: { memory: 2G } } }
    networks: ["ns_network"]

  litellm:
    image: litellm/litellm:latest
    container_name: ns_litellm
    restart: always
    ports: ["4000:4000"]
    volumes: ["./infra/litellm_config.yaml:/app/config.yaml"]
    command: [ "--config", "/app/config.yaml", "--port", "4000" ]
    environment:
      GEMINI_KEY_1: ${GEMINI_KEY_1}
      GEMINI_KEY_2: ${GEMINI_KEY_2}
      GROQ_API_KEY: ${GROQ_API_KEY}
    networks: ["ns_network"]

  core:
    build: ./services/core
    container_name: ns_core
    restart: always
    ports: ["8000:8000"]
    env_file: .env
    volumes: ["./skills:/app/skills"]
    depends_on: ["postgres", "redis", "litellm"]
    networks: ["ns_network"]

  core_worker:
    build: ./services/core
    container_name: ns_core_worker
    restart: always
    command: celery -A tasks.celery_app worker --loglevel=info -Q default -c 2
    env_file: .env
    volumes: ["./skills:/app/skills"]
    depends_on: ["core", "redis"]
    networks: ["ns_network"]

  opencode:
    build: ./services/opencode
    container_name: ns_opencode
    restart: always
    ports: ["8002:8002"]
    env_file: .env
    volumes: ["./skills:/app/skills"]
    deploy: { resources: { limits: { cpus: '2.0', memory: 4G } } }
    networks: ["ns_network"]

  websurfer:
    build: ./services/websurfer
    container_name: ns_websurfer
    restart: always
    shm_size: '2gb'
    ports: ["8003:8003"]
    env_file: .env
    volumes: ["./infra/browser_data:/app/browser_data"]
    deploy: { resources: { limits: { cpus: '1.0', memory: 2G } } }
    networks: ["ns_network"]

  memory:
    build: ./services/memory
    container_name: ns_memory
    restart: always
    ports: ["8001:8001"]
    env_file: .env
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
    depends_on: ["milvus", "neo4j"]
    networks: ["ns_network"]

  telegram:
    build: ./services/telegram
    container_name: ns_telegram
    restart: always
    ports: ["8004:8004"]
    env_file: .env
    networks: ["ns_network"]

  governor:
    build: ./services/governor
    container_name: ns_governor
    restart: always
    volumes: ["/var/run/docker.sock:/var/run/docker.sock"]
    env_file: .env
    networks: ["ns_network"]

  # FIX: DASHBOARD WITH ROOT & SOCKET
  dashboard:
    build: ./services/dashboard
    container_name: ns_dashboard
    restart: always
    user: root # <--- ВАЖНО: Запуск от рута, чтобы читать сокет
    ports: ["8501:8501"]
    env_file: .env
    volumes:
      - ./skills:/app/skills
      - /var/run/docker.sock:/var/run/docker.sock # <--- ВАЖНО
    networks: ["ns_network"]

  avatar:
    build: ./services/avatar
    container_name: ns_avatar
    restart: always
    ports: ["8005:8005"]
    environment: { CORE_URL: http://core:8000 }
    networks: ["ns_network"]

  webhook:
    build: ./services/webhook
    container_name: ns_webhook
    restart: always
    ports: ["8007:8007"]
    env_file: .env
    networks: ["ns_network"]

  wallet:
    build: ./services/wallet
    container_name: ns_wallet
    restart: always
    ports: ["8006:8006"]
    volumes: ["./infra/wallet_data:/app/data"]
    networks: ["ns_network"]

networks:
  ns_network:
    driver: bridge
EOF

# 3. RE-APPLY DASHBOARD V4 CODE (Чтобы убедиться, что код новый)
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
    host = "ns_postgres"
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
            st.metric("Active Modules", f"{running}")
            
            with st.expander("Container Health"):
                for c in containers:
                    if "ns_" in c.name:
                        st.write(f"**{c.name}:** {c.status}")
        except Exception as e:
            st.error(f"Docker Socket Error: {e}")
    else:
        st.error("Docker Client Init Failed")
    
    # Queue Check
    if r:
        try:
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
        except: st.warning("Redis Disconnected")

# --- TABS ---
t_chat, t_logs, t_strat, t_treasury, t_files = st.tabs(["💬 Direct Link", "📜 Logs", "🎯 Strategy", "💰 Treasury", "📂 Files"])

# === TAB 1: DIRECT CHAT ===
with t_chat:
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
        try:
            df = pd.read_sql("SELECT * FROM run_logs ORDER BY created_at DESC LIMIT 50", pg)
            if not df.empty:
                errs = len(df[df['status']!='success'])
                st.metric("Errors (Last 50)", errs, delta=-errs if errs>0 else 0)
                for i, row in df.iterrows():
                    icon = "🟢" if row['status']=='success' else "🔴"
                    with st.expander(f"{icon} {row['agent_role']} -> {row['tool_used']} ({row['duration_ms']:.0f}ms)"):
                        c1, c2 = st.columns(2)
                        c1.code(row['input_summary'], language="json")
                        c2.code(row['output_summary'])
            else: st.info("No logs yet.")
        except: st.warning("Logs DB not ready.")

# === TAB 3: STRATEGY ===
with t_strat:
    st.subheader("Active Goals")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM goals WHERE status='active'", pg)
            if not df.empty:
                for i, row in df.iterrows():
                    st.info(f"**{row['title']}**")
                    st.caption(row['description'])
                    if st.button("Execute Step", key=f"g_{i}"):
                        requests.post(f"{CORE_URL}/chat", json={"session_id":"admin", "content":f"Work on {row['title']}"})
                        st.toast("Agent Deployed")
            else: st.info("No active goals.")
        except: pass

# === TAB 4: TREASURY (Cost Monitor) ===
with t_treasury:
    st.header("Resource Consumption")
    if pg:
        try:
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
            else: st.info("Not enough data.")
        except: pass

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

# 4. FORCE REBUILD
echo "🔄 REMOVING OLD DASHBOARD..."
docker rm -f ns_dashboard 2>/dev/null

echo "🚀 BUILDING & STARTING NEW DASHBOARD..."
docker compose up -d --build --force-recreate dashboard

echo "✅ DONE. Check http://localhost:8501 (Status should be OK)"
