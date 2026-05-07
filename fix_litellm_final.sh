#!/bin/bash
echo "🔧 REPAIRING LITELLM CONFIG & TELEGRAM..."

# 1. Записываем ГАРАНТИРОВАННО РАБОЧИЙ конфиг
# Используем Gemini 1.5 Flash везде, так как он самый надежный сейчас.
cat << 'EOF' > infra/litellm_config.yaml
model_list:
  # 1. SMART MODEL (Main Brain) -> Gemini 1.5 Flash
  # Используем Flash вместо Pro, так как Pro выдавал вам ошибки лимитов/доступа.
  - model_name: smart-model
    litellm_params:
      model: gemini/gemini-1.5-flash
      api_key: os.environ/GEMINI_KEY_1
      rpm: 100 # Высокий лимит

  # 2. TURBO -> Gemini 2.0 Flash Exp (Если доступен)
  - model_name: turbo-model
    litellm_params:
      model: gemini/gemini-2.0-flash-exp
      api_key: os.environ/GEMINI_KEY_1

  # 3. VISION
  - model_name: vision-model
    litellm_params:
      model: gemini/gemini-1.5-flash
      api_key: os.environ/GEMINI_KEY_1

  # 4. GROQ (Если нужен)
  - model_name: speed-coder
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: os.environ/GROQ_API_KEY

router_settings:
  routing_strategy: "simple-shuffle"
  timeout: 60
  num_retries: 2
  # Fallback: Если что-то не найдено, использовать smart-model
  fallbacks:
    - "turbo-model": ["smart-model"]
EOF

# 2. Перезапускаем критические сервисы
echo "🔄 Restarting Gateway and Interfaces..."
docker compose restart litellm telegram core_worker

echo "⏳ Waiting for LiteLLM initialization (5s)..."
sleep 5

# 3. Проверка логов LiteLLM, чтобы убедиться, что модели загрузились
echo "🔍 LiteLLM Logs:"
docker logs --tail 20 ns_litellm
