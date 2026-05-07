"""
World Model - Understanding Environment State
============================================

CRITICAL for AGI: Enables agent to reason about environment.

Responsibility:
    - Track entity states
    - Model relationships between entities
    - Predict effects of actions
    - Enable counterfactual reasoning

Author: AI-OS AGI Architecture
Date: 2026-03-10
Phase: AGI Component 2
"""

from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from logging_config import get_logger

logger = get_logger(__name__)


class EntityType(str, Enum):
    """Types of entities in the world"""
    RESOURCE = "resource"  # Servers, databases, APIs
    TASK = "task"  # Running tasks, processes
    AGENT = "agent"  # AI agents, services
    USER = "user"  # Human users
    SYSTEM = "system"  # System state
    CONSTRAINT = "constraint"  # Limits, rules


class RelationType(str, Enum):
    """Types of relationships between entities"""
    DEPENDS_ON = "depends_on"  # A depends on B
    ENABLES = "enables"  # A enables B
    CONFLICTS_WITH = "conflicts_with"  # A conflicts with B
    PART_OF = "part_of"  # A is part of B
    CONTAINS = "contains"  # A contains B


@dataclass
class EntityState:
    """
    State of an entity in the world.

    NOT beliefs (epistemic) - actual or observed state.
    """
    id: UUID = field(default_factory=uuid4)
    entity_type: EntityType = EntityType.RESOURCE
    name: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Temporal
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Confidence (observations can be uncertain)
    confidence: float = 1.0  # 0.0 to 1.0

    # Provenance
    source: str = ""  # Where did this info come from?
    source_artifact_id: Optional[UUID] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "entity_type": self.entity_type.value,
            "name": self.name,
            "attributes": self.attributes,
            "observed_at": self.observed_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "confidence": self.confidence,
            "source": self.source,
            "source_artifact_id": str(self.source_artifact_id) if self.source_artifact_id else None
        }


@dataclass
class Relation:
    """Relationship between two entities"""
    id: UUID = field(default_factory=uuid4)
    from_entity: str = ""  # Entity name
    to_entity: str = ""
    relation_type: RelationType = RelationType.DEPENDS_ON
    strength: float = 1.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "from": self.from_entity,
            "to": self.to_entity,
            "type": self.relation_type.value,
            "strength": self.strength,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Prediction:
    """
    Prediction of action effect.

    Enables counterfactual reasoning: "What if I do X?"
    """
    action: str = ""
    expected_effect: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "expected_effect": self.expected_effect,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


