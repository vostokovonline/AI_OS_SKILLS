"""
Domain Models - Execution Trace
===============================
Чистые доменные модели для трассировки выполнения.
Никаких внешних зависимостей - только Python dataclasses.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4


class TraceEventType(Enum):
    """Типы событий в trace"""
    GOAL_CREATED = "goal_created"
    GOAL_READY = "goal_ready"
    DECOMPOSITION_STARTED = "decomposition_started"
    DECOMPOSITION_COMPLETED = "decomposition_completed"
    SKILL_SELECTED = "skill_selected"
    SKILL_STARTED = "skill_started"
    SKILL_COMPLETED = "skill_completed"
    SKILL_FAILED = "skill_failed"
    ARTIFACT_PRODUCED = "artifact_produced"
    ARTIFACT_VERIFIED = "artifact_verified"
    EVALUATION_STARTED = "evaluation_started"
    EVALUATION_COMPLETED = "evaluation_completed"
    GOAL_COMPLETED = "goal_completed"
    GOAL_FAILED = "goal_failed"
    GOAL_BLOCKED = "goal_blocked"
    GOAL_RETRY = "goal_retry"
    CONTEXT_BUILT = "context_built"
    LLM_CALLED = "llm_called"
    ERROR_OCCURRED = "error_occurred"


class TraceStatus(Enum):
    """Статус trace"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class TraceEvent:
    """
    Атомарное событие в execution trace.
    Immutable - после создания не изменяется.
    """
    event_id: UUID = field(default_factory=uuid4)
    event_type: TraceEventType = TraceEventType.GOAL_CREATED
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Что произошло
    goal_id: Optional[UUID] = None
    skill_id: Optional[str] = None
    artifact_id: Optional[UUID] = None
    
    # Детали события
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Контекст
    goal_type: Optional[str] = None
    confidence: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "goal_id": str(self.goal_id) if self.goal_id else None,
            "skill_id": self.skill_id,
            "artifact_id": str(self.artifact_id) if self.artifact_id else None,
            "message": self.message,
            "metadata": self.metadata,
            "goal_type": self.goal_type,
            "confidence": self.confidence,
        }


@dataclass
class ExecutionTrace:
    """
    Полный trace выполнения цели.
    Включает все события от создания до завершения.
    """
    trace_id: UUID = field(default_factory=uuid4)
    goal_id: UUID = None  # type: ignore # Will be set
    goal_title: str = ""
    goal_type: str = ""
    
    events: List[TraceEvent] = field(default_factory=list)
    status: TraceStatus = TraceStatus.PENDING
    
    # Метрики
    confidence: float = 0.0
    success_score: float = 0.0
    
    # Время
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Технические
    retry_count: int = 0
    error_count: int = 0
    
    def add_event(self, event: TraceEvent) -> None:
        """Добавить событие в trace"""
        self.events.append(event)
        self._recalculate_status()
    
    def _recalculate_status(self) -> None:
        """Пересчитать статус на основе событий"""
        event_types = {e.event_type for e in self.events}
        
        if TraceEventType.GOAL_COMPLETED in event_types:
            self.status = TraceStatus.COMPLETED
            self.completed_at = datetime.utcnow()
        elif TraceEventType.GOAL_FAILED in event_types:
            self.status = TraceStatus.FAILED
            self.completed_at = datetime.utcnow()
        elif TraceEventType.GOAL_BLOCKED in event_types:
            self.status = TraceStatus.BLOCKED
            self.completed_at = datetime.utcnow()
        elif TraceEventType.GOAL_READY in event_types or TraceEventType.SKILL_STARTED in event_types:
            self.status = TraceStatus.RUNNING
    
    def get_skill_events(self) -> List[TraceEvent]:
        """Получить все события связанные с навыками"""
        skill_types = {
            TraceEventType.SKILL_SELECTED,
            TraceEventType.SKILL_STARTED,
            TraceEventType.SKILL_COMPLETED,
            TraceEventType.SKILL_FAILED,
        }
        return [e for e in self.events if e.event_type in skill_types]
    
    def get_artifact_events(self) -> List[TraceEvent]:
        """Получить все события связанные с артефактами"""
        artifact_types = {
            TraceEventType.ARTIFACT_PRODUCED,
            TraceEventType.ARTIFACT_VERIFIED,
        }
        return [e for e in self.events if e.event_type in artifact_types]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": str(self.trace_id),
            "goal_id": str(self.goal_id),
            "goal_title": self.goal_title,
            "goal_type": self.goal_type,
            "events": [e.to_dict() for e in self.events],
            "status": self.status.value,
            "confidence": self.confidence,
            "success_score": self.success_score,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
            "error_count": self.error_count,
        }


@dataclass
class TraceStatistics:
    """Агрегированная статистика по traces"""
    total_traces: int = 0
    completed_traces: int = 0
    failed_traces: int = 0
    blocked_traces: int = 0
    
    avg_confidence: float = 0.0
    avg_success_score: float = 0.0
    avg_duration_seconds: float = 0.0
    
    # По типам целей
    by_goal_type: Dict[str, int] = field(default_factory=dict)
    
    # По навыкам
    skill_usage: Dict[str, int] = field(default_factory=dict)
    skill_success_rate: Dict[str, float] = field(default_factory=dict)
