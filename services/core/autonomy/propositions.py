"""
PROPOSITIONS LAYER v1.1
=======================

Semantic abstraction between observations and goals.

KEY CONCEPT:
- Artifact = observation (raw data)
- Proposition = assertion about the world (interpreted)
- Goal = desired world state (evaluates propositions via patterns)

This is the foundation for AGI-style belief systems.

v1.1 Changes:
- Added GoalPattern for pattern-based goal evaluation
- Goals now query world state, not just aggregate their artifacts
- Pattern matching: subject_type + predicate + expected_value
- Added threading.Lock for concurrent access safety

Author: AI-OS Team
Date: 2026-02-22
Version: 1.1.0
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import RLock
from typing import Dict, List, Optional, Any, Set
from uuid import UUID, uuid4


class PropositionType(str, Enum):
    EXISTS = "exists"
    EQUALS = "equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    RESPONDS = "responds"
    COMPLETED = "completed"
    VERIFIED = "verified"


class MatchMode(str, Enum):
    ANY = "any"          # At least one proposition must match
    ALL = "all"          # All propositions must match
    AVERAGE = "average"  # Aggregate confidence from all matching
    COUNT = "count"      # Count matches, compare to threshold


@dataclass
class GoalPattern:
    """
    Defines what propositions a goal cares about.
    
    Instead of: "aggregate all artifacts for this goal"
    Now: "find propositions matching this pattern"
    
    This makes goals universal evaluators of world state.
    """
    subject_type: str           # "file", "api", "metric", "goal", "artifact"
    predicate: str              # "exists", "responds", "greater_than", etc.
    expected_value: Any         # True, 200, 1000, etc.
    
    match_mode: MatchMode = MatchMode.ANY
    confidence_threshold: float = 0.9
    min_count: int = 1          # For COUNT mode
    
    subject_id_pattern: Optional[str] = None  # Wildcard pattern for subject_id
    
    def matches_proposition(self, proposition: "Proposition") -> bool:
        """Check if a proposition matches this pattern."""
        if proposition.subject_type != self.subject_type:
            return False
        
        if proposition.predicate != self.predicate:
            return False
        
        if self.expected_value is not None:
            if proposition.value != self.expected_value:
                return False
        
        if self.subject_id_pattern:
            import fnmatch
            if not fnmatch.fnmatch(proposition.subject_id, self.subject_id_pattern):
                return False
        
        return True
    
    def to_dict(self) -> Dict:
        return {
            "subject_type": self.subject_type,
            "predicate": self.predicate,
            "expected_value": str(self.expected_value),
            "match_mode": self.match_mode.value,
            "confidence_threshold": self.confidence_threshold,
            "min_count": self.min_count,
            "subject_id_pattern": self.subject_id_pattern
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "GoalPattern":
        return cls(
            subject_type=data["subject_type"],
            predicate=data["predicate"],
            expected_value=data.get("expected_value"),
            match_mode=MatchMode(data.get("match_mode", "any")),
            confidence_threshold=data.get("confidence_threshold", 0.9),
            min_count=data.get("min_count", 1),
            subject_id_pattern=data.get("subject_id_pattern")
        )


@dataclass
class PatternMatchResult:
    """Result of matching a pattern against propositions."""
    pattern: GoalPattern
    matching_propositions: List["Proposition"]
    
    @property
    def count(self) -> int:
        return len(self.matching_propositions)
    
    @property
    def confidence(self) -> float:
        if not self.matching_propositions:
            return 0.0
        
        if self.pattern.match_mode == MatchMode.ANY:
            return max(p.confidence for p in self.matching_propositions)
        
        elif self.pattern.match_mode == MatchMode.ALL:
            return min(p.confidence for p in self.matching_propositions)
        
        elif self.pattern.match_mode == MatchMode.AVERAGE:
            return sum(p.confidence for p in self.matching_propositions) / len(self.matching_propositions)
        
        elif self.pattern.match_mode == MatchMode.COUNT:
            return 1.0 if self.count >= self.pattern.min_count else self.count / self.pattern.min_count
        
        return 0.0
    
    @property
    def satisfied(self) -> bool:
        return self.confidence >= self.pattern.confidence_threshold
    
    def to_dict(self) -> Dict:
        return {
            "pattern": self.pattern.to_dict(),
            "count": self.count,
            "confidence": round(self.confidence, 4),
            "satisfied": self.satisfied
        }


@dataclass
class Proposition:
    """
    Atomic assertion about the world.
    
    Structure: (subject_type, subject_id, predicate, value, confidence)
    
    Examples:
        ("file", "/report.pdf", "exists", True, 0.98)
        ("api", "payment", "responds", "200", 0.91)
        ("goal", "uuid", "completed", True, 0.85)
    """
    id: UUID
    subject_type: str
    subject_id: str
    predicate: str
    value: Any
    confidence: float
    
    source_artifact_id: Optional[UUID] = None
    source_goal_id: Optional[UUID] = None
    
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    @property
    def is_certain(self) -> bool:
        return self.confidence >= 0.95
    
    @property
    def is_uncertain(self) -> bool:
        return self.confidence < 0.5
    
    def matches(self, subject_type: str, subject_id: str, predicate: str) -> bool:
        """Check if proposition matches a query pattern."""
        return (
            self.subject_type == subject_type and
            self.subject_id == subject_id and
            self.predicate == predicate
        )
    
    def to_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "value": self.value,
            "confidence": round(self.confidence, 4),
            "source_artifact_id": str(self.source_artifact_id) if self.source_artifact_id else None,
            "source_goal_id": str(self.source_goal_id) if self.source_goal_id else None,
            "created_at": self.created_at
        }


class ArtifactToPropositionConverter:
    """
    Converts artifacts to propositions.
    
    This is the semantic bridge between raw observations and world assertions.
    """
    
    ARTIFACT_TYPE_MAPPING = {
        "FILE": "file",
        "KNOWLEDGE": "knowledge",
        "DATASET": "dataset",
        "REPORT": "report",
        "LINK": "link",
        "EXECUTION_LOG": "execution",
        "DECISION": "decision",
    }
    
    VERIFICATION_TO_CONFIDENCE = {
        "passed": 0.95,
        "partial": 0.6,
        "pending": 0.3,
        "failed": 0.1,
    }
    
    def convert(self, artifact: Any) -> List[Proposition]:
        """
        Convert artifact to propositions.
        
        Args:
            artifact: Artifact object with type, content_location, verification_status
            
        Returns:
            List of Propositions derived from the artifact
        """
        propositions = []
        
        artifact_type = getattr(artifact, 'type', 'FILE')
        artifact_id = getattr(artifact, 'id', uuid4())
        goal_id = getattr(artifact, 'goal_id', None)
        verification_status = getattr(artifact, 'verification_status', 'pending')
        content_location = getattr(artifact, 'content_location', '')
        
        subject_type = self.ARTIFACT_TYPE_MAPPING.get(artifact_type, "artifact")
        confidence = self.VERIFICATION_TO_CONFIDENCE.get(verification_status, 0.5)
        
        # Primary proposition: artifact exists
        propositions.append(Proposition(
            id=uuid4(),
            subject_type=subject_type,
            subject_id=str(artifact_id),
            predicate="exists",
            value=True,
            confidence=confidence,
            source_artifact_id=artifact_id,
            source_goal_id=goal_id
        ))
        
        # Secondary proposition: artifact verified
        if verification_status == "passed":
            propositions.append(Proposition(
                id=uuid4(),
                subject_type=subject_type,
                subject_id=str(artifact_id),
                predicate="verified",
                value=True,
                confidence=0.95,
                source_artifact_id=artifact_id,
                source_goal_id=goal_id
            ))
        
        # Goal completion proposition
        if goal_id:
            propositions.append(Proposition(
                id=uuid4(),
                subject_type="goal",
                subject_id=str(goal_id),
                predicate="has_evidence",
                value=artifact_type,
                confidence=confidence,
                source_artifact_id=artifact_id,
                source_goal_id=goal_id
            ))
        
        return propositions
    
    def convert_batch(self, artifacts: List[Any]) -> List[Proposition]:
        """Convert multiple artifacts to propositions."""
        all_propositions = []
        for artifact in artifacts:
            all_propositions.extend(self.convert(artifact))
        return all_propositions


class PatternMatcher:
    """
    Matches goal patterns against proposition store.
    
    This is the core of pattern-based goal evaluation.
    """
    
    def __init__(self, store: "PropositionStore"):
        self.store = store
    
    def match(self, pattern: GoalPattern) -> PatternMatchResult:
        """
        Find all propositions matching a pattern.
        
        Args:
            pattern: GoalPattern to match against
            
        Returns:
            PatternMatchResult with matching propositions and confidence
        """
        matching = []
        
        # Get propositions by subject_type (indexed)
        for prop in self.store.get_by_type(pattern.subject_type):
            if pattern.matches_proposition(prop):
                matching.append(prop)
        
        return PatternMatchResult(
            pattern=pattern,
            matching_propositions=matching
        )
    
    def match_patterns(self, patterns: List[GoalPattern]) -> List[PatternMatchResult]:
        """Match multiple patterns."""
        return [self.match(p) for p in patterns]


class PropositionStore:
    """
    In-memory proposition store with indexing.
    
    Thread-safe using RLock for concurrent access.
    For production: replace with proper database.
    """
    
    def __init__(self):
        self._lock = RLock()
        self._propositions: Dict[UUID, Proposition] = {}
        self._by_subject: Dict[str, List[UUID]] = {}
        self._by_goal: Dict[UUID, List[UUID]] = {}
        self._by_type: Dict[str, List[UUID]] = {}
    
    def add(self, proposition: Proposition):
        """Add proposition to store (thread-safe)."""
        with self._lock:
            self._propositions[proposition.id] = proposition
            
            key = f"{proposition.subject_type}:{proposition.subject_id}"
            if key not in self._by_subject:
                self._by_subject[key] = []
            self._by_subject[key].append(proposition.id)
            
            if proposition.source_goal_id:
                if proposition.source_goal_id not in self._by_goal:
                    self._by_goal[proposition.source_goal_id] = []
                self._by_goal[proposition.source_goal_id].append(proposition.id)
            
            if proposition.subject_type not in self._by_type:
                self._by_type[proposition.subject_type] = []
            self._by_type[proposition.subject_type].append(proposition.id)
    
    def get_by_goal(self, goal_id: UUID) -> List[Proposition]:
        """Get all propositions for a goal (thread-safe)."""
        with self._lock:
            ids = self._by_goal.get(goal_id, [])
            return [self._propositions[i] for i in ids if i in self._propositions]
    
    def get_by_subject(self, subject_type: str, subject_id: str) -> List[Proposition]:
        """Get all propositions for a subject (thread-safe)."""
        with self._lock:
            key = f"{subject_type}:{subject_id}"
            ids = self._by_subject.get(key, [])
            return [self._propositions[i] for i in ids if i in self._propositions]
    
    def get_by_type(self, subject_type: str) -> List[Proposition]:
        """Get all propositions for a subject type (thread-safe)."""
        with self._lock:
            ids = self._by_type.get(subject_type, [])
            return [self._propositions[i] for i in ids if i in self._propositions]
    
    def get_all(self) -> List[Proposition]:
        """Get all propositions (thread-safe snapshot)."""
        with self._lock:
            return list(self._propositions.values())
    
    def clear(self):
        """Clear all propositions (thread-safe)."""
        with self._lock:
            self._propositions.clear()
            self._by_subject.clear()
            self._by_goal.clear()
            self._by_type.clear()
    
    @property
    def count(self) -> int:
        with self._lock:
            return len(self._propositions)


# Default patterns for common goal types
DEFAULT_PATTERNS = {
    "file_exists": GoalPattern(
        subject_type="file",
        predicate="exists",
        expected_value=True,
        match_mode=MatchMode.ANY,
        confidence_threshold=0.9
    ),
    "api_healthy": GoalPattern(
        subject_type="api",
        predicate="responds",
        expected_value="200",
        match_mode=MatchMode.ALL,
        confidence_threshold=0.95
    ),
    "goal_evidenced": GoalPattern(
        subject_type="goal",
        predicate="has_evidence",
        expected_value=None,  # Any evidence type
        match_mode=MatchMode.COUNT,
        confidence_threshold=0.8,
        min_count=1
    ),
    "artifact_verified": GoalPattern(
        subject_type="artifact",
        predicate="verified",
        expected_value=True,
        match_mode=MatchMode.ANY,
        confidence_threshold=0.9
    ),
}


_proposition_store: Optional[PropositionStore] = None
_converter: Optional[ArtifactToPropositionConverter] = None
_matcher: Optional[PatternMatcher] = None


def get_proposition_store() -> PropositionStore:
    """Get or create global proposition store."""
    global _proposition_store
    if _proposition_store is None:
        _proposition_store = PropositionStore()
    return _proposition_store


def get_converter() -> ArtifactToPropositionConverter:
    """Get or create global converter."""
    global _converter
    if _converter is None:
        _converter = ArtifactToPropositionConverter()
    return _converter


def get_matcher() -> PatternMatcher:
    """Get or create global pattern matcher."""
    global _matcher
    if _matcher is None:
        _matcher = PatternMatcher(get_proposition_store())
    return _matcher


def reset_propositions():
    """Reset proposition store."""
    global _proposition_store, _matcher
    if _proposition_store:
        _proposition_store.clear()
    _proposition_store = PropositionStore()
    _matcher = None
