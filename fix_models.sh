#!/bin/bash
echo "⚡ FIXING GEMINI MODEL NAMES..."

# Обновляем конфиг с правильными именами
cat << 'EOF' > infra/litellm_config.yaml
model_list:
  # 1. SMART (Gemini 1.5 Pro)
  # Используем стабильное имя 'gemini-1.5-pro' без '-latest'
  - model_name: smart-model
    litellm_params:
      model: gemini/gemini-1.5-pro
      api_key: os.environ/GEMINI_KEY_1
      rpm: 10

  # 2. TURBO (Gemini 2.0 Flash)
  # Если experimental недоступен, можно откатить на 'gemini-1.5-flash'
  - model_name: turbo-model
    litellm_params:
      model: gemini/gemini-2.0-flash-exp
      api_key: os.environ/GEMINI_KEY_1
      rpm: 15

  # 3. SPEED CODER (Groq)
  - model_name: speed-coder
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: os.environ/GROQ_API_KEY
      rpm: 30

  # 4. VISION
  - model_name: vision-model
    litellm_params:
      model: gemini/gemini-1.5-flash
      api_key: os.environ/GEMINI_KEY_1

router_settings:
  routing_strategy: "simple-shuffle"
  timeout: 120
  num_retries: 2
  # Fallback: Если 2.0 Flash упадет -> 1.5 Flash
  fallbacks:
    - "turbo-model": ["vision-model"]
EOF

echo "✅ Config updated. Restarting LiteLLM..."
docker compose restart litellm core core_worker
