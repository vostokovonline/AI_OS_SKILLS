"""
Decision Events - Phase 1.5
Capture decision points for Strategy Mining and Experience Store.

These events capture WHY a decision was made, not just WHAT happened.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import List, Optional, Dict, Any


@dataclass(frozen=True)
class SkillCandidatesGenerated:
    """System generated candidate skills for evaluation"""
    goal_id: UUID
    requirements: Dict[str, Any]
    candidates: List[Dict[str, Any]]  # [{"skill_id", "score", "capabilities"}]
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())


@dataclass(frozen=True)
class SkillSelected:
    """System selected a skill from candidates"""
    goal_id: UUID
    skill_id: str
    candidates_count: int
    rejected_count: int
    selection_reason: str  # "capability_match", "fallback", "retry"
    confidence: float  # 0.0-1.0
    alternative_skills: List[str]  # What was NOT chosen
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())


@dataclass(frozen=True)
class SkillRetry:
    """System decided to retry with different skill/parameters"""
    goal_id: UUID
    original_skill: str
    retry_skill: str
    reason: str  # "verification_failed", "timeout", "error"
    attempt_number: int
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())


@dataclass(frozen=True)
class PlanGenerated:
    """System generated execution plan for goal"""
    goal_id: UUID
    steps: List[Dict[str, Any]]  # [{"step_type", "skill", "reason"}]
    strategy_name: Optional[str]  # e.g., "research_pipeline", "coding_flow"
    estimated_steps: int
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())


@dataclass(frozen=True)
class FallbackTriggered:
    """System fell back to alternative strategy"""
    goal_id: UUID
    primary_strategy: str
    fallback_strategy: str
    trigger_reason: str  # "skill_failed", "timeout", "error"
    recovery_successful: bool
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())


@dataclass(frozen=True)
class LLMModelSelected:
    """System selected LLM model for specific task"""
    goal_id: UUID
    task_type: str  # "reasoning", "generation", "analysis"
    selected_model: str
    alternative_models: List[str]
    selection_reason: str  # "cost", "speed", "quality", "fallback"
    estimated_cost_usd: float
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())
