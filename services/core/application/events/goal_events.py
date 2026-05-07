"""
Domain Events - События предметной области
==========================================

Все события - immutable dataclasses с @frozen=True
"""
from dataclasses import dataclass
from uuid import UUID
from datetime import datetime


@dataclass(frozen=True)
class GoalActivated:
    """Цель активирована (переведена из pending в active)"""
    goal_id: UUID
    actor: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())


@dataclass(frozen=True)
class GoalDecomposed:
    """Цель декомпозирована - созданы подцели"""
    parent_goal_id: UUID
    child_count: int
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())


@dataclass(frozen=True)
class GoalExecuted:
    """Атомарная цель выполнена"""
    goal_id: UUID
    success: bool
    progress: float
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())


@dataclass(frozen=True)
class GoalCompleted:
    """Цель завершена успешно"""
    goal_id: UUID
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())


@dataclass(frozen=True)
class GoalFailed:
    """Цель не удалась"""
    goal_id: UUID
    error: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())
