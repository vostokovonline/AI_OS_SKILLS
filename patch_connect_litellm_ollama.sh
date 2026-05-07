#!/bin/bash
set -e

ROOT="/home/onor/ai_os_final"

echo "🔧 [1/4] Creating LiteLLM config..."

mkdir -p $ROOT/infra

cat > $ROOT/infra/litellm_config.yaml <<'EOF'
model_list:
  - model_name: cloud-reasoner
    litellm_params:
      model: ollama/deepseek-v3.1:671b-cloud
      api_base: http://host.docker.internal:11434
      temperature: 0.2
      max_tokens: 8192

  - model_name: local-coder
    litellm_params:
      model: ollama/qwen2.5-coder:latest
      api_base: http://host.docker.internal:11434
      temperature: 0.3
      max_tokens: 4096

router_settings:
  timeout: 180
  num_retries: 3
  fallbacks:
    cloud-reasoner:
      - local-coder
EOF

echo "✅ LiteLLM config created"

# ----------------------------------------------------

echo "🔧 [2/4] Wiring LiteLLM into core worker..."

CORE_LLM="$ROOT/services/core/llm"

mkdir -p $CORE_LLM

cat > $CORE_LLM/client.py <<'EOF'
import os
import time
from litellm import completion

DEFAULT_MODEL = os.getenv("LLM_MODEL", "cloud-reasoner")

def call_llm(messages, model=DEFAULT_MODEL, retries=3):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            return completion(
                model=model,
                messages=messages,
            )
        except Exception as e:
            last_error = e
            if "429" in str(e):
                time.sleep(2 * attempt)
            else:
                time.sleep(1)

    raise RuntimeError(f"LLM failed after {retries} retries: {last_error}")
EOF

echo "✅ core/llm/client.py created"

# ----------------------------------------------------

echo "🔧 [3/4] Injecting environment variables into docker-compose..."

DC="$ROOT/docker-compose.yml"

if ! grep -q LITELLM_CONFIG "$DC"; then
  sed -i '/services:/a\
  litellm:\n\
    image: ghcr.io/berriai/litellm:latest\n\
    volumes:\n\
      - ./infra:/app/infra\n\
    environment:\n\
      - LITELLM_CONFIG=/app/infra/litellm_config.yaml\n\
    extra_hosts:\n\
      - "host.docker.internal:host-gateway"\n\
    ports:\n\
      - "4000:4000"\n' "$DC"
fi

echo "✅ docker-compose updated"

# ----------------------------------------------------

echo "🔧 [4/4] Restarting stack..."

cd $ROOT
docker compose down
docker compose up -d

echo "🚀 DONE. LiteLLM + Windows Ollama are now wired correctly."
