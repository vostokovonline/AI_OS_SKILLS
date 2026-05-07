#!/bin/bash
# Тест прямых запросов к LiteLLM

echo "🧪 Testing LLM Connection..."

# 1. Test Groq via LiteLLM
echo "--- Testing Groq (Speed Coder) ---"
curl -s -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "speed-coder",
    "messages": [{"role": "user", "content": "Say hello!"}]
  }' | grep "content" || echo "❌ Groq Failed"

# 2. Test Gemini via LiteLLM
echo -e "\n--- Testing Gemini (Turbo) ---"
curl -s -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "turbo-model",
    "messages": [{"role": "user", "content": "Say hello!"}]
  }' | grep "content" || echo "❌ Gemini Failed"
