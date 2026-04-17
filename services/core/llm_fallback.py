from logging_config import get_logger
logger = get_logger(__name__)

"""
LLM Fallback Manager - Умное переключение между LLM при rate limits
Предотвращает ошибки 404 от Groq путем переключения на fallback модель
"""
import os
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx

try:
    import aioredis
    AIOREDIS_AVAILABLE = True
except ImportError:
    AIOREDIS_AVAILABLE = False
    aioredis = None

# Конфигурация
GROQ_COOLDOWN_HOURS = int(os.getenv("GROQ_COOLDOWN_HOURS", "6"))  # На сколько часов отключать Groq
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "ollama/qwen2.5-coder:latest")
FALLBACK_API_BASE = os.getenv("FALLBACK_API_BASE", "http://host.docker.internal:11434")

# Redis ключи
GROQ_FAILURE_KEY = "llm:groq:failure_timestamp"
GROQ_DISABLED_KEY = "llm:groq:disabled_until"


class AsyncRedisManager:
    """Async Redis connection manager with fallback"""
    
    def __init__(self):
        self._redis = None
        self._mock_storage = {}  # Fallback when aioredis unavailable
    
    async def get_redis(self):
        if not AIOREDIS_AVAILABLE:
            return None
        if self._redis is None:
            self._redis = aioredis.Redis(
                host='redis',
                port=6379,
                db=0,
                decode_responses=True
            )
        return self._redis
    
    async def get(self, key: str) -> Optional[str]:
        if not AIOREDIS_AVAILABLE:
            return self._mock_storage.get(key)
        redis = await self.get_redis()
        return await redis.get(key)
    
    async def set(self, key: str, value: str, ex: int = None):
        if not AIOREDIS_AVAILABLE:
            self._mock_storage[key] = value
            return
        redis = await self.get_redis()
        await redis.set(key, value, ex=ex)
    
    async def delete(self, *keys: str):
        if not AIOREDIS_AVAILABLE:
            for key in keys:
                self._mock_storage.pop(key, None)
            return
        redis = await self.get_redis()
        await redis.delete(*keys)


# Global async Redis manager
async_redis = AsyncRedisManager()


