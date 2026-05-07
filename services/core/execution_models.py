"""
PHASE 1: Execution Tracking Models

Tracks goal executions and skill performance metrics.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, Integer, Boolean, Float, Text, JSON, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from database import Base


class GoalExecution(Base):
    """
    Tracks every goal execution with detailed metrics.

    PHASE 1: Foundation for analytics and skill performance tracking.
    """
    __tablename__ = "goal_execution_metrics"

    # Primary key
    execution_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # References
    goal_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    skill_id = Column(String(255), nullable=False, index=True)

    # Execution engine (v3 vs legacy)
    execution_engine = Column(String(50), index=True)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)

    # Outcome
    success = Column(Boolean, nullable=False, index=True)
    confidence = Column(Float)
    artifacts_count = Column(Integer, default=0)

    # Error tracking
    error_message = Column(Text)
    error_type = Column(String(255))

    # Goal snapshot
    goal_snapshot = Column(JSONB)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    # Constraints
    __table_args__ = (
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="execution_duration_check"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="execution_confidence_check"),
        CheckConstraint("artifacts_count >= 0", name="execution_artifacts_check"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "execution_id": str(self.execution_id),
            "goal_id": str(self.goal_id),
            "skill_id": self.skill_id,
            "execution_engine": self.execution_engine,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "confidence": self.confidence,
            "artifacts_count": self.artifacts_count,
            "error_type": self.error_type
        }


class SkillStats(Base):
    """
    Aggregated performance metrics for each skill.

    PHASE 1: Updated after every execution for skill ranking.
    """
    __tablename__ = "skill_performance_stats"

    # Primary key
    skill_id = Column(String(255), primary_key=True)

    # Execution counts
    total_executions = Column(Integer, default=0)
    successful_executions = Column(Integer, default=0)
    failed_executions = Column(Integer, default=0)

    # Latency metrics (milliseconds)
    avg_latency_ms = Column(Float)
    p50_latency_ms = Column(Float)
    p95_latency_ms = Column(Float)
    p99_latency_ms = Column(Float)

    # Quality metrics
    avg_confidence = Column(Float)
    avg_artifacts_count = Column(Float)
    success_rate = Column(Float, index=True)

    # Timestamps
    last_execution_at = Column(DateTime(timezone=True))
    last_calculated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Trend data (last 100 executions)
    recent_success_rate = Column(Float)
    recent_avg_latency = Column(Float)

    # Constraints
    __table_args__ = (
        CheckConstraint("total_executions >= 0", name="skill_stats_total_check"),
        CheckConstraint("successful_executions >= 0", name="skill_stats_success_check"),
        CheckConstraint("failed_executions >= 0", name="skill_stats_failed_check"),
        CheckConstraint("avg_latency_ms IS NULL OR avg_latency_ms >= 0", name="skill_stats_latency_check"),
        CheckConstraint("avg_confidence IS NULL OR (avg_confidence >= 0 AND avg_confidence <= 1)", name="skill_stats_confidence_check"),
        CheckConstraint("success_rate IS NULL OR (success_rate >= 0 AND success_rate <= 1)", name="skill_stats_rate_check"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "skill_id": self.skill_id,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "avg_confidence": self.avg_confidence,
            "last_execution_at": self.last_execution_at.isoformat() if self.last_execution_at else None
        }
