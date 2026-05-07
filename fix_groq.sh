#!/bin/bash
echo "⚡ UPDATING GROQ MODELS (FIX DEPRECATION)..."

# Переписываем конфиг LiteLLM с актуальной моделью (Llama 3.3)
cat << 'EOF' > infra/litellm_config.yaml
model_list:
  # --- 1. SPEED CODER (Updated to Llama 3.3 70B) ---
  # Это самая новая и мощная модель от Groq на данный момент
  - model_name: speed-coder
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: os.environ/GROQ_API_KEY
      rpm: 30

  # --- 2. TURBO (GEMINI 2.0 FLASH) ---
  - model_name: turbo-model
    litellm_params:
      model: gemini/gemini-2.0-flash-exp
      api_key: os.environ/GEMINI_KEY_1
      rpm: 10

  # --- 3. SMART (GEMINI 1.5 PRO) ---
  - model_name: smart-model
    litellm_params:
      model: gemini/gemini-1.5-pro-latest
      api_key: os.environ/GEMINI_KEY_1
      rpm: 10

  # --- 4. VISION ---
  - model_name: vision-model
    litellm_params:
      model: gemini/gemini-1.5-flash
      api_key: os.environ/GEMINI_KEY_1

router_settings:
  routing_strategy: "simple-shuffle"
  timeout: 90
  num_retries: 2
  # Если Groq упадет, переключиться на Gemini Turbo
  fallbacks:
    - "speed-coder": ["turbo-model"]
EOF

echo "🔄 Restarting LiteLLM Gateway..."
docker compose restart litellm

echo "✅ DONE. Models updated."
