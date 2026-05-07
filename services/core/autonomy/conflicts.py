"""
CONFLICT DETECTION v1.1
=======================

Epistemic consistency layer with LOCALIZED penalty.

KEY PRINCIPLE:
World cannot be X and NOT-X without penalty.
BUT penalty only affects goals whose patterns intersect with conflict.

v1.1 Changes:
- Localized conflict penalty (not global)
- Penalty only if goal pattern intersects conflict key
- Multiple penalty levels by intersection strength

CONFLICT INVARIANT:
If (subject_type, subject_id, predicate) same AND values differ
AND both confidences >= threshold
→ CONFLICT exists

LOCALIZED PENALTY MODEL:
goal_penalty = max(conflict_score for conflicts where pattern intersects)

A goal is only penalized if it cares about the conflicted proposition.

Author: AI-OS Team
Date: 2026-02-22
Version: 1.1.0
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional, Set
from collections import defaultdict
from datetime import datetime


@dataclass
class Conflict:
    """
    Detected conflict between propositions.
    
    Represents: X and NOT-X exist simultaneously in world state.
    """
    subject_type: str
    subject_id: str
    predicate: str
    propositions: List[Any]
    conflict_score: float
    
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.subject_type, self.subject_id, self.predicate)
    
    @property
    def values(self) -> List[Any]:
        return [p.value for p in self.propositions]
    
    @property
    def unique_values(self) -> set:
        return set(self.values)
    
    def intersects_pattern(self, pattern: Any) -> bool:
        """
        Check if this conflict intersects with a goal pattern.
        
        Intersection rules:
        - subject_type must match
        - predicate must match
        - if pattern has subject_id_pattern, conflict.subject_id must match it
        
        Args:
            pattern: GoalPattern object
            
        Returns:
            True if conflict affects this pattern
        """
        if pattern.subject_type != self.subject_type:
            return False
        
        if pattern.predicate != self.predicate:
            return False
        
        # If pattern has subject_id_pattern, check wildcard match
        if pattern.subject_id_pattern:
            import fnmatch
            if not fnmatch.fnmatch(self.subject_id, pattern.subject_id_pattern):
                return False
        
        return True
    
    def to_dict(self) -> Dict:
        return {
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "conflict_score": round(self.conflict_score, 4),
            "values": list(self.unique_values),
            "proposition_count": len(self.propositions),
            "propositions": [
                {
                    "id": str(p.id),
                    "value": p.value,
                    "confidence": round(p.confidence, 4)
                }
                for p in self.propositions
            ],
            "detected_at": self.detected_at
        }


@dataclass
class ConflictReport:
    """
    Full conflict analysis report with LOCALIZED penalties.
    """
    conflicts: List[Conflict]
    total_propositions: int
    conflicted_propositions: int
    
    # Index for fast lookup
    _conflicts_by_key: Dict[Tuple[str, str, str], Conflict] = field(default_factory=dict)
    
    def __post_init__(self):
        """Build index after initialization."""
        self._conflicts_by_key = {c.key: c for c in self.conflicts}
    
    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0
    
    @property
    def max_conflict_score(self) -> float:
        if not self.conflicts:
            return 0.0
        return max(c.conflict_score for c in self.conflicts)
    
    @property
    def global_penalty(self) -> float:
        """
        Global penalty (v1.0 behavior, deprecated).
        
        Use localized_penalty_for_patterns() instead.
        """
        return self.max_conflict_score
    
    def localized_penalty_for_patterns(self, patterns: List[Any]) -> float:
        """
        Calculate penalty for a goal based on its patterns.
        
        ONLY conflicts that intersect with patterns count.
        This makes penalty LOCAL, not global.
        
        Args:
            patterns: List of GoalPattern objects
            
        Returns:
            Penalty value in [0, 1]
        """
        if not self.conflicts or not patterns:
            return 0.0
        
        intersecting_scores = []
        
        for conflict in self.conflicts:
            for pattern in patterns:
                if conflict.intersects_pattern(pattern):
                    intersecting_scores.append(conflict.conflict_score)
                    break  # One match per conflict is enough
        
        if not intersecting_scores:
            return 0.0
        
        return max(intersecting_scores)
    
    def conflicts_for_patterns(self, patterns: List[Any]) -> List[Conflict]:
        """
        Get conflicts that intersect with given patterns.
        
        Args:
            patterns: List of GoalPattern objects
            
        Returns:
            List of intersecting conflicts
        """
        if not self.conflicts or not patterns:
            return []
        
        result = []
        for conflict in self.conflicts:
            for pattern in patterns:
                if conflict.intersects_pattern(pattern):
                    result.append(conflict)
                    break
        
        return result
    
    def to_dict(self) -> Dict:
        return {
            "has_conflicts": self.has_conflicts,
            "conflict_count": len(self.conflicts),
            "max_conflict_score": round(self.max_conflict_score, 4),
            "global_penalty": round(self.global_penalty, 4),
            "total_propositions": self.total_propositions,
            "conflicted_propositions": self.conflicted_propositions,
            "conflicts": [c.to_dict() for c in self.conflicts]
        }


class ConflictDetector:
    """
    Detects epistemic conflicts in world state.
    
    O(n) complexity. No SAT solver. No magic.
    
    Usage:
        detector = ConflictDetector(threshold=0.6)
        report = detector.detect(propositions)
        
        if report.has_conflicts:
            confidence *= (1 - report.penalty)
    """
    
    DEFAULT_THRESHOLD = 0.6
    
    def __init__(self, threshold: float = None):
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD
        self._last_report: ConflictReport = None
    
    def detect(self, propositions: List[Any]) -> ConflictReport:
        """
        Detect conflicts in propositions.
        
        Algorithm:
        1. Group by (subject_type, subject_id, predicate)
        2. For each group with multiple values:
           - Filter by confidence threshold
           - If values differ → CONFLICT
        
        Args:
            propositions: List of Proposition objects
            
        Returns:
            ConflictReport with all detected conflicts
        """
        if not propositions:
            self._last_report = ConflictReport(
                conflicts=[],
                total_propositions=0,
                conflicted_propositions=0
            )
            return self._last_report
        
        # Group propositions by key
        groups: Dict[Tuple[str, str, str], List[Any]] = defaultdict(list)
        
        for p in propositions:
            key = (p.subject_type, p.subject_id, p.predicate)
            groups[key].append(p)
        
        conflicts = []
        conflicted_ids = set()
        
        for (stype, sid, pred), props in groups.items():
            # Filter by confidence threshold
            strong = [p for p in props if p.confidence >= self.threshold]
            
            if len(strong) < 2:
                continue
            
            # Check for different values
            unique_values = set(p.value for p in strong)
            
            if len(unique_values) > 1:
                # Conflict detected
                conflict_score = min(p.confidence for p in strong)
                
                conflict = Conflict(
                    subject_type=stype,
                    subject_id=sid,
                    predicate=pred,
                    propositions=strong,
                    conflict_score=conflict_score
                )
                
                conflicts.append(conflict)
                
                # Track conflicted proposition IDs
                for p in strong:
                    conflicted_ids.add(p.id)
        
        self._last_report = ConflictReport(
            conflicts=conflicts,
            total_propositions=len(propositions),
            conflicted_propositions=len(conflicted_ids)
        )
        
        return self._last_report
    
    def get_last_report(self) -> ConflictReport:
        """Get last detection report."""
        return self._last_report
    
    def clear(self):
        """Clear last report."""
        self._last_report = None


def apply_conflict_penalty(
    confidence_true: float,
    uncertainty: float,
    report: ConflictReport,
    patterns: Optional[List[Any]] = None
) -> Tuple[float, float]:
    """
    Apply LOCALIZED conflict penalty to truth estimate.
    
    v1.1: Penalty only applies if patterns intersect with conflicts.
    v1.0: Global penalty (deprecated, use patterns parameter).
    
    Model:
    - final_confidence *= (1 - penalty)
    - uncertainty = 1 - confidence_true - confidence_false (self-consistent)
    
    Soft degradation. No hard rejection.
    
    Args:
        confidence_true: Original confidence
        uncertainty: Original uncertainty  
        report: Conflict report
        patterns: Optional list of GoalPattern objects for localized penalty
        
    Returns:
        (adjusted_confidence, adjusted_uncertainty)
    """
    if not report.has_conflicts:
        return confidence_true, uncertainty
    
    # LOCALIZED penalty: only if patterns intersect with conflicts
    if patterns:
        penalty = report.localized_penalty_for_patterns(patterns)
    else:
        # v1.0 fallback: global penalty (deprecated)
        penalty = report.global_penalty
    
    if penalty <= 0:
        return confidence_true, uncertainty
    
    # Apply penalty to confidence
    adjusted_confidence = confidence_true * (1 - penalty)
    
    # Self-consistent uncertainty model
    # uncertainty = 1 - conf_true - conf_false (if applicable)
    # For simplicity, just add penalty with soft cap
    adjusted_uncertainty = min(1.0, uncertainty + penalty * (1 - uncertainty))
    
    return adjusted_confidence, adjusted_uncertainty


# Global detector instance
_conflict_detector: ConflictDetector = None


def get_conflict_detector(threshold: float = None) -> ConflictDetector:
    """Get or create global conflict detector."""
    global _conflict_detector
    if _conflict_detector is None:
        _conflict_detector = ConflictDetector(threshold)
    return _conflict_detector


def reset_conflict_detector():
    """Reset global conflict detector."""
    global _conflict_detector
    _conflict_detector = None
