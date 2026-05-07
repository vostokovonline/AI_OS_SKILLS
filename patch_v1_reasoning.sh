#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/onor/ai_os_final"

echo "🩹 APPLYING PATCH v1 — Cloud Reasoning + 429 Safe Supervisor"

########################################
# 1. LiteLLM CONFIG (REAL PATH)
########################################

LITELLM_CFG="$ROOT/infra/litellm_config.yaml"

echo "🧠 Rewriting LiteLLM config → $LITELLM_CFG"

cat > "$LITELLM_CFG" <<'EOF'
model_list:
  # --- PRIMARY: Cloud Reasoning (DeepSeek via Ollama Cloud) ---
  - model_name: cloud-reasoner
    litellm_params:
      model: ollama/deepseek-v3.1:671b-cloud
      api_base: http://host.docker.internal:11434
      temperature: 0.2
      max_tokens: 8192

  # --- FALLBACK: Local Continuity ---
  - model_name: local-reasoner
    litellm_params:
      model: ollama/qwen2.5-coder:latest
      api_base: http://host.docker.internal:11434
      temperature: 0.3
      max_tokens: 4096

router_settings:
  routing_strategy: simple-shuffle
  timeout: 120
  num_retries: 0
  fallbacks:
    cloud-reasoner:
      - local-reasoner
EOF

########################################
# 2. SUPERVISOR PATCH (429 ≠ ERROR)
########################################

SUPERVISOR="$ROOT/services/core/supervisor.py"

echo "🧠 Patching Supervisor → $SUPERVISOR"

if ! grep -q "RateLimitError" "$SUPERVISOR"; then
cat >> "$SUPERVISOR" <<'EOF'

# --- PATCH: RATE LIMIT AWARE SUPERVISOR ---
from litellm.exceptions import RateLimitError
from datetime import datetime

def _safe_run_with_wait(self, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)

    except RateLimitError as e:
        retry_after = getattr(e, "retry_after", 60)

        self.logger.warning(
            f"🚦 RATE LIMIT — retry after {retry_after}s"
        )

        return {
            "status": "WAIT",
            "reason": "rate_limit",
            "retry_after": retry_after,
            "preferred_model": "cloud-reasoner",
            "timestamp": datetime.utcnow().isoformat()
        }
EOF
fi

########################################
# 3. CORE WORKER PATCH (Celery retry)
########################################

WORKER="$ROOT/services/core/worker.py"

echo "⚙️  Patching Core Worker → $WORKER"

if ! grep -q "status.*WAIT" "$WORKER"; then
cat >> "$WORKER" <<'EOF'

# --- PATCH: HANDLE WAIT STATE ---
if isinstance(result, dict) and result.get("status") == "WAIT":
    countdown = int(result.get("retry_after", 60))

    logger.info(
        f"⏳ Task deferred due to rate limit. Retry in {countdown}s"
    )

    raise self.retry(
        countdown=countdown,
        max_retries=10
    )
EOF
fi

########################################
# 4. REMOVE GEMINI ENV (OPTIONAL CLEANUP)
########################################

ENV_FILE="$ROOT/.env"

echo "🧹 Cleaning Gemini keys from .env (optional)"

sed -i '/GEMINI_KEY/d' "$ENV_FILE" || true

########################################
# 5. RESTART LITELLM + CORE
########################################

echo "🔄 Restarting affected services"

docker compose restart litellm core core_worker

echo "✅ PATCH v1 APPLIED SUCCESSFULLY"
