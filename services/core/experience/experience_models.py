"""
Experience Models - Core of Learning Loop

Every execution becomes a training example.
This is how AI-OS learns from experience.

Architecture:
    Execution → Experience → SkillStats → Better Skill Selection
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from database import Base


class Experience(Base):
    """
    Single execution record - the atom of learning.

    Each execution creates ONE experience row.
    This becomes training data for skill evolution.
    """

    __tablename__ = "experiences"

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Timestamp
    created_at = Column(DateTime(timezone=True), nullable=False, index=True, default=datetime.utcnow)

    # Goal reference
    goal_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Task classification (CRITICAL for skill comparison)
    task_type = Column(String(100), nullable=False, index=True)

    # Skill used
    skill_id = Column(String(255), nullable=False, index=True)

    # Outcome
    success = Column(Boolean, nullable=False, index=True)
    confidence = Column(Float)

    # Performance
    latency_ms = Column(Integer, nullable=False)

    # Error tracking
    error_type = Column(String(255))
    error_message = Column(Text)

    # Additional context (renamed from 'metadata' to avoid SQLAlchemy reserved word)
    extra_metadata = Column(JSON, default={})

    # Relationships
    # goal = relationship("Goal", back_populates="experiences")
    # NOTE: Commented out to avoid circular import.
    # Relationship defined in models.py Goal class when needed.

    def __repr__(self):
        return f"<Experience {self.task_type} | {self.skill_id} | {'✓' if self.success else '✗'}>"

    @property
    def is_high_quality(self) -> bool:
        """High quality = successful + confident"""
        return self.success and (self.confidence or 0) >= 0.7

    @property
    def is_fast(self) -> bool:
        """Fast = under 1 second"""
        return self.latency_ms < 1000


class SkillStats(Base):
    """
    Aggregated skill performance memory.

    This is the system's "brain" for skill selection.
    Updated after every experience.

    Composite key: (skill_id, task_type)
    """

    __tablename__ = "skill_stats"

    # Composite primary key
    skill_id = Column(String(255), primary_key=True)
    task_type = Column(String(100), primary_key=True)

    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)

    # Performance metrics (computed)
    success_rate = Column(Float, nullable=False, default=0.0)
    avg_latency_ms = Column(Float, nullable=False, default=0.0)
    avg_confidence = Column(Float, nullable=False, default=0.0)

    # Recent performance (last 10 executions)
    recent_success_rate = Column(Float)
    recent_avg_latency = Column(Float)

    # Metadata
    first_used_at = Column(DateTime(timezone=True))
    last_used_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SkillStats {self.skill_id}@{self.task_type} | {self.success_rate:.1%} | {self.usage_count} uses>"

    @property
    def is_reliable(self) -> bool:
        """Reliable = used 10+ times + success rate >= 80%"""
        return self.usage_count >= 10 and self.success_rate >= 0.8

    @property
    def is_new(self) -> bool:
        """New = used less than 5 times"""
        return self.usage_count < 5

    @property
    def latency_score(self) -> float:
        """
        Convert latency to score (0-1).
        Lower latency = higher score.
        """
        # Inverse: latency 0ms = 1.0, latency 5000ms = 0.0
        return max(0.0, 1.0 - (self.avg_latency_ms / 5000.0))

    def compute_score(
        self,
        success_weight: float = 0.5,
        confidence_weight: float = 0.2,
        latency_weight: float = 0.2,
        usage_weight: float = 0.1
    ) -> float:
        """
        Compute composite skill score.

        Weights:
        - 50% success rate (most important)
        - 20% confidence
        - 20% latency (inverse - faster is better)
        - 10% usage count (prefer proven skills)
        """
        # Success rate score
        success_score = self.success_rate

        # Confidence score (0-1)
        confidence_score = self.avg_confidence

        # Latency score (0-1, faster is better)
        latency_score = self.latency_score

        # Usage score (0-1, log scale - diminishes after 100 uses)
        usage_score = min(1.0, self.usage_count / 100.0)

        # Weighted composite
        score = (
            success_weight * success_score +
            confidence_weight * confidence_score +
            latency_weight * latency_score +
            usage_weight * usage_score
        )

        return score


# Add relationship to Goal model (need to import this in models.py)
# This is a circular import workaround - add this to models.py:
# from experience.experience_models import Experience
# Goal.experiences = relationship("Experience", back_populates="goal")
