"""
Domain Events - AI-OS Event System
====================================
Domain events для межкомпонентного взаимодействия.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4


class DomainEventType(Enum):
    """Типы доменных событий"""
    # Goal lifecycle
    GOAL_CREATED = "goal.created"
    GOAL_READY = "goal.ready"
    GOAL_DECOMPOSED = "goal.decomposed"
    GOAL_STARTED = "goal.started"
    GOAL_EVALUATING = "goal.evaluating"
    GOAL_COMPLETED = "goal.completed"
    GOAL_FAILED = "goal.failed"
    GOAL_BLOCKED = "goal.blocked"
    GOAL_RETRY = "goal.retry"
    GOAL_FROZEN = "goal.frozen"
    GOAL_UNFROZEN = "goal.unfrozen"
    
    # Skill lifecycle
    SKILL_SELECTED = "skill.selected"
    SKILL_INVOKED = "skill.invoked"
    SKILL_COMPLETED = "skill.completed"
    SKILL_FAILED = "skill.failed"
    SKILL_EVOLVED = "skill.evolved"
    
    # Artifact lifecycle
    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_VERIFIED = "artifact.verified"
    ARTIFACT_FAILED = "artifact.failed"
    
    # Decision engine
    POLICY_SELECTED = "policy.selected"
    REGRET_ANALYZED = "regret.analyzed"
    STRATEGY_UPDATED = "strategy.updated"
    
    # Memory
    PATTERN_STORED = "pattern.stored"
    BELIEF_UPDATED = "belief.updated"
    CONTEXT_BUILT = "context.built"
    
    # Execution
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"


@dataclass
class DomainEvent:
    """
    Базовый класс для всех domain events.
    Все события immutable после создания.
    """
    event_id: UUID = field(default_factory=uuid4)
    event_type: DomainEventType = DomainEventType.GOAL_CREATED
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Aggregate roots
    goal_id: Optional[UUID] = None
    skill_id: Optional[str] = None
    artifact_id: Optional[UUID] = None
    
    # Payload
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Causation
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "goal_id": str(self.goal_id) if self.goal_id else None,
            "skill_id": self.skill_id,
            "artifact_id": str(self.artifact_id) if self.artifact_id else None,
            "metadata": self.metadata,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "causation_id": str(self.causation_id) if self.causation_id else None,
        }


# Специализированные события


@dataclass
class GoalCreatedEvent(DomainEvent):
    """Событие создания цели"""
    goal_title: str = ""
    goal_type: str = ""
    parent_goal_id: Optional[UUID] = None
    
    def __init__(self, goal_id: UUID, title: str, goal_type: str, parent_goal_id: Optional[UUID] = None):
        super().__init__()
        self.event_type = DomainEventType.GOAL_CREATED
        self.goal_id = goal_id
        self.goal_title = title
        self.goal_type = goal_type
        self.parent_goal_id = parent_goal_id
        self.metadata = {
            "title": title,
            "goal_type": goal_type,
            "parent_goal_id": str(parent_goal_id) if parent_goal_id else None,
        }


@dataclass
class GoalCompletedEvent(DomainEvent):
    """Событие завершения цели"""
    success_score: float = 0.0
    confidence: float = 0.0
    artifacts_count: int = 0
    
    def __init__(self, goal_id: UUID, success_score: float, confidence: float, artifacts_count: int):
        super().__init__()
        self.event_type = DomainEventType.GOAL_COMPLETED
        self.goal_id = goal_id
        self.success_score = success_score
        self.confidence = confidence
        self.artifacts_count = artifacts_count
        self.metadata = {
            "success_score": success_score,
            "confidence": confidence,
            "artifacts_count": artifacts_count,
        }


@dataclass
class SkillInvokedEvent(DomainEvent):
    """Событие вызова навыка"""
    skill_name: str = ""
    capability: str = ""
    success: bool = False
    latency_seconds: float = 0.0
    
    def __init__(self, goal_id: UUID, skill_id: str, skill_name: str, capability: str):
        super().__init__()
        self.event_type = DomainEventType.SKILL_INVOKED
        self.goal_id = goal_id
        self.skill_id = skill_id
        self.skill_name = skill_name
        self.capability = capability
        self.metadata = {
            "skill_name": skill_name,
            "capability": capability,
        }


@dataclass
class SkillCompletedEvent(DomainEvent):
    """Событие завершения навыка"""
    skill_name: str = ""
    success: bool = False
    latency_seconds: float = 0.0
    quality_score: float = 0.0
    
    def __init__(self, goal_id: UUID, skill_id: str, skill_name: str, success: bool, latency: float, quality: float):
        super().__init__()
        self.event_type = DomainEventType.SKILL_COMPLETED
        self.goal_id = goal_id
        self.skill_id = skill_id
        self.skill_name = skill_name
        self.success = success
        self.latency_seconds = latency
        self.quality_score = quality
        self.metadata = {
            "skill_name": skill_name,
            "success": success,
            "latency_seconds": latency,
            "quality_score": quality,
        }


@dataclass
class ArtifactVerifiedEvent(DomainEvent):
    """Событие верификации артефакта"""
    verified_artifact_id: UUID = None  # type: ignore
    verification_status: str = ""
    quality_score: float = 0.0
    
    def __init__(self, artifact_id: UUID, goal_id: UUID, verification_status: str, quality_score: float):
        super().__init__()
        self.event_type = DomainEventType.ARTIFACT_VERIFIED
        self.verified_artifact_id = artifact_id
        self.goal_id = goal_id
        self.verification_status = verification_status
        self.quality_score = quality_score
        self.metadata = {
            "artifact_id": str(artifact_id),
            "verification_status": verification_status,
            "quality_score": quality_score,
        }


@dataclass
class PolicySelectedEvent(DomainEvent):
    """Событие выбора политики"""
    policy_name: str = ""
    goal_type: str = ""
    utility_score: float = 0.0
    
    def __init__(self, goal_id: UUID, policy_name: str, goal_type: str, utility_score: float):
        super().__init__()
        self.event_type = DomainEventType.POLICY_SELECTED
        self.goal_id = goal_id
        self.policy_name = policy_name
        self.goal_type = goal_type
        self.utility_score = utility_score
        self.metadata = {
            "policy_name": policy_name,
            "goal_type": goal_type,
            "utility_score": utility_score,
        }
