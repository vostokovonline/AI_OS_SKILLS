"""
Trace Store - Persistent хранилище execution traces для AI-OS Learning Layer

Хранит полные цепочки execution для:
1. Обучения на прошлом
2. Pattern mining
3. Cognitive Cache (по goal_type)
4. Strategy Compilation

Использует Postgres для persistence + in-memory кэш.
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4


def get_logger():
    """Get logger - structlog if available, else standard logging"""
    try:
        import structlog
        return structlog.get_logger(__name__)
    except ImportError:
        class SimpleLogger:
            def info(self, msg, **kwargs):
                print(f"[INFO] {msg} {kwargs}", file=sys.stderr)
            def warning(self, msg, **kwargs):
                print(f"[WARNING] {msg} {kwargs}", file=sys.stderr)
            def debug(self, msg, **kwargs):
                print(f"[DEBUG] {msg} {kwargs}", file=sys.stderr)
            def error(self, msg, **kwargs):
                print(f"[ERROR] {msg} {kwargs}", file=sys.stderr)
        return SimpleLogger()

logger = get_logger()


class TraceStore:
    """
    Persistent хранилище traces с Postgres backend.
    
    Структура trace:
    {
        "trace_id": str,
        "goal_id": str,
        "goal_title": str,
        "goal_type": str,  # CRITICAL: for goal_type-based cognitive cache
        "events": [...],
        "status": str,
        "confidence": float,
        "started_at": datetime,
        "completed_at": datetime
    }
    """
    
    def __init__(self):
        self._traces: Dict[str, dict] = {}
        self._pool = None
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Инициализация - подключение к Postgres"""
        if self._initialized:
            return
            
        try:
            from database import engine
            self._pool = engine
            await self._load_traces_from_db()
            self._initialized = True
            logger.info("trace_store_initialized", traces_count=len(self._traces))
        except Exception as e:
            logger.warning("trace_store_db_init_failed", error=str(e), using="in_memory")
            self._initialized = True
    
    async def _load_traces_from_db(self) -> None:
        """Загрузить traces из Postgres при старте"""
        try:
            from sqlalchemy import text
            from database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text("""
                        SELECT trace_id, goal_id, goal_title, goal_type, 
                               skill_name, status, confidence, 
                               started_at, completed_at, events
                        FROM execution_traces 
                        ORDER BY started_at DESC 
                        LIMIT 500
                    """)
                )
                rows = result.fetchall()
                
                for row in rows:
                    trace = {
                        "trace_id": row[0],
                        "goal_id": row[1],
                        "goal_title": row[2],
                        "goal_type": row[3],
                        "skill_name": row[4],
                        "status": row[5],
                        "confidence": row[6],
                        "started_at": row[7].isoformat() if row[7] else None,
                        "completed_at": row[8].isoformat() if row[8] else None,
                        "events": row[9] if isinstance(row[9], list) else json.loads(row[9]) if row[9] else []
                    }
                    self._traces[row[1]] = trace
                    
                logger.info("traces_loaded_from_db", count=len(rows))
        except Exception as e:
            logger.warning("load_traces_from_db_failed", error=str(e))
    
    async def append_event(self, goal_id: str, event_type: str, data: dict) -> None:
        """Добавить событие к trace"""
        async with self._lock:
            if goal_id not in self._traces:
                self._traces[goal_id] = {
                    "trace_id": str(uuid4()),
                    "goal_id": goal_id,
                    "goal_title": data.get("goal_title", ""),
                    "goal_type": data.get("goal_type", ""),
                    "events": [],
                    "started_at": datetime.utcnow().isoformat()
                }
            
            self._traces[goal_id]["events"].append({
                "type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            })
            
            if event_type == "SkillSelected":
                self._traces[goal_id]["skill_name"] = data.get("skill_name", "")
            
            await self._save_to_db(goal_id)
    
    async def _save_to_db(self, goal_id: str) -> None:
        """Сохранить trace в Postgres"""
        if not self._pool:
            return
            
        try:
            from sqlalchemy import text
            from database import AsyncSessionLocal
            
            trace = self._traces.get(goal_id)
            if not trace:
                return
            
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("""
                        INSERT INTO execution_traces 
                        (trace_id, goal_id, goal_title, goal_type, skill_name, status, confidence, started_at, completed_at, events)
                        VALUES (:trace_id, :goal_id, :goal_title, :goal_type, :skill_name, :status, :confidence, :started_at, :completed_at, :events)
                        ON CONFLICT (trace_id) DO UPDATE SET
                            events = EXCLUDED.events,
                            status = COALESCE(EXCLUDED.status, execution_traces.status),
                            confidence = COALESCE(EXCLUDED.confidence, execution_traces.confidence),
                            completed_at = COALESCE(EXCLUDED.completed_at, execution_traces.completed_at)
                    """),
                    {
                        "trace_id": trace["trace_id"],
                        "goal_id": trace["goal_id"],
                        "goal_title": trace.get("goal_title", ""),
                        "goal_type": trace.get("goal_type", ""),
                        "skill_name": trace.get("skill_name", ""),
                        "status": trace.get("status", ""),
                        "confidence": trace.get("confidence", 0.0),
                        "started_at": trace.get("started_at"),
                        "completed_at": trace.get("completed_at"),
                        "events": json.dumps(trace.get("events", []))
                    }
                )
                await session.commit()
        except Exception as e:
            logger.debug("trace_save_to_db_failed", goal_id=goal_id, error=str(e))
    
    async def update_trace_status(self, goal_id: str, status: str, confidence: float) -> None:
        """Обновить статус trace после завершения"""
        async with self._lock:
            if goal_id in self._traces:
                self._traces[goal_id]["status"] = status
                self._traces[goal_id]["confidence"] = confidence
                self._traces[goal_id]["completed_at"] = datetime.utcnow().isoformat()
                await self._save_to_db(goal_id)
    
    async def get_trace(self, goal_id: str) -> Optional[dict]:
        """Получить trace по goal_id"""
        return self._traces.get(goal_id)
    
    async def get_all_traces(self, limit: int = 100) -> List[dict]:
        """Получить все traces (последние)"""
        traces = list(self._traces.values())
        traces.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return traces[:limit]
    
    async def get_traces_by_goal_type(self, goal_type: str) -> List[dict]:
        """Получить traces по goal_type"""
        return [t for t in self._traces.values() if t.get("goal_type") == goal_type]
    
    async def get_traces_by_status(self, status: str) -> List[dict]:
        """Получить traces по статусу"""
        return [t for t in self._traces.values() if t.get("status") == status]
    
    async def get_skill_usage(self) -> Dict[str, int]:
        """Подсчитать использование каждого skill"""
        usage: Dict[str, int] = {}
        for trace in self._traces.values():
            for event in trace.get("events", []):
                if event.get("type") == "SkillSelected":
                    skill = event.get("data", {}).get("skill_name", "unknown")
                    usage[skill] = usage.get(skill, 0) + 1
        return usage
    
    async def get_skill_success_rate(self) -> Dict[str, Dict[str, Any]]:
        """Подсчитать success rate для каждого skill"""
        skill_results: Dict[str, Dict[str, int]] = {}
        
        for trace in self._traces.values():
            status = trace.get("status")
            if not status:
                continue
                
            for event in trace.get("events", []):
                if event.get("type") == "SkillSelected":
                    skill = event.get("data", {}).get("skill_name", "unknown")
                    if skill not in skill_results:
                        skill_results[skill] = {"success": 0, "total": 0}
                    
                    skill_results[skill]["total"] += 1
                    if status == "completed":
                        skill_results[skill]["success"] += 1
        
        rates = {}
        for skill, stats in skill_results.items():
            rates[skill] = {
                "success_rate": stats["success"] / stats["total"] if stats["total"] > 0 else 0.0,
                "total": stats["total"],
                "success": stats["success"]
            }
        
        return rates
    
    async def get_goal_type_stats(self) -> Dict[str, Dict[str, Any]]:
        """Получить статистику по goal_type для cognitive cache"""
        goal_type_stats: Dict[str, Dict[str, Any]] = {}
        
        for trace in self._traces.values():
            goal_type = trace.get("goal_type", "unknown")
            if not goal_type:
                continue
                
            skill_name = trace.get("skill_name", "")
            status = trace.get("status", "")
            
            if goal_type not in goal_type_stats:
                goal_type_stats[goal_type] = {"skills": {}, "total": 0}
            
            goal_type_stats[goal_type]["total"] += 1
            
            if skill_name:
                if skill_name not in goal_type_stats[goal_type]["skills"]:
                    goal_type_stats[goal_type]["skills"][skill_name] = {"success": 0, "total": 0}
                
                goal_type_stats[goal_type]["skills"][skill_name]["total"] += 1
                if status == "completed":
                    goal_type_stats[goal_type]["skills"][skill_name]["success"] += 1
        
        return goal_type_stats
    
    async def clear_old_traces(self, days: int = 30) -> int:
        """Очистить старые traces"""
        cutoff = datetime.utcnow().timestamp() - (days * 86400)
        to_delete = []
        
        for goal_id, trace in self._traces.items():
            try:
                started_str = trace.get("started_at", "")
                if started_str:
                    started = datetime.fromisoformat(started_str)
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
            "skill_success_rate": await self.get_skill_success_rate(),
            "goal_type_stats": await self.get_goal_type_stats()
        }


_trace_store: Optional[TraceStore] = None


def get_trace_store() -> TraceStore:
    """Получить глобальный trace store"""
    global _trace_store
    if _trace_store is None:
        _trace_store = TraceStore()
    return _trace_store