class WorldModel:
    """
    Model of the environment state.

    Separated from BeliefState:
    - BeliefState = what agent believes (epistemic)
    - WorldModel = what environment is like (ontological)

    Critical for AGI because it enables:
    - Counterfactual reasoning
    - Planning with environment constraints
    - Understanding cause-effect
    """

    def __init__(self):
        # Entity storage: name → EntityState
        self._entities: Dict[str, EntityState] = {}

        # Relations: (from, to, type) → Relation
        self._relations: Dict[Tuple[str, str, RelationType], Relation] = {}

        # Entity index by type
        self._entities_by_type: Dict[EntityType, Dict[str, EntityState]] = {
            et: {} for et in EntityType
        }

    # ========================================================================
    # ENTITY MANAGEMENT
    # ========================================================================

    async def update_entity(
        self,
        name: str,
        entity_type: EntityType,
        attributes: Dict[str, Any],
        confidence: float = 1.0,
        source: str = "",
        source_artifact_id: Optional[UUID] = None
    ) -> EntityState:
        """
        Update or create entity state.

        Args:
            name: Unique entity name
            entity_type: Type of entity
            attributes: Current state attributes
            confidence: Observation confidence
            source: Where info came from
            source_artifact_id: Source artifact

        Returns:
            EntityState: Updated state
        """
        now = datetime.now(timezone.utc)

        if name in self._entities:
            # Update existing
            entity = self._entities[name]
            entity.attributes.update(attributes)
            entity.last_updated = now
            entity.confidence = min(entity.confidence, confidence)  # Use lowest confidence
        else:
            # Create new
            entity = EntityState(
                name=name,
                entity_type=entity_type,
                attributes=attributes,
                confidence=confidence,
                source=source,
                source_artifact_id=source_artifact_id
            )
            self._entities[name] = entity
            self._entities_by_type[entity_type][name] = entity

        logger.debug(
            "entity_updated",
            name=name,
            entity_type=entity_type.value,
            attributes=attributes
        )

        return entity

    async def get_entity(self, name: str) -> Optional[EntityState]:
        """Get entity state by name"""
        return self._entities.get(name)

    async def get_entities_by_type(
        self,
        entity_type: EntityType
    ) -> List[EntityState]:
        """Get all entities of a type"""
        return list(self._entities_by_type[entity_type].values())

    async def query_entities(
        self,
        filter_fn: callable
    ) -> List[EntityState]:
        """
        Query entities with custom filter.

        Args:
            filter_fn: Function(entity) → bool

        Returns:
            List[EntityState]: Matching entities
        """
        return [e for e in self._entities.values() if filter_fn(e)]

    # ========================================================================
    # RELATION MANAGEMENT
    # ========================================================================

    async def add_relation(
        self,
        from_entity: str,
        to_entity: str,
        relation_type: RelationType,
        strength: float = 1.0,
        metadata: Dict[str, Any] = None
    ) -> Relation:
        """
        Add relationship between entities.

        Args:
            from_entity: Source entity name
            to_entity: Target entity name
            relation_type: Type of relationship
            strength: Relationship strength (0.0 to 1.0)
            metadata: Additional info

        Returns:
            Relation: Created relation
        """
        key = (from_entity, to_entity, relation_type)

        relation = Relation(
            from_entity=from_entity,
            to_entity=to_entity,
            relation_type=relation_type,
            strength=strength,
            metadata=metadata or {}
        )

        self._relations[key] = relation

        logger.debug(
            "relation_added",
            from_entity=from_entity,
            to_entity=to_entity,
            type=relation_type.value
        )

        return relation

    async def get_relations(
        self,
        entity_name: str,
        relation_type: Optional[RelationType] = None
    ) -> List[Relation]:
        """
        Get relations for an entity.

        Args:
            entity_name: Entity to query
            relation_type: Filter by type (optional)

        Returns:
            List[Relation]: Matching relations
        """
        relations = []
        for (from_e, to_e, rt), rel in self._relations.items():
            if from_e == entity_name or to_e == entity_name:
                if relation_type is None or rt == relation_type:
                    relations.append(rel)
        return relations

    # ========================================================================
    # PREDICTION & REASONING
    # ========================================================================

    async def predict_effect(
        self,
        action: str,
        context: Dict[str, Any] = None
    ) -> Prediction:
        """
        Predict effect of an action on world state.

        This enables counterfactual reasoning:
        "What will happen if I do X?"

        Args:
            action: Action description
            context: Current context

        Returns:
            Prediction: Expected effect with confidence
        """
        # TODO: Implement actual prediction logic
        # For now, simple heuristic-based prediction

        # Extract action type and target
        action_lower = action.lower()

        if "restart" in action_lower or "start" in action_lower:
            # Starting/restarting something
            target = self._extract_target(action)
            if target and target in self._entities:
                return Prediction(
                    action=action,
                    expected_effect={
                        "entity": target,
                        "status": "running",
                        "change": "started"
                    },
                    confidence=0.7,
                    reasoning=f"Action will start entity '{target}'"
                )

        elif "stop" in action_lower or "kill" in action_lower:
            target = self._extract_target(action)
            if target and target in self._entities:
                return Prediction(
                    action=action,
                    expected_effect={
                        "entity": target,
                        "status": "stopped",
                        "change": "stopped"
                    },
                    confidence=0.7,
                    reasoning=f"Action will stop entity '{target}'"
                )

        elif "create" in action_lower or "deploy" in action_lower:
            return Prediction(
                action=action,
                expected_effect={
                    "new_entity": True,
                    "change": "created"
                },
                confidence=0.5,
                reasoning="Action will create new entity"
            )

        # Default: uncertain
        return Prediction(
            action=action,
            expected_effect={"change": "unknown"},
            confidence=0.1,
            reasoning="Unable to predict effect"
        )

    def _extract_target(self, action: str) -> Optional[str]:
        """Extract target entity name from action"""
        # Simple heuristic: look for entity names
        words = action.split()
        for word in words:
            if word in self._entities:
                return word
        return None

    async def check_preconditions(
        self,
        action: str,
        context: Dict[str, Any] = None
    ) -> Tuple[bool, List[str]]:
        """
        Check if preconditions for action are met.

        Args:
            action: Action to check
            context: Current context

        Returns:
            Tuple[bool, List[str]]: (all_met, unmet_preconditions)
        """
        # TODO: Implement actual precondition checking
        # For now, simple checks

        unmet = []

        # Check if action mentions dependencies
        action_lower = action.lower()

        # Get relations for entities mentioned in action
        for entity_name in self._entities:
            if entity_name.lower() in action_lower:
                relations = await self.get_relations(
                    entity_name,
                    RelationType.DEPENDS_ON
                )

                for rel in relations:
                    dep_entity = rel.to_entity
                    if dep_entity not in self._entities:
                        unmet.append(f"Missing dependency: {dep_entity}")
                    else:
                        dep_state = self._entities[dep_entity].attributes
                        if dep_state.get("status") != "running":
                            unmet.append(f"Dependency not running: {dep_entity}")

        return (len(unmet) == 0, unmet)

    # ========================================================================
    # SNAPSHOT & RESTORE
    # ========================================================================

    def snapshot(self) -> Dict[str, Any]:
        """
        Create snapshot of world state.

        Useful for:
        - Rollback
        - Branching prediction
        - State comparison
        """
        return {
            "entities": {name: e.to_dict() for name, e in self._entities.items()},
            "relations": {key: r.to_dict() for key, r in self._relations.items()},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of world state"""
        return {
            "total_entities": len(self._entities),
            "entities_by_type": {
                et.value: len(entities)
                for et, entities in self._entities_by_type.items()
            },
            "total_relations": len(self._relations),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }


# Singleton instance
world_model = WorldModel()
