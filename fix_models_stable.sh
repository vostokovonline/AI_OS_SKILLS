#!/bin/bash
echo "🛡 SWITCHING TO STABLE MODELS (GEMINI FLASH ONLY)..."

# Переписываем конфиг LiteLLM
# Используем 'gemini/gemini-1.5-flash' для ВСЕХ ролей.
# Это гарантирует, что мы не упремся в ограничения Pro версии.

cat << 'EOF' > infra/litellm_config.yaml
model_list:
  # 1. SMART (Теперь тоже Flash, так как Pro недоступна)
  - model_name: smart-model
    litellm_params:
      model: gemini/gemini-1.5-flash
      api_key: os.environ/GEMINI_KEY_1
      rpm: 15

  # 2. TURBO (Flash)
  - model_name: turbo-model
    litellm_params:
      model: gemini/gemini-1.5-flash
      api_key: os.environ/GEMINI_KEY_1
      rpm: 15

  # 3. SPEED CODER (Groq - оставляем, если ключ есть, или фоллбек на Flash)
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
  timeout: 60
  num_retries: 2
  # Если Groq не настроен, используем Flash
  fallbacks:
    - "speed-coder": ["turbo-model"]
EOF

echo "🔄 Restarting LiteLLM..."
# Принудительно пересоздаем контейнер, чтобы конфиг точно обновился
docker compose up -d --force-recreate litellm

echo "✅ DONE. All systems mapped to Gemini Flash."
