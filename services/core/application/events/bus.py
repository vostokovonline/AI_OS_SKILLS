"""
Event Bus - Simple in-process event system
==========================================

Заменяет HTTP вызовы между компонентами.

Usage:
    event_bus = EventBus()
    
    # Subscribe
    event_bus.subscribe(GoalActivated, my_handler)
    
    # Publish
    await event_bus.publish(GoalActivated(goal_id=uuid))
"""
from collections import defaultdict
from typing import Callable, Awaitable, Type, Any, List

Handler = Callable[[Any], Awaitable[None]]


class EventBus:
    """Простой in-process event bus"""
    
    def __init__(self):
        self._subs: dict[Type, List[Handler]] = defaultdict(list)
    
    def subscribe(self, event_type: Type, handler: Handler) -> None:
        """Подписаться на событие"""
        self._subs[event_type].append(handler)
    
    async def publish(self, event: Any) -> None:
        """Опубликовать одно событие"""
        import logging
        logger = logging.getLogger("event_bus")
        logger.info(f"event_published: {type(event).__name__}")
        handlers = self._subs.get(type(event), [])
        logger.info(f"event_subscribers: {type(event).__name__}, count={len(handlers)}")
        for handler in handlers:
            try:
                import asyncio
                import inspect
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    f"event_handler_error: event_type={type(event).__name__}, error={str(e)}"
                )
    
    async def publish_many(self, events: List[Any]) -> None:
        """Опубликовать несколько событий"""
        for event in events:
            await self.publish(event)


# Глобальный event bus
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Получить глобальный event bus"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def set_event_bus(bus: EventBus) -> None:
    """Установить глобальный event bus (для тестов)"""
    global _event_bus
    _event_bus = bus
