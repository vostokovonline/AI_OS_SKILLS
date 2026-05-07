"""
Skill Evolution Loop - Data Models

Модели для:
- Pattern Extraction
- Composite Skills
- Evolution Tracking
- Skill Graph
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, Integer, Float, Text, JSON, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from database import Base


class SkillPattern(Base):
    """
    Обнаруженный паттерн execution chains.

    Пример:
        pattern_id = "research_summarize_write"
        skill_sequence = ["web_research", "summarize", "write_file"]
        frequency = 45
        avg_success_rate = 0.91
    """
    __tablename__ = "skill_patterns"

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Identification
    pattern_id = Column(String(255), unique=True, nullable=False, index=True)
    skill_sequence = Column(JSON, nullable=False)  # ["skill1", "skill2", ...]

    # Statistics
    frequency = Column(Integer, default=1)
    avg_success_rate = Column(Float)
    avg_duration_ms = Column(Float)
    avg_confidence = Column(Float)

    # Artifact production
    common_artifact_types = Column(JSON)

    # Timestamps
    discovered_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        CheckConstraint("frequency >= 0", name="pattern_frequency_check"),
        CheckConstraint(
            "avg_success_rate IS NULL OR (avg_success_rate >= 0 AND avg_success_rate <= 1)",
            name="pattern_success_rate_check"
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "skill_sequence": self.skill_sequence,
            "frequency": self.frequency,
            "avg_success_rate": self.avg_success_rate,
            "avg_duration_ms": self.avg_duration_ms,
            "score": self.frequency * (self.avg_success_rate or 0)
        }


class CompositeSkill(Base):
    """
    Сгенерированный composite skill.

    Пример:
        skill_id = "research_summarize_write_v1"
        component_skills = ["web_research", "summarize", "write_file"]
        execution_strategy = "sequential"
        status = "testing"
        improvement_over_baseline = 0.15  # +15% better
    """
    __tablename__ = "composite_skills"

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Identification
    skill_id = Column(String(255), unique=True, nullable=False)
    version = Column(Integer, nullable=False, default=1)

    # Composition
    component_skills = Column(JSON, nullable=False)
    execution_strategy = Column(String(50), nullable=False)

    # Status lifecycle
    status = Column(String(50), nullable=False)

    # Metrics from benchmarking
    success_rate = Column(Float)
    avg_latency_ms = Column(Float)
    avg_cost_tokens = Column(Float)

    # Evolution metrics
    improvement_over_baseline = Column(Float)
    statistical_significance = Column(Float)

    # Version tracking
    parent_pattern_id = Column(PG_UUID(as_uuid=True), ForeignKey("skill_patterns.id", ondelete="SET NULL"))
    baseline_skill_id = Column(String(255))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    promoted_at = Column(DateTime(timezone=True))
    deprecated_at = Column(DateTime(timezone=True))

    # Extra metadata
    extra_data = Column(JSON)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "success_rate IS NULL OR (success_rate >= 0 AND success_rate <= 1)",
            name="composite_success_rate_check"
        ),
        CheckConstraint(
            "status IN ('candidate', 'testing', 'active', 'deprecated', 'archived')",
            name="composite_status_check"
        ),
        CheckConstraint(
            "execution_strategy IN ('sequential', 'parallel', 'conditional', 'loop')",
            name="composite_strategy_check"
        ),
        CheckConstraint(
            "improvement_over_baseline IS NULL OR improvement_over_baseline >= -1",
            name="composite_improvement_check"
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "component_skills": self.component_skills,
            "execution_strategy": self.execution_strategy,
            "status": self.status,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "improvement_over_baseline": self.improvement_over_baseline,
            "statistical_significance": self.statistical_significance
        }


class SkillEvolutionLog(Base):
    """
    История evolution решений.

    Пример:
        event_type = "promoted"
        candidate_skill_id = "research_summarize_write_v2"
        baseline_skill_id = "manual_chain"
        improvement_score = 0.23  # +23% improvement
        reason = "Significant improvement in speed and success rate"
    """
    __tablename__ = "skill_evolution_log"

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Event
    event_type = Column(String(50), nullable=False)

    # Skills involved
    candidate_skill_id = Column(String(255))
    baseline_skill_id = Column(String(255))

    # Evolution metrics
    improvement_score = Column(Float)
    statistical_significance = Column(Float)
    sample_size = Column(Integer)

    # Decision reason
    reason = Column(Text)
    decision_metadata = Column(JSON)

    # Timestamp
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('pattern_discovered', 'candidate_created', 'benchmark_started', "
            "'benchmark_completed', 'promoted', 'rejected', 'deprecated', 'archived')",
            name="evolution_event_type_check"
        ),
        CheckConstraint(
            "improvement_score IS NULL OR improvement_score >= -1",
            name="evolution_improvement_check"
        ),
    )


class SkillGraphNode(Base):
    """
    Node в Skill Graph.

    Представляет skill (primitive, composite, или generated).
    """
    __tablename__ = "skill_graph_nodes"

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Node identification
    skill_id = Column(String(255), unique=True, nullable=False)
    node_type = Column(String(50), nullable=False)  # primitive, composite, generated

    # Metrics
    total_executions = Column(Integer, default=0)
    success_rate = Column(Float)
    avg_latency_ms = Column(Float)

    # Graph position
    depth_level = Column(Integer)  # 0 = atomic/primitive

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "node_type IN ('primitive', 'composite', 'generated')",
            name="graph_node_type_check"
        ),
    )


class SkillGraphEdge(Base):
    """
    Edge в Skill Graph.

    Представляет переход от одного skill к другому.

    Пример:
        from_skill = "web_research"
        to_skill = "summarize"
        weight = 0.7  # 70% chance
        transition_count = 45
        success_rate = 0.95
    """
    __tablename__ = "skill_graph_edges"

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Edge identification
    from_skill = Column(String(255), nullable=False)
    to_skill = Column(String(255), nullable=False)

    # Weight metrics
    weight = Column(Float, default=0.0)
    transition_count = Column(Integer, default=1)
    success_rate = Column(Float)
    avg_latency_ms = Column(Float)

    # Context
    discovered_from_pattern = Column(PG_UUID(as_uuid=True), ForeignKey("skill_patterns.id", ondelete="SET NULL"))

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Constraints
    __table_args__ = (
        CheckConstraint("weight >= 0 AND weight <= 1", name="edge_weight_check"),
        CheckConstraint("from_skill != to_skill", name="edge_not_self_loop"),
    )


class PatternDiscoveryRequest(Base):
    """
    Запрос на обнаружение паттернов.

    Используется для планирования batch jobs.
    """
    __tablename__ = "pattern_discovery_requests"

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Request parameters
    lookback_executions = Column(Integer, default=100)
    min_frequency = Column(Integer, default=5)
    min_success_rate = Column(Float, default=0.8)

    # Status
    status = Column(String(50), default="pending")  # pending, running, completed, failed

    # Results
    patterns_found = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # Error tracking
    error_message = Column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="discovery_status_check"
        ),
        CheckConstraint(
            "min_success_rate IS NULL OR (min_success_rate >= 0 AND min_success_rate <= 1)",
            name="discovery_success_rate_check"
        ),
    )
