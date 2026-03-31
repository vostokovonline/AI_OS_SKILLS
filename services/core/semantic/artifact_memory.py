"""
Artifact-Driven Memory System v5

Enables:
- Plan reuse: store and retrieve successful plan structures
- Step replacement: learn better step sequences
- Pre-execution adaptation: modify plans before running
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time
import hashlib


@dataclass
class PlanArtifact:
    """A learned plan structure for a goal type."""
    goal_type: str
    plan_steps: List[str]
    
    success_count: int = 0
    fail_count: int = 0
    last_used: float = field(default_factory=time.time)
    
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.0
    
    def total_runs(self) -> int:
        return self.success_count + self.fail_count


@dataclass
class StepArtifact:
    """Cached execution result for a step."""
    step_type: str
    input_hash: str
    result: Any
    success: bool
    strategy_used: str
    timestamp: float = field(default_factory=time.time)
    usage_count: int = 0


class ArtifactMemory:
    """
    Memory system for plan reuse and step replacement.
    
    Key concepts:
    - Plan artifacts: successful plan structures for goal types
    - Step artifacts: cached execution results
    - Step replacements: learned better sequences
    """
    
    # Thresholds
    MIN_SUCCESS_RATE = 0.6  # Only reuse plans above this
    MIN_REPLACEMENT_COUNT = 2  # Only replace after this many observations
    PLAN_TTL_HOURS = 24  # Plan becomes stale after this
    STEP_TTL_SECONDS = 300  # Step result TTL
    
    def __init__(self):
        # Plan artifacts: goal_type -> List[PlanArtifact]
        self._plan_db: Dict[str, List[PlanArtifact]] = {}
        
        # Step artifacts: key -> StepArtifact
        self._step_db: Dict[str, StepArtifact] = {}
        
        # Step replacements: old_step -> {new_step: count}
        self._replacements: Dict[str, Dict[str, int]] = {}
        
        # Statistics
        self._stats = {
            "plans_stored": 0,
            "plans_reused": 0,
            "replacements_made": 0,
            "steps_cached": 0
        }
    
    # =========================================================================
    # PLAN ARTIFACTS
    # =========================================================================
    
    def get_best_plan(self, goal_type: str) -> Optional[PlanArtifact]:
        """Get the best plan for a goal type based on success rate + recency."""
        plans = self._plan_db.get(goal_type, [])
        
        if not plans:
            return None
        
        now = time.time()
        
        # Sort by: success_rate DESC, then recency DESC
        def plan_score(p: PlanArtifact) -> tuple:
            # Decay old plans
            age_hours = (now - p.last_used) / 3600
            recency = 1.0 / (1.0 + age_hours)
            return (p.success_rate() * 0.8 + recency * 0.2, p.last_used)
        
        plans.sort(key=plan_score, reverse=True)
        
        # Only return if above threshold
        best = plans[0]
        if best.success_rate() >= self.MIN_SUCCESS_RATE and best.total_runs() >= 2:
            self._stats["plans_reused"] += 1
            return best
        
        return None
    
    def store_plan(self, goal_type: str, steps: List[str], success: bool) -> None:
        """Store a plan execution result."""
        if len(steps) < 1:
            return  # Don't store trivial plans
        
        plans = self._plan_db.setdefault(goal_type, [])
        
        # Find existing plan
        for p in plans:
            if p.plan_steps == steps:
                # Update existing
                if success:
                    p.success_count += 1
                else:
                    p.fail_count += 1
                p.last_used = time.time()
                return
        
        # Create new artifact
        artifact = PlanArtifact(
            goal_type=goal_type,
            plan_steps=list(steps),
            success_count=1 if success else 0,
            fail_count=0 if success else 1,
            last_used=time.time()
        )
        plans.append(artifact)
        self._stats["plans_stored"] += 1
        
        # Cleanup old plans
        if len(plans) > 20:
            plans.sort(key=lambda p: p.last_used, reverse=True)
            self._plan_db[goal_type] = plans[:20]
    
    def get_plan_suggestions(self, goal_type: str) -> List[str]:
        """Get alternative plan structures for a goal."""
        plans = self._plan_db.get(goal_type, [])
        if not plans:
            return []
        
        # Return top 3 plans (excluding the best one)
        plans.sort(key=lambda p: p.success_rate(), reverse=True)
        return [p.plan_steps for p in plans[1:4] if p.total_runs() >= 2]
    
    # =========================================================================
    # STEP ARTIFACTS
    # =========================================================================
    
    def _make_step_key(self, step_type: str, input_data: Any) -> str:
        """Create a unique key for step caching."""
        data_str = str(input_data) if input_data else ""
        raw = f"{step_type}:{data_str}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    def get_step_artifact(self, step_type: str, input_data: Any = None) -> Optional[StepArtifact]:
        """Get cached step result if valid."""
        key = self._make_step_key(step_type, input_data)
        artifact = self._step_db.get(key)
        
        if not artifact:
            return None
        
        # Check TTL
        age = time.time() - artifact.timestamp
        if age > self.STEP_TTL_SECONDS:
            del self._step_db[key]
            return None
        
        # Check success rate (only use reliable cache)
        if not artifact.success:
            return None
        
        artifact.usage_count += 1
        self._stats["steps_cached"] += 1
        return artifact
    
    def store_step_artifact(self, step_type: str, input_data: Any, 
                           result: Any, success: bool, strategy: str) -> None:
        """Store step execution result."""
        if not success:
            return  # Don't cache failures
        
        key = self._make_step_key(step_type, input_data)
        
        self._step_db[key] = StepArtifact(
            step_type=step_type,
            input_hash=key,
            result=result,
            success=True,
            strategy_used=strategy,
            timestamp=time.time(),
            usage_count=1
        )
        
        # Enforce max size
        if len(self._step_db) > 1000:
            # Remove oldest
            oldest = min(self._step_db.keys(), 
                        key=lambda k: self._step_db[k].timestamp)
            del self._step_db[oldest]
    
    # =========================================================================
    # STEP REPLACEMENTS
    # =========================================================================
    
    def register_replacement(self, old_step: str, new_step: str) -> None:
        """Register that new_step is preferred over old_step."""
        replacements = self._replacements.setdefault(old_step, {})
        replacements[new_step] = replacements.get(new_step, 0) + 1
    
    def get_replacement(self, step: str) -> Optional[str]:
        """Get preferred replacement for a step."""
        replacements = self._replacements.get(step, {})
        
        if not replacements:
            return None
        
        # Only return if we have enough observations
        total = sum(replacements.values())
        if total < self.MIN_REPLACEMENT_COUNT:
            return None
        
        # Return most common replacement
        return max(replacements.items(), key=lambda x: x[1])[0]
    
    def get_all_replacements(self) -> Dict[str, str]:
        """Get all learned replacements."""
        result = {}
        for old_step, replacements in self._replacements.items():
            best = self.get_replacement(old_step)
            if best:
                result[old_step] = best
        return result
    
    # =========================================================================
    # PLAN ADAPTATION (pre-execution)
    # =========================================================================
    
    def adapt_plan(self, base_plan: List[str]) -> List[str]:
        """Adapt a plan by replacing steps with better alternatives."""
        adapted = []
        
        for step in base_plan:
            replacement = self.get_replacement(step)
            
            if replacement:
                adapted.append(replacement)
            else:
                adapted.append(step)
        
        return adapted
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            **self._stats,
            "unique_goals": len(self._plan_db),
            "cached_steps": len(self._step_db),
            "replacement_rules": len(self._replacements)
        }
    
    def reset(self) -> None:
        """Reset all memory (for testing)."""
        self._plan_db.clear()
        self._step_db.clear()
        self._replacements.clear()
        self._stats = {
            "plans_stored": 0,
            "plans_reused": 0,
            "replacements_made": 0,
            "steps_cached": 0
        }


# Global singleton instance
_artifact_memory: Optional[ArtifactMemory] = None


def get_artifact_memory() -> ArtifactMemory:
    """Get or create global artifact memory instance."""
    global _artifact_memory
    if _artifact_memory is None:
        _artifact_memory = ArtifactMemory()
    return _artifact_memory