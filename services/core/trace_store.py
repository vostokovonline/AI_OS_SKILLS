"""
Trace Store - Хранилище reasoning traces для AI-OS

Хранит полные цепочки execution для:
1. Обучения на прошлом
2. Pattern mining
3. Cognitive Cache
4. Strategy Compilation
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID


class TraceStore:
    """
    In-memory хранилище traces с Redis backup.
    
    Структура trace:
    {
        "goal_id": str,
        "goal_title": str,
        "events": [
            {"type": "GoalExecutionStarted", "timestamp": "...", "data": {...}},
            {"type": "SkillSelected", "timestamp": "...", "data": {...}},
            ...
        ],
        "status": str,
        "confidence": float,
        "started_at": datetime,
        "completed_at": datetime
    }
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self._traces: Dict[str, dict] = {}
        self._redis_url = redis_url
        self._redis = None
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Инициализация Redis"""
        if self._redis_url:
            try:
                from redis.asyncio import Redis
                self._redis = Redis.from_url(self._redis_url, decode_responses=True)
                await self._redis.ping()
            except Exception as e:
                print(f"Redis not available: {e}")
                self._redis = None
    
    async def append_event(self, goal_id: str, event_type: str, data: dict) -> None:
        """Добавить событие к trace"""
        async with self._lock:
            if goal_id not in self._traces:
                self._traces[goal_id] = {
                    "goal_id": goal_id,
                    "events": [],
                    "started_at": datetime.utcnow().isoformat()
                }
            
            self._traces[goal_id]["events"].append({
                "type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            })
            
            # Backup to Redis
            if self._redis:
                try:
                    await self._redis.hset(
                        f"trace:{goal_id}",
                        mapping={
                            "data": json.dumps(self._traces[goal_id]),
                            "updated_at": datetime.utcnow().isoformat()
                        }
                    )
                except Exception:
                    pass  # Best effort
    
    async def update_trace_status(self, goal_id: str, status: str, confidence: float) -> None:
        """Обновить статус trace после завершения"""
        async with self._lock:
            if goal_id in self._traces:
                self._traces[goal_id]["status"] = status
                self._traces[goal_id]["confidence"] = confidence
                self._traces[goal_id]["completed_at"] = datetime.utcnow().isoformat()
    
    async def get_trace(self, goal_id: str) -> Optional[dict]:
        """Получить trace по goal_id"""
        # Try memory first
        if goal_id in self._traces:
            return self._traces[goal_id]
        
        # Try Redis
        if self._redis:
            try:
                data = await self._redis.hget(f"trace:{goal_id}", "data")
                if data:
                    return json.loads(data)
            except Exception:
                pass
        
        return None
    
    async def get_all_traces(self, limit: int = 100) -> List[dict]:
        """Получить все traces (последние)"""
        traces = list(self._traces.values())
        traces.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return traces[:limit]
    
    async def get_traces_by_status(self, status: str) -> List[dict]:
        """Получить traces по статусу"""
        return [t for t in self._traces.values() if t.get("status") == status]
    
    async def get_skill_usage(self) -> Dict[str, int]:
        """Подсчитать использование каждого skill"""
        usage = {}
        for trace in self._traces.values():
            for event in trace.get("events", []):
                if event["type"] == "SkillSelected":
                    skill = event["data"].get("skill_name", "unknown")
                    usage[skill] = usage.get(skill, 0) + 1
        return usage
    
    async def get_skill_success_rate(self) -> Dict[str, float]:
        """Подсчитать success rate для каждого skill"""
        skill_results: Dict[str, Dict[str, int]] = {}
        
        for trace in self._traces.values():
            status = trace.get("status")
            if not status:
                continue
                
            for event in trace.get("events", []):
                if event["type"] == "SkillSelected":
                    skill = event["data"].get("skill_name", "unknown")
                    if skill not in skill_results:
                        skill_results[skill] = {"success": 0, "total": 0}
                    
                    skill_results[skill]["total"] += 1
                    if status == "completed":
                        skill_results[skill]["success"] += 1
        
        # Calculate rates
        rates = {}
        for skill, stats in skill_results.items():
            if stats["total"] > 0:
                rates[skill] = stats["success"] / stats["total"]
            else:
                rates[skill] = 0.0
        
        return rates
    
    async def clear_old_traces(self, days: int = 7) -> int:
        """Очистить старые traces"""
        cutoff = datetime.utcnow().timestamp() - (days * 86400)
        to_delete = []
        
        for goal_id, trace in self._traces.items():
            try:
                started = datetime.fromisoformat(trace.get("started_at", "2000-01-01"))
                if started.timestamp() < cutoff:
                    to_delete.append(goal_id)
            except Exception:
                pass
        
        for goal_id in to_delete:
            del self._traces[goal_id]
        
        return len(to_delete)
    
    async def get_stats(self) -> dict:
        """Получить статистику по traces"""
        total = len(self._traces)
        completed = len([t for t in self._traces.values() if t.get("status") == "completed"])
        failed = len([t for t in self._traces.values() if t.get("status") == "failed"])
        
        return {
            "total_traces": total,
            "completed": completed,
            "failed": failed,
            "in_progress": total - completed - failed,
            "skill_usage": await self.get_skill_usage(),
            "skill_success_rate": await self.get_skill_success_rate()
        }


# Global trace store
_trace_store: Optional[TraceStore] = None


def get_trace_store() -> TraceStore:
    """Получить глобальный trace store"""
    global _trace_store
    if _trace_store is None:
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _trace_store = TraceStore(redis_url=redis_url)
    return _trace_store
