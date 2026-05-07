#!/bin/bash
set -e

ROOT="/home/onor/ai_os_final"
CFG="$ROOT/infra/litellm_config.yaml"

echo "🧠 Fixing LiteLLM → Ollama (FINAL, CLEAN)"

# 1. Backup
echo "📦 Backup old config"
cp "$CFG" "$CFG.bak.$(date +%s)" 2>/dev/null || true

# 2. Write CLEAN config (schema-valid)
echo "📝 Writing clean litellm_config.yaml"
cat << 'EOF' > "$CFG"
model_list:
  - model_name: qwen-coder
    litellm_params:
      model: ollama/qwen2.5-coder:latest
      api_base: http://host.docker.internal:11434

  - model_name: deepseek-reasoner
    litellm_params:
      model: ollama/deepseek-v3.1:671b-cloud
      api_base: http://host.docker.internal:11434

general_settings:
  master_key: sk-no-auth
  drop_params: true
  request_timeout: 120
EOF

echo "✅ Config written"

# 3. Restart only needed services
cd "$ROOT"
echo "🔄 Restarting LiteLLM + Core"
docker compose restart litellm core core_worker

# 4. Wait & show logs
echo "⏳ Waiting for LiteLLM..."
sleep 6

echo "📜 LiteLLM logs:"
docker logs --tail 50 ns_litellm || true

echo "✅ DONE"
echo "👉 Test with:"
echo "curl http://localhost:4000/v1/models"
