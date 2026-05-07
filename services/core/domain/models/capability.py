"""
Domain Models - Capability & Skill
====================================
Чистые доменные модели для capability graph и skill system.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Set
from uuid import UUID, uuid4


class CapabilityType(Enum):
    """Типы capabilities"""
    RESEARCH = "research"
    CODE_GENERATION = "code_generation"
    DATA_EXTRACTION = "data_extraction"
    SUMMARIZATION = "summarization"
    WEB_SEARCH = "web_search"
    FILE_WRITE = "file_write"
    EXECUTION = "execution"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    REASONING = "reasoning"
    CREATIVE = "creative"
    COMMUNICATION = "communication"


class SkillStatus(Enum):
    """Статус навыка"""
    EXPERIMENTAL = "experimental"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    TRAINING = "training"


@dataclass
class Capability:
    """
    Абстрактная способность которую может выполнять система.
    Не привязана к конкретной реализации.
    """
    id: str  # e.g., "research", "code_generation"
    name: str
    description: str
    
    # Иерархия
    parent_capability: Optional[str] = None
    child_capabilities: List[str] = field(default_factory=list)
    
    # Метаданные
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Вес при выборе (重要性)
    default_weight: float = 1.0
    
    def is_leaf(self) -> bool:
        return len(self.child_capabilities) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_capability": self.parent_capability,
            "child_capabilities": self.child_capabilities,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "default_weight": self.default_weight,
        }


@dataclass
class SkillManifest:
    """
    Манифест навыка - контракт между domain и infrastructure.
    Определяет что навык делает, но не как.
    """
    id: str
    name: str
    
    # Capabilities
    capabilities: List[str]  # Какие capabilities реализует
    
    # Интерфейс
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    
    # Версионирование
    version: str = "1.0.0"
    deprecated: bool = False
    
    # Метаданные
    description: str = ""
    examples: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "capabilities": self.capabilities,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "version": self.version,
            "deprecated": self.deprecated,
            "description": self.description,
            "examples": self.examples,
        }


@dataclass
class SkillMetrics:
    """
    Метрики производительности навыка.
    Основа для skill selection и evolution.
    """
    skill_id: str
    
    # Основные метрики
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    
    # Время
    avg_latency_seconds: float = 0.0
    min_latency_seconds: float = 0.0
    max_latency_seconds: float = 0.0
    
    # Качество
    avg_quality_score: float = 0.0
    avg_confidence: float = 0.0
    
    # Стоимость
    avg_cost: float = 0.0
    
    # Время жизни метрик
    last_updated: datetime = field(default_factory=datetime.utcnow)
    sample_count: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions
    
    @property
    def failure_rate(self) -> float:
        return 1.0 - self.success_rate
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "avg_latency_seconds": self.avg_latency_seconds,
            "min_latency_seconds": self.min_latency_seconds,
            "max_latency_seconds": self.max_latency_seconds,
            "avg_quality_score": self.avg_quality_score,
            "avg_confidence": self.avg_confidence,
            "avg_cost": self.avg_cost,
            "last_updated": self.last_updated.isoformat(),
            "sample_count": self.sample_count,
        }


@dataclass
class Skill:
    """
    Полный навык - манифест + метрики + реализация.
    """
    manifest: SkillManifest
    metrics: SkillMetrics
    
    # Implementation reference (not in domain)
    implementation_path: str = ""
    
    # Lifecycle
    status: SkillStatus = SkillStatus.EXPERIMENTAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "metrics": self.metrics.to_dict(),
            "implementation_path": self.implementation_path,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class CapabilityGraph:
    """
    Граф capabilities - отображает связи между capabilities.
    """
    nodes: Dict[str, Capability] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)  # parent -> children
    
    def add_capability(self, capability: Capability) -> None:
        self.nodes[capability.id] = capability
        if capability.parent_capability:
            if capability.parent_capability not in self.edges:
                self.edges[capability.parent_capability] = []
            self.edges[capability.parent_capability].append(capability.id)
    
    def get_capability(self, capability_id: str) -> Optional[Capability]:
        return self.nodes.get(capability_id)
    
    def get_children(self, capability_id: str) -> List[Capability]:
        children_ids = self.edges.get(capability_id, [])
        return [self.nodes[cid] for cid in children_ids if cid in self.nodes]
    
    def get_parent(self, capability_id: str) -> Optional[Capability]:
        capability = self.nodes.get(capability_id)
        if capability and capability.parent_capability:
            return self.nodes.get(capability.parent_capability)
        return None
    
    def get_skills_for_capability(self, capability_id: str, skills: List[Skill]) -> List[Skill]:
        """Найти все навыки которые реализуют данную capability"""
        return [
            s for s in skills
            if capability_id in s.manifest.capabilities
        ]
    
    def get_all_ancestors(self, capability_id: str) -> List[Capability]:
        """Получить все родительские capabilities"""
        ancestors = []
        current = self.get_parent(capability_id)
        while current:
            ancestors.append(current)
            current = self.get_parent(current.id)
        return ancestors
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": self.edges,
        }
