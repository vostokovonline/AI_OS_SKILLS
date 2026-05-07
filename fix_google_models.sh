#!/bin/bash
echo "🔧 FIXING GOOGLE MODEL NAMES (FORCE GEMINI 2.0)..."

# Переписываем конфиг.
# Используем gemini/gemini-2.0-flash-exp везде. Это "серебряная пуля".
cat << 'EOF' > infra/litellm_config.yaml
model_list:
  # 1. SMART (Brain) -> Gemini 2.0 Flash Exp
  - model_name: smart-model
    litellm_params:
      model: gemini/gemini-2.0-flash-exp
      api_key: os.environ/GEMINI_KEY_1
      rpm: 10 # Rate Limit

  # 2. TURBO (Tools) -> Gemini 2.0 Flash Exp
  - model_name: turbo-model
    litellm_params:
      model: gemini/gemini-2.0-flash-exp
      api_key: os.environ/GEMINI_KEY_1
      rpm: 10

  # 3. VISION (Eyes) -> Gemini 2.0 Flash Exp
  - model_name: vision-model
    litellm_params:
      model: gemini/gemini-2.0-flash-exp
      api_key: os.environ/GEMINI_KEY_1

  # 4. SPEED CODER (Fallback if Groq fails)
  - model_name: speed-coder
    litellm_params:
      model: gemini/gemini-2.0-flash-exp
      api_key: os.environ/GEMINI_KEY_1

router_settings:
  routing_strategy: "simple-shuffle"
  timeout: 120
  num_retries: 2
  fallbacks:
    - "smart-model": ["turbo-model"]
EOF

echo "🔄 Restarting LiteLLM & Worker..."
docker compose restart litellm core_worker
