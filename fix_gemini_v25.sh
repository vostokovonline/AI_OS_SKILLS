#!/bin/bash
echo "🚀 UPGRADING MODELS TO GEMINI 2.5..."

# Переписываем конфиг LiteLLM
cat << 'EOF' > infra/litellm_config.yaml
model_list:
  # 1. SMART (Gemini 2.5 Pro)
  # Используем новейшую Pro модель для сложных задач
  - model_name: smart-model
    litellm_params:
      model: gemini/gemini-2.5-pro
      api_key: os.environ/GEMINI_KEY_1
      rpm: 10

  # 2. TURBO (Gemini 2.5 Flash)
  # Используем новейшую Flash модель для скорости
  - model_name: turbo-model
    litellm_params:
      model: gemini/gemini-2.5-flash
      api_key: os.environ/GEMINI_KEY_1
      rpm: 15

  # 3. VISION
  - model_name: vision-model
    litellm_params:
      model: gemini/gemini-2.5-flash
      api_key: os.environ/GEMINI_KEY_1

  # 4. SPEED CODER (Groq)
  # Оставляем, если есть ключ. Если нет - сработает fallback
  - model_name: speed-coder
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: os.environ/GROQ_API_KEY
      rpm: 30

router_settings:
  routing_strategy: "simple-shuffle"
  timeout: 120
  num_retries: 2
  # Fallback: Если Groq не работает, используем Gemini 2.5 Flash
  fallbacks:
    - "speed-coder": ["turbo-model"]
EOF

echo "🔄 Restarting LiteLLM & Core..."
docker compose restart litellm core core_worker

echo "✅ DONE. System is now running on Gemini 2.5."
