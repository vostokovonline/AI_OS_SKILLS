"""
Experience Service - Learning from Past Executions
=================================================

CRITICAL for AGI: Enables system to learn from experience.

Responsibility:
    - Store execution experiences
    - Retrieve similar past experiences
    - Recommend strategies based on history
    - Track success patterns

Author: AI-OS AGI Architecture
Date: 2026-03-10
Phase: AGI Component 1
"""

from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger

logger = get_logger(__name__)


class OutcomeType(str, Enum):
    """Types of execution outcomes"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ExperienceRecord:
    """
    Single execution experience record.

    What the agent learned from one execution.
    """
    id: UUID = field(default_factory=uuid4)

    # Context
    goal_id: UUID = None
    goal_title: str = ""
    goal_type: str = ""
    goal_domains: List[str] = field(default_factory=list)

    # Strategy used
    strategy_name: str = ""
    strategy_params: Dict[str, Any] = field(default_factory=dict)

    # Execution
    execution_type: str = ""  # "atomic" | "complex" | "agent_graph"
    duration_ms: int = 0
    artifacts_count: int = 0

    # Outcome
    outcome: OutcomeType = OutcomeType.SUCCESS
    success_score: float = 0.0  # 0.0 to 1.0
    error_message: str = ""

    # Meta
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: UUID = None

    # Learning signals
    should_repeat: bool = False  # Would use this strategy again?
    confidence: float = 0.5  # How confident in this assessment?

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "goal_id": str(self.goal_id) if self.goal_id else None,
            "goal_title": self.goal_title,
            "goal_type": self.goal_type,
            "goal_domains": self.goal_domains,
            "strategy_name": self.strategy_name,
            "strategy_params": self.strategy_params,
            "execution_type": self.execution_type,
            "duration_ms": self.duration_ms,
            "artifacts_count": self.artifacts_count,
            "outcome": self.outcome.value,
            "success_score": self.success_score,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "user_id": str(self.user_id) if self.user_id else None,
            "should_repeat": self.should_repeat,
            "confidence": self.confidence
        }


# TODO: Create actual database table
# CREATE TABLE experiences (
#     id UUID PRIMARY KEY,
#     goal_id UUID,
#     goal_title TEXT,
#     goal_type VARCHAR(50),
#     goal_domains JSONB,
#     strategy_name VARCHAR(100),
#     strategy_params JSONB,
#     execution_type VARCHAR(50),
#     duration_ms INTEGER,
#     artifacts_count INTEGER,
#     outcome VARCHAR(20),
#     success_score FLOAT,
#     error_message TEXT,
#     created_at TIMESTAMPTZ,
#     user_id UUID,
#     should_repeat BOOLEAN,
#     confidence FLOAT
# );


class ExperienceService:
    """
    Service for managing execution experiences.

    Enables AGI-like learning:
    - "What worked before?"
    - "What should I avoid?"
    - "Which strategy is best?"
    """

    def __init__(self):
        # In-memory storage for now (TODO: move to DB)
        self._experiences: Dict[UUID, ExperienceRecord] = {}
        self._goal_index: Dict[str, List[UUID]] = {}  # goal_title → experience_ids

    async def store(
        self,
        goal_id: UUID,
        goal_title: str,
        goal_type: str,
        strategy_name: str,
        execution_type: str,
        duration_ms: int,
        artifacts_count: int,
        outcome: OutcomeType,
        success_score: float,
        error_message: str = "",
        goal_domains: List[str] = None,
        strategy_params: Dict[str, Any] = None,
        user_id: UUID = None,
        should_repeat: bool = False,
        confidence: float = 0.5
    ) -> ExperienceRecord:
        """
        Store a new execution experience.

        Args:
            goal_id: Goal that was executed
            goal_title: Title for similarity matching
            goal_type: Type classification
            strategy_name: Strategy used
            execution_type: Type of execution
            duration_ms: Execution time
            artifacts_count: Artifacts produced
            outcome: What happened
            success_score: 0.0 to 1.0
            error_message: Error if any
            goal_domains: Domain tags
            strategy_params: Strategy parameters
            user_id: User context
            should_repeat: Would use this strategy again?
            confidence: How confident?

        Returns:
            ExperienceRecord: Stored record
        """
        record = ExperienceRecord(
            goal_id=goal_id,
            goal_title=goal_title,
            goal_type=goal_type,
            goal_domains=goal_domains or [],
            strategy_name=strategy_name,
            strategy_params=strategy_params or {},
            execution_type=execution_type,
            duration_ms=duration_ms,
            artifacts_count=artifacts_count,
            outcome=outcome,
            success_score=success_score,
            error_message=error_message,
            user_id=user_id,
            should_repeat=should_repeat,
            confidence=confidence
        )

        # Store in memory (TODO: in database)
        self._experiences[record.id] = record

        # Index by goal title
        title_key = goal_title.lower()
        if title_key not in self._goal_index:
            self._goal_index[title_key] = []
        self._goal_index[title_key].append(record.id)

        logger.info(
            "experience_stored",
            experience_id=str(record.id),
            goal_title=goal_title,
            outcome=outcome.value,
            success_score=success_score
        )

        return record

    async def find_similar(
        self,
        goal_title: str,
        goal_type: Optional[str] = None,
        goal_domains: Optional[List[str]] = None,
        max_results: int = 10,
        min_success_score: float = 0.0
    ) -> List[ExperienceRecord]:
        """
        Find similar past experiences.

        Args:
            goal_title: Title to match against
            goal_type: Filter by type
            goal_domains: Filter by domains
            max_results: Max results to return
            min_success_score: Minimum success threshold

        Returns:
            List[ExperienceRecord]: Similar experiences, sorted by success_score
        """
        # Simple similarity matching (TODO: use vector embeddings)
        title_key = goal_title.lower()

        # Find matching experiences
        similar_ids = []
        for key, ids in self._goal_index.items():
            if title_key in key or key in title_key:
                similar_ids.extend(ids)

        # Get records
        records = [
            self._experiences[eid]
            for eid in similar_ids
            if eid in self._experiences
        ]

        # Filter by type
        if goal_type:
            records = [r for r in records if r.goal_type == goal_type]

        # Filter by domains
        if goal_domains:
            records = [
                r for r in records
                if any(d in r.goal_domains for d in goal_domains)
            ]

        # Filter by success score
        records = [r for r in records if r.success_score >= min_success_score]

        # Sort by success_score (descending)
        records.sort(key=lambda r: r.success_score, reverse=True)

        return records[:max_results]

    async def get_best_strategy(
        self,
        goal_title: str,
        goal_type: str,
        goal_domains: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Recommend best strategy based on past experience.

        Args:
            goal_title: Goal to execute
            goal_type: Type of goal
            goal_domains: Domain tags

        Returns:
            dict: {strategy_name, strategy_params, confidence, expected_score}
            or None if no similar experiences found
        """
        # Find successful similar experiences
        similar = await self.find_similar(
            goal_title=goal_title,
            goal_type=goal_type,
            goal_domains=goal_domains,
            min_success_score=0.5
        )

        if not similar:
            return None

        # Group by strategy
        strategies: Dict[str, List[ExperienceRecord]] = {}
        for exp in similar:
            if exp.should_repeat:  # Only consider strategies agent would use again
                key = exp.strategy_name
                if key not in strategies:
                    strategies[key] = []
                strategies[key].append(exp)

        # Find best strategy (highest average success_score)
        best_strategy = None
        best_avg_score = 0.0

        for strategy_name, exps in strategies.items():
            avg_score = sum(e.success_score for e in exps) / len(exps)
            if avg_score > best_avg_score:
                best_avg_score = avg_score
                best_strategy = {
                    "strategy_name": strategy_name,
                    "strategy_params": exps[0].strategy_params,
                    "confidence": min(0.9, len(exs) * 0.1),  # More data = more confidence
                    "expected_success_score": best_avg_score,
                    "sample_size": len(exps)
                }

        if best_strategy:
            logger.info(
                "best_strategy_found",
                goal_title=goal_title,
                strategy=best_strategy["strategy_name"],
                expected_score=best_strategy["expected_success_score"],
                confidence=best_strategy["confidence"]
            )

        return best_strategy

    async def get_statistics(
        self,
        user_id: Optional[UUID] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get experience statistics.

        Args:
            user_id: Filter by user (optional)
            days: Lookback period

        Returns:
            dict: Statistics summary
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Filter experiences
        records = [
            r for r in self._experiences.values()
            if r.created_at >= cutoff
        ]

        if user_id:
            records = [r for r in records if r.user_id == user_id]

        # Calculate stats
        total = len(records)
        if total == 0:
            return {
                "total_experiences": 0,
                "avg_success_score": 0.0,
                "outcome_counts": {},
                "strategy_counts": {}
            }

        avg_score = sum(r.success_score for r in records) / total

        outcome_counts = {}
        for outcome in OutcomeType:
            count = sum(1 for r in records if r.outcome == outcome)
            outcome_counts[outcome.value] = count

        strategy_counts = {}
        for r in records:
            name = r.strategy_name
            strategy_counts[name] = strategy_counts.get(name, 0) + 1

        return {
            "total_experiences": total,
            "avg_success_score": round(avg_score, 3),
            "outcome_counts": outcome_counts,
            "top_strategies": sorted(
                strategy_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }

    async def learn_from_execution(
        self,
        execution_result: Dict[str, Any],
        goal: "Goal"
    ):
        """
        Automatically extract learning from execution result.

        Called after each execution to build experience database.

        Args:
            execution_result: Result from GoalExecutionService
            goal: Goal that was executed
        """
        # Determine outcome
        if execution_result.get("success"):
            if execution_result.get("artifacts"):
                outcome = OutcomeType.SUCCESS
                success_score = 0.9
            else:
                outcome = OutcomeType.PARTIAL
                success_score = 0.5
        else:
            error = execution_result.get("error_message", "")
            if "timeout" in error.lower():
                outcome = OutcomeType.TIMEOUT
            else:
                outcome = OutcomeType.ERROR
            success_score = 0.1

        # Determine strategy
        strategy_name = execution_result.get("execution_type", "unknown")

        # Store experience
        await self.store(
            goal_id=goal.id,
            goal_title=goal.title,
            goal_type=goal.goal_type,
            goal_domains=goal.domains or [],
            strategy_name=strategy_name,
            execution_type=execution_result.get("execution_type", ""),
            duration_ms=execution_result.get("duration_ms", 0),
            artifacts_count=len(execution_result.get("artifacts", [])),
            outcome=outcome,
            success_score=success_score,
            error_message=execution_result.get("error_message", ""),
            should_repeat=(success_score >= 0.5),
            confidence=0.7
        )

        logger.info(
            "learned_from_execution",
            goal_id=str(goal.id),
            outcome=outcome.value,
            strategy=strategy_name
        )


# Singleton instance
experience_service = ExperienceService()
