"""
BELIEF STATE LAYER v1.0
=======================

Epistemic foundation for cognitive evaluation.

PRINCIPLE:
Knowledge is not binary. It's a distribution of support.

BELIEF STATE:
For each (subject_type, subject_id, predicate):
- support_true:  total confidence supporting True
- support_false: total confidence supporting False
- uncertainty:   remaining epistemic gap

KEY INSIGHT:
Conflict is not "penalty".
Conflict is when support_true ≈ support_false.
This naturally leads to uncertainty.

NO MORE PENALTY:
Goal evaluation reads BeliefState.probability(expected_value).
If world is conflicted, probability is low.
No artificial penalty needed.

MATHEMATICAL MODEL (v1 - simple normalization):
    total = support_true + support_false
    P(True)  = support_true  / total (if total > 0)
    P(False) = support_false / total (if total > 0)
    uncertainty = 1 - (P(True) + P(False))

Author: AI-OS Team
Date: 2026-02-22
Version: 1.0.0
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from datetime import datetime


@dataclass
class BeliefState:
    """
    Epistemic state for a single proposition key.
    
    Represents: What does the agent believe about (subject_type, subject_id, predicate)?
    
    Structure:
    - support_true: sum of confidences for value=True
    - support_false: sum of confidences for value=False
    - support_other: sum of confidences for other values
    - total_evidence: count of supporting propositions
    
    This is NOT a probability distribution.
    This is EVIDENCE AGGREGATION.
    """
    subject_type: str
    subject_id: str
    predicate: str
    
    support_true: float = 0.0
    support_false: float = 0.0
    support_other: float = 0.0
    other_values: Dict[Any, float] = field(default_factory=dict)
    
    total_evidence: int = 0
    proposition_ids: List[str] = field(default_factory=list)
    
    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.subject_type, self.subject_id, self.predicate)
    
    @property
    def total_support(self) -> float:
        """Total support across all values."""
        return self.support_true + self.support_false + self.support_other
    
    @property
    def has_evidence(self) -> bool:
        return self.total_evidence > 0
    
    @property
    def is_conflicted(self) -> bool:
        """
        Conflict exists when multiple values have significant support.
        
        Definition: support_true > 0 AND support_false > 0
        Or: len(other_values) > 1 with significant support
        """
        has_true = self.support_true > 0
        has_false = self.support_false > 0
        has_multiple_other = sum(1 for v in self.other_values.values() if v > 0.3) > 1
        
        return (has_true and has_false) or has_multiple_other
    
    @property
    def conflict_intensity(self) -> float:
        """
        How strong is the conflict?
        
        High when support is balanced between true/false.
        Low when one side dominates.
        """
        if self.support_true <= 0 or self.support_false <= 0:
            return 0.0
        
        # Balance = min/max, 1.0 = perfectly balanced (max conflict)
        min_support = min(self.support_true, self.support_false)
        max_support = max(self.support_true, self.support_false)
        
        return min_support / max_support if max_support > 0 else 0.0
    
    def probability(self, value: Any) -> float:
        """
        Probability-like measure for a specific value.
        
        This is normalized support, not true Bayesian probability.
        
        Args:
            value: Expected value (True, False, or arbitrary)
            
        Returns:
            Normalized support in [0, 1]
        """
        total = self.total_support
        if total <= 0:
            return 0.0
        
        if value is True:
            return self.support_true / total
        elif value is False:
            return self.support_false / total
        else:
            return self.other_values.get(value, 0.0) / total
    
    @property
    def probability_true(self) -> float:
        """P(True) normalized."""
        return self.probability(True)
    
    @property
    def probability_false(self) -> float:
        """P(False) normalized."""
        return self.probability(False)
    
    @property
    def uncertainty(self) -> float:
        """
        Epistemic uncertainty.
        
        High when:
        - No evidence
        - Conflicting evidence
        - Evidence spread across many values
        
        Low when:
        - Strong support for one value
        """
        if not self.has_evidence:
            return 1.0
        
        total = self.total_support
        if total <= 0:
            return 1.0
        
        # Find dominant support
        max_support = max(
            self.support_true,
            self.support_false,
            max(self.other_values.values()) if self.other_values else 0.0
        )
        
        # Uncertainty = 1 - dominance
        dominance = max_support / total
        return 1.0 - dominance
    
    @property
    def dominant_value(self) -> Optional[Any]:
        """Which value has most support?"""
        candidates = [
            (True, self.support_true),
            (False, self.support_false),
        ]
        for val, support in self.other_values.items():
            candidates.append((val, support))
        
        if not candidates:
            return None
        
        best_val, best_support = max(candidates, key=lambda x: x[1])
        return best_val if best_support > 0 else None
    
    @property
    def confidence(self) -> float:
        """
        How confident is the agent in the dominant value?
        
        Returns:
            confidence in [0, 1]
        """
        if not self.has_evidence:
            return 0.0
        
        return 1.0 - self.uncertainty
    
    def to_dict(self) -> Dict:
        return {
            "key": list(self.key),
            "support_true": round(self.support_true, 4),
            "support_false": round(self.support_false, 4),
            "support_other": round(self.support_other, 4),
            "other_values": {str(k): round(v, 4) for k, v in self.other_values.items()},
            "total_evidence": self.total_evidence,
            "probability_true": round(self.probability_true, 4),
            "probability_false": round(self.probability_false, 4),
            "uncertainty": round(self.uncertainty, 4),
            "confidence": round(self.confidence, 4),
            "is_conflicted": self.is_conflicted,
            "conflict_intensity": round(self.conflict_intensity, 4),
            "dominant_value": str(self.dominant_value) if self.dominant_value is not None else None
        }


@dataclass
class WorldBeliefState:
    """
    Complete belief state of the world.
    
    Maps each proposition key to its BeliefState.
    """
    belief_states: Dict[Tuple[str, str, str], BeliefState] = field(default_factory=dict)
    
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    @property
    def count(self) -> int:
        return len(self.belief_states)
    
    def get(self, subject_type: str, subject_id: str, predicate: str) -> Optional[BeliefState]:
        """Get belief state for a specific key."""
        return self.belief_states.get((subject_type, subject_id, predicate))
    
    def get_for_pattern(self, pattern: Any) -> List[BeliefState]:
        """
        Get all belief states matching a pattern.
        
        Args:
            pattern: GoalPattern object
            
        Returns:
            List of matching BeliefStates
        """
        results = []
        
        for state in self.belief_states.values():
            if state.subject_type != pattern.subject_type:
                continue
            if state.predicate != pattern.predicate:
                continue
            
            # Check subject_id pattern if specified
            if pattern.subject_id_pattern:
                import fnmatch
                if not fnmatch.fnmatch(state.subject_id, pattern.subject_id_pattern):
                    continue
            
            results.append(state)
        
        return results
    
    def aggregate_confidence(
        self, 
        pattern: Any, 
        expected_value: Any = None,
        match_mode: Any = None
    ) -> Tuple[float, float]:
        """
        Aggregate confidence across all beliefs matching a pattern.
        
        AGGREGATION MODES (logically consistent):
        
        ALL (conjunction): confidence = product(P_i)
            "All must be true" → probability multiplies
            
        ANY (disjunction): confidence = max(P_i)
            "At least one must be true" → best wins
            
        AVERAGE: confidence = mean(P_i)
            "Soft average" → balanced view
            
        COUNT: confidence = count / threshold
            "Need N items" → ratio based
        
        Args:
            pattern: GoalPattern object
            expected_value: Optional expected value to check
            match_mode: MatchMode enum (ALL, ANY, AVERAGE, COUNT)
            
        Returns:
            (confidence, uncertainty) tuple
        """
        states = self.get_for_pattern(pattern)
        
        if not states:
            return 0.0, 1.0
        
        # Calculate probabilities for each state
        if expected_value is not None:
            probs = [s.probability(expected_value) for s in states]
            uncertainties = [s.uncertainty for s in states]
        else:
            probs = [s.confidence for s in states]
            uncertainties = [s.uncertainty for s in states]
        
        if not probs:
            return 0.0, 1.0
        
        # Import MatchMode if available
        try:
            from autonomy.propositions import MatchMode
            mode = match_mode if match_mode else MatchMode.ANY
        except:
            # Fallback if MatchMode not available
            mode = None
        
        # AGGREGATION BASED ON MODE
        if mode and hasattr(mode, 'value'):
            mode_str = mode.value if hasattr(mode, 'value') else str(mode)
        else:
            mode_str = "any"
        
        if mode_str == "all":
            # Product: ALL must be true → confidence = product
            import math
            confidence = math.prod(probs) if probs else 0.0
            uncertainty = 1.0 - confidence
            
        elif mode_str == "any":
            # Max: ANY must be true → confidence = best
            confidence = max(probs) if probs else 0.0
            # Uncertainty = uncertainty of best match
            if probs:
                best_idx = probs.index(max(probs))
                uncertainty = uncertainties[best_idx]
            else:
                uncertainty = 1.0
                
        elif mode_str == "average":
            # Mean: balanced view
            confidence = sum(probs) / len(probs) if probs else 0.0
            uncertainty = sum(uncertainties) / len(uncertainties) if uncertainties else 1.0
            
        elif mode_str == "count":
            # Count-based: how many satisfy threshold
            min_count = getattr(pattern, 'min_count', 1)
            threshold = getattr(pattern, 'confidence_threshold', 0.5)
            satisfied = sum(1 for p in probs if p >= threshold)
            confidence = min(1.0, satisfied / min_count) if min_count > 0 else 0.0
            uncertainty = 1.0 - confidence
            
        else:
            # Default: ANY (max)
            confidence = max(probs) if probs else 0.0
            uncertainty = min(uncertainties) if uncertainties else 1.0
        
        return confidence, uncertainty
    
    @property
    def conflicted_keys(self) -> List[Tuple[str, str, str]]:
        """Get all keys with conflicts."""
        return [k for k, v in self.belief_states.items() if v.is_conflicted]
    
    def to_dict(self) -> Dict:
        return {
            "count": self.count,
            "conflicted_count": len(self.conflicted_keys),
            "created_at": self.created_at,
            "belief_states": {
                f"{k[0]}:{k[1]}:{k[2]}": v.to_dict()
                for k, v in self.belief_states.items()
            }
        }


class BeliefStateBuilder:
    """
    Builds belief states from propositions.
    
    This replaces ConflictDetector as the epistemic foundation.
    
    Algorithm:
    1. Group propositions by (subject_type, subject_id, predicate)
    2. Aggregate support for each value
    3. Return WorldBeliefState
    """
    
    def __init__(self, min_support_threshold: float = 0.3):
        """
        Args:
            min_support_threshold: Ignore propositions with confidence below this
        """
        self.min_support_threshold = min_support_threshold
    
    def build(self, propositions: List[Any]) -> WorldBeliefState:
        """
        Build world belief state from propositions.
        
        Args:
            propositions: List of Proposition objects
            
        Returns:
            WorldBeliefState with all belief states
        """
        # Group by key
        groups: Dict[Tuple[str, str, str], List[Any]] = defaultdict(list)
        
        for p in propositions:
            if p.confidence < self.min_support_threshold:
                continue
            key = (p.subject_type, p.subject_id, p.predicate)
            groups[key].append(p)
        
        # Build belief states
        belief_states = {}
        
        for (stype, sid, pred), props in groups.items():
            state = BeliefState(
                subject_type=stype,
                subject_id=sid,
                predicate=pred
            )
            
            for p in props:
                state.total_evidence += 1
                state.proposition_ids.append(str(p.id))
                
                if p.value is True:
                    state.support_true += p.confidence
                elif p.value is False:
                    state.support_false += p.confidence
                else:
                    # Arbitrary value
                    state.support_other += p.confidence
                    if p.value not in state.other_values:
                        state.other_values[p.value] = 0.0
                    state.other_values[p.value] += p.confidence
            
            belief_states[(stype, sid, pred)] = state
        
        return WorldBeliefState(belief_states=belief_states)


# Global builder
_belief_builder: Optional[BeliefStateBuilder] = None


def get_belief_builder() -> BeliefStateBuilder:
    """Get or create global belief builder."""
    global _belief_builder
    if _belief_builder is None:
        _belief_builder = BeliefStateBuilder()
    return _belief_builder


def reset_belief_builder():
    """Reset global belief builder."""
    global _belief_builder
    _belief_builder = None