class LLMFallbackManager:
    """Менеджер для умного переключения между LLM моделями"""

    def __init__(self):
        self.litellm_base_url = os.getenv("OPENAI_API_BASE", "http://litellm:4000/v1")
        self.api_key = os.getenv("OPENAI_API_KEY", "sk-1234")

    async def is_groq_available(self) -> bool:
        """Проверяет доступен ли Groq (не в cooldown)"""
        disabled_until = await async_redis.get(GROQ_DISABLED_KEY)
        if not disabled_until:
            return True

        disabled_until_ts = float(disabled_until)
        if time.time() > disabled_until_ts:
            # Cooldown истек, можно возвращаться к Groq
            await async_redis.delete(GROQ_DISABLED_KEY, GROQ_FAILURE_KEY)
            logger.info(f"✅ Groq cooldown expired, switching back to Groq")
            return True

        return False

    async def mark_groq_failed(self):
        """Помечает Groq как недоступный на N часов"""
        now = time.time()
        disabled_until = now + (GROQ_COOLDOWN_HOURS * 3600)

        await async_redis.set(GROQ_FAILURE_KEY, str(now))
        await async_redis.set(GROQ_DISABLED_KEY, str(disabled_until), ex=GROQ_COOLDOWN_HOURS * 3600 + 60)

        logger.info(f"⚠️ Groq marked as FAILED for {GROQ_COOLDOWN_HOURS} hours")
        logger.info(f"   Disabled until: {datetime.fromtimestamp(disabled_until).isoformat()}")

    async def chat_completion(
        self,
        model: str,
        messages: list,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Выполняет chat/completions запрос с автоматическим fallback (async)
        """
        # Проверяем если это Groq модель и она в cooldown
        is_groq_model = "groq" in model.lower()
        
        # groq сломана - используем только работающие модели
        if is_groq_model or "qwen3" in model or model in ["deepseek-reasoner", "minimax", "glm-", "kimi", "gemma4"]:
            logger.info(f"⚠️ Using qwen2.5-coder (broken models fallback)")
            model = "qwen2.5-coder"
            kwargs.pop("api_base", None)  # Remove custom api_base

        # Выполняем запрос через litellm
        url = f"{self.litellm_base_url}/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                model_used = result.get("model", model)
                logger.info(f"✅ LLM call successful: {model_used}")
                return result

        except httpx.HTTPStatusError as e:
            error_text = e.response.text

            # Детектируем 404 ошибку от Groq (rate limit)
            if e.response.status_code == 404 and "groq" in model.lower():
                if "GroqException" in error_text or "404 page not found" in error_text:
                    logger.info(f"❌ Groq 404 error detected - rate limit hit!")
                    await self.mark_groq_failed()

                    # Retry с fallback моделью
                    logger.info(f"🔄 Retrying with fallback: {FALLBACK_MODEL}")

                    # Меняем модель на fallback
                    payload["model"] = FALLBACK_MODEL
                    if "ollama" in FALLBACK_MODEL:
                        payload["api_base"] = FALLBACK_API_BASE

                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(url, json=payload, headers=headers)
                        response.raise_for_status()
                        result = response.json()
                        model_used = result.get("model", FALLBACK_MODEL)
                        logger.info(f"✅ Fallback LLM call successful: {model_used}")
                        return result

            # Другие ошибки пробрасываем дальше
            logger.info(f"❌ LLM API error: {e.response.status_code} - {error_text[:200]}")
            raise

    async def get_status(self) -> Dict[str, Any]:
        """Возвращает статус fallback системы"""
        disabled_until = await async_redis.get(GROQ_DISABLED_KEY)
        failure_timestamp = await async_redis.get(GROQ_FAILURE_KEY)

        status = {
            "groq_available": await self.is_groq_available(),
            "fallback_model": FALLBACK_MODEL,
            "cooldown_hours": GROQ_COOLDOWN_HOURS
        }

        if disabled_until:
            disabled_until_dt = datetime.fromtimestamp(float(disabled_until))
            remaining = disabled_until_dt - datetime.now()
            status["groq_disabled_until"] = disabled_until_dt.isoformat()
            status["cooldown_remaining"] = str(remaining)

        if failure_timestamp:
            failure_dt = datetime.fromtimestamp(float(failure_timestamp))
            status["last_failure"] = failure_dt.isoformat()

        return status


# Глобальный инстанс
llm_fallback = LLMFallbackManager()


def chat_with_fallback_sync(model: str, messages: list, **kwargs) -> Dict[str, Any]:
    """
    Синхронная обертка для LLM вызовов с fallback.
    """
    import httpx
    import os
    
    litellm_base_url = os.getenv("OPENAI_API_BASE", "http://ns_litellm:4000/v1")
    api_key = os.getenv("OPENAI_API_KEY", "sk-1234")
    
    url = f"{litellm_base_url}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        **kwargs
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


async def chat_with_fallback(model: str, messages: list, **kwargs) -> Dict[str, Any]:
    """
    Обертка для LLM вызов с автоматическим fallback (async version)

    Usage:
        result = await chat_with_fallback(
            model="groq/llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Hello"}]
        )
    """
    return await llm_fallback.chat_completion(model, messages, **kwargs)


if __name__ == "__main__":
    # Тест
    import asyncio

    async def test():
        manager = LLMFallbackManager()

        # Проверка статуса
        status = await manager.get_status()
        logger.info(json.dumps(status, indent=2))

        # Тест вызова
        result = await manager.chat_completion(
            model="groq/llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Say 'Hello World'"}]
        )
        logger.info(json.dumps(result, indent=2))

    asyncio.run(test())
