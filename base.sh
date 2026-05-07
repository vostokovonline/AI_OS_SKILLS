#!/bin/bash
# base.sh - INFRASTRUCTURE & CONFIG
set -e

echo "🚀 [1/3] INITIALIZING INFRASTRUCTURE (v3.10)..."

# 1. Directories
mkdir -p infra/postgres_data infra/neo4j_data/data infra/neo4j_data/logs infra/minio_data infra/milvus_data infra/browser_data
mkdir -p skills
touch skills/__init__.py
mkdir -p services/core/agents services/core/llm services/opencode services/memory services/core/cognition
mkdir -p services/websurfer services/telegram services/governor services/dashboard services/avatar services/webhook

# 2. Configs
echo "📝 Generating .env..."
cat << 'EOF' > .env
# --- SECRETS (EDIT AFTER RUNNING!) ---
GEMINI_KEY_1=change_me
GEMINI_KEY_2=change_me
GROQ_API_KEY=change_me
TELEGRAM_TOKEN=change_me
TELEGRAM_OWNER_ID=000000000
OPENAI_API_KEY=sk-stub

# --- SYSTEM ---
POSTGRES_USER=ns_admin
POSTGRES_PASSWORD=ns_secure_pass
POSTGRES_DB=ns_core_db
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
NEO4J_PASSWORD=ns_graph_secure_pass

# Governor Limits
CPU_THRESHOLD=99
RAM_THRESHOLD=99

# Internal URLs
DATABASE_URL=postgresql+asyncpg://ns_admin:ns_secure_pass@postgres:5432/ns_core_db
OPENCODE_URL=http://opencode:8002
WEBSURFER_URL=http://websurfer:8003
MEMORY_URL=http://memory:8001
TELEGRAM_URL=http://telegram:8004
CORE_URL=http://core:8000
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
LLM_BASE_URL=http://litellm:4000
MINIO_ENDPOINT=http://minio:9000
EOF

echo "📝 Generating LiteLLM Config..."
cat << 'EOF' > infra/litellm_config.yaml
model_list:
  # TURBO (Gemini 2.0 Flash)
  - model_name: turbo-model
    litellm_params:
      model: gemini/gemini-2.0-flash-exp
      api_key: os.environ/GEMINI_KEY_1
      rpm: 10
  # SMART (Gemini 1.5 Pro)
  - model_name: smart-model
    litellm_params:
      model: gemini/gemini-1.5-pro-latest
      api_key: os.environ/GEMINI_KEY_2
      rpm: 10
  # SPEED CODER (Groq Llama 3)
  - model_name: speed-coder
    litellm_params:
      model: groq/llama3-70b-8192
      api_key: os.environ/GROQ_API_KEY
      rpm: 30
  # VISION
  - model_name: vision-model
    litellm_params:
      model: gemini/gemini-1.5-flash
      api_key: os.environ/GEMINI_KEY_1

router_settings:
  routing_strategy: "simple-shuffle"
  timeout: 90
  num_retries: 2
EOF

# 3. Docker Compose
echo "🐳 Generating docker-compose.yml..."
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
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks: ["ns_network"]

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

  dashboard:
    build: ./services/dashboard
    container_name: ns_dashboard
    restart: always
    ports: ["8501:8501"]
    env_file: .env
    volumes: ["./skills:/app/skills"]
    networks: ["ns_network"]

  avatar:
    build: ./services/avatar
    container_name: ns_avatar
    restart: always
    ports: ["8005:8005"]
    environment: { CORE_URL: http://core:8000 }
    networks: ["ns_network"]

networks:
  ns_network:
    driver: bridge
EOF

echo "✅ BASE Setup Complete."
