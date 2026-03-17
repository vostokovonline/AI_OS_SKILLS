"""
TELEGRAM NOTIFIER MODULE

Отправляет уведомления о вопросах и выполнении целей в Telegram.
"""
import os
import json
import logging
from typing import Optional, Dict, Any
import redis
import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CORE_API_URL = os.getenv("CORE_API_URL", "http://ns_core:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://ns_redis:6379/0")
TELEGRAM_URL = os.getenv("TELEGRAM_URL", "http://telegram:8004")


class TelegramNotifier:
    """Отправляет уведомления в Telegram"""

    def __init__(self):
        self.enabled = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "your_bot_token_here")
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        self._owner_chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID")

    def is_enabled(self) -> bool:
        """Проверяет включен ли Telegram"""
        return self.enabled

    def is_user_linked(self, user_id: str) -> bool:
        """Проверяет привязан ли пользователь к Telegram"""
        try:
            chat_id = self.redis_client.get(f"telegram:user_chat:{user_id}")
            return chat_id is not None
        except redis.RedisError as e:
            logger.debug("redis_error_checking_user_link", user_id=user_id, error=str(e))
            return False
        except Exception as e:
            logger.warning("unexpected_error_checking_user_link", user_id=user_id, error=str(e))
            return False

    async def send_question(self, user_id: str, question_data: Dict[str, Any]) -> bool:
        """
        Отправляет вопрос пользователю в Telegram
        """
        if not self.enabled:
            logger.debug("Telegram not enabled, skipping notification")
            return False

        if not self.is_user_linked(user_id):
            logger.info(f"User {user_id} not linked to Telegram")
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{CORE_API_URL}/telegram/send_question",
                    json={
                        "user_id": user_id,
                        "question_data": question_data
                    },
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    async def notify_goal_completed(
        self,
        goal_id: str,
        goal_title: str,
        status: str = "done",
        artifacts_count: int = 0,
        duration_seconds: float = 0,
        details: Dict[str, Any] = None
    ) -> bool:
        """
        Отправляет уведомление о выполнении цели в Telegram.
        
        Args:
            goal_id: ID цели
            goal_title: Название цели
            status: Статус выполнения (done, failed, blocked)
            artifacts_count: Количество созданных артефактов
            duration_seconds: Время выполнения в секундах
            details: Дополнительные детали
        """
        if not self.enabled:
            logger.debug("Telegram not enabled, skipping goal notification")
            return False

        try:
            # Формируем подробное сообщение
            status_emoji = "✅" if status == "done" else "❌" if status == "failed" else "⚠️"
            
            message_lines = [
                f"{status_emoji} <b>Цель выполнена</b>",
                "",
                f"📋 <b>{goal_title}</b>",
                f"ID: <code>{goal_id[:8]}...</code>",
                "",
                f"📊 <b>Статус:</b> {status}",
                f"📦 <b>Артефактов:</b> {artifacts_count}",
                f"⏱️ <b>Время:</b> {duration_seconds:.1f}s",
            ]
            
            if details:
                message_lines.append("")
                message_lines.append("<b>📝 Детали:</b>")
                for key, value in details.items():
                    if value:
                        message_lines.append(f"  • {key}: {value}")
            
            message = "\n".join(message_lines)
            
            # Отправляем через Telegram API напрямую
            async with httpx.AsyncClient() as client:
                # Пробуем отправить владельцу
                if self._owner_chat_id:
                    try:
                        await client.post(
                            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                            json={
                                "chat_id": self._owner_chat_id,
                                "text": message,
                                "parse_mode": "HTML"
                            },
                            timeout=10.0
                        )
                        logger.info("goal_notification_sent_to_owner", goal_id=goal_id)
                        return True
                    except Exception as e:
                        logger.warning("failed_send_to_owner", error=str(e))
                
                # Пробуем через internal API
                response = await client.post(
                    f"{CORE_API_URL}/telegram/notify",
                    json={"message": message},
                    timeout=10.0
                )
                return response.status_code == 200
                
        except Exception as e:
            logger.error("goal_notification_error", goal_id=goal_id, error=str(e))
            return False

    async def notify_decomposition_needed(self, goal_id: str, goal_title: str, question_data: Dict[str, Any] = None, question_text: str = "") -> bool:
        """
        Отправляет вопрос декомпозиции в Telegram.
        """
        if not self.enabled:
            return False
        
        # If question_data provided, send the actual question
        if question_data:
            question_text = question_data.get("text", question_text)
            question_id = question_data.get("id", "")
            
        try:
            message = f"""
🔍 <b>Вопрос по цели</b>

📋 <b>{goal_title}</b>

❓ <b>Вопрос:</b>
{question_text}

Ответьте на этот вопрос в дашборде или здесь.
"""
            async with httpx.AsyncClient() as client:
                if self._owner_chat_id:
                    await client.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": self._owner_chat_id,
                            "text": message,
                            "parse_mode": "HTML"
                        },
                        timeout=10.0
                    )
                    logger.info("question_sent_to_telegram", goal_id=goal_id)
                    return True
        except Exception as e:
            logger.error("question_notification_error", error=str(e))
            return False


# Глобальный инстанс
notifier = TelegramNotifier()


async def send_question_notification(user_id: str, question_data: Dict[str, Any]) -> bool:
    """Отправляет уведомление о вопросе в Telegram"""
    return await notifier.send_question(user_id, question_data)


async def send_goal_completed_notification(
    goal_id: str,
    goal_title: str,
    status: str = "done",
    artifacts_count: int = 0,
    duration_seconds: float = 0,
    details: Dict[str, Any] = None
) -> bool:
    """Отправляет уведомление о выполнении цели в Telegram"""
    return await notifier.notify_goal_completed(
        goal_id=goal_id,
        goal_title=goal_title,
        status=status,
        artifacts_count=artifacts_count,
        duration_seconds=duration_seconds,
        details=details
    )


async def send_decomposition_notification(
    goal_id: str,
    goal_title: str,
    question_data: Dict[str, Any] = None,
    question_text: str = ""
) -> bool:
    """Отправляет вопрос декомпозиции в Telegram"""
    return await notifier.notify_decomposition_needed(goal_id, goal_title, question_data, question_text)


if __name__ == "__main__":
    import asyncio

    async def test():
        tn = TelegramNotifier()
        logger.info(f"Telegram enabled: {tn.is_enabled()}")

    asyncio.run(test())
