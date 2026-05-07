"""
EXECUTION POLICY - Skill Selection and Execution Strategy
=========================================================

Extracts skill selection logic from GoalExecutorV2 into separate layer.
Enables:
- A/B testing of different selection strategies
- Policy learning over time
- Easy swapping of selection algorithms

ARCHITECTURE:
    GoalExecutorV2 (orchestration)
        ↓
    ExecutionPolicy.select_skill(goal, requirements)
        ↓
    Skill executes
        ↓
    ExecutionPolicy.finalize(execution_result)
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class SkillNotFoundError(Exception):
    """Raised when no suitable skill can be found for requirements."""
    pass


@dataclass
class ExecutionContext:
    """Context for execution decisions."""
    goal_id: str
    goal_title: str
    goal_type: str
    capabilities: List[str]
    required_artifacts: List[str]
    attempt: int = 1
    previous_failures: int = 0


@dataclass
class ExecutionResult:
    """Result of skill execution."""
    success: bool
    skill_id: str
    skill_name: str
    confidence: float
    artifacts_count: int
    duration_ms: int
    error: Optional[str] = None
    evaluation_passed: Optional[bool] = None


class ExecutionPolicy(ABC):
    """
    Base class for execution policies.
    
    Defines HOW the system selects skills and handles execution.
    """
    
    @abstractmethod
    def select_skill(
        self,
        requirements: Dict[str, Any],
        context: ExecutionContext,
        available_skills: List[Any]
    ) -> Optional[Any]:
        """
        Select appropriate skill based on requirements and context.
        
        Args:
            requirements: Parsed requirements (capabilities, artifacts)
            context: Execution context
            available_skills: List of available skills
            
        Returns:
            Selected skill or None
        """
        pass
    
    @abstractmethod
    def should_retry(
        self,
        result: ExecutionResult,
        attempt: int,
        max_attempts: int = 3
    ) -> bool:
        """
        Determine if execution should be retried.
        
        Args:
            result: Previous execution result
            attempt: Current attempt number
            max_attempts: Maximum attempts allowed
            
        Returns:
            True if should retry
        """
        pass
    
    @abstractmethod
    def select_fallback(
        self,
        failed_skill: Any,
        requirements: Dict[str, Any],
        available_skills: List[Any]
    ) -> Optional[Any]:
        """
        Select fallback skill when primary fails.
        
        Args:
            failed_skill: Skill that failed
            requirements: Original requirements
            available_skills: Available skills
            
        Returns:
            Fallback skill or None
        """
        pass
    
    def finalize(
        self,
        goal_id: str,
        skill: Any,
        result: ExecutionResult,
        execution_context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Finalize execution - record analytics, update stats.
        
        This is the SINGLE POINT where all execution data is recorded.
        
        Args:
            goal_id: Goal ID
            skill: Selected skill
            result: Execution result
            execution_context: Execution context
            
        Returns:
            Dict with finalization metadata
        """
        # This will be implemented to call analytics
        return {
            "goal_id": goal_id,
            "skill_id": skill.id if skill else "none",
            "success": result.success,
            "recorded": True
        }


class DefaultExecutionPolicy(ExecutionPolicy):
    """
    Default execution policy - capability + artifact matching.
    
    Current implementation moved from GoalExecutorV2.
    """
    
    def select_skill(
        self,
        requirements: Dict[str, Any],
        context: ExecutionContext,
        available_skills: List[Any]
    ) -> Optional[Any]:
        """Select skill with scoring based on capability match."""
        
        required_capabilities = requirements.get("capabilities", [])
        required_artifacts = requirements.get("artifacts", [])
        
        if not available_skills:
            raise SkillNotFoundError(
                f"No skills available for capabilities: {required_capabilities}"
            )
        
        scored_skills = []
        
        for skill in available_skills:
            if not skill or not hasattr(skill, 'capabilities'):
                continue
            
            skill_caps = getattr(skill, 'capabilities', [])
            skill_artifacts = getattr(skill, 'produces_artifacts', [])
            
            score = 0
            matched_caps = []
            missed_caps = []
            
            # Score capability matches
            for req_cap in required_capabilities:
                if req_cap in skill_caps:
                    score += 5
                    matched_caps.append(req_cap)
                elif req_cap in ['research', 'web-research', 'search']:
                    score -= 2
                    missed_caps.append(req_cap)
            
            # Score artifact type matches
            for req_art in required_artifacts:
                if req_art in skill_artifacts:
                    score += 3
            
            # Penalize generic skills
            skill_name = getattr(skill, 'id', '')
            if 'echo' in skill_name.lower():
                score -= 10
            
            # Bonus for exact match
            if matched_caps and len(matched_caps) == len(required_capabilities):
                score += 5
            
            if score > 0:
                scored_skills.append((score, skill, matched_caps, missed_caps))
        
        if not scored_skills:
            raise SkillNotFoundError(
                f"No skills match required capabilities: {required_capabilities}"
            )
        
        # Sort by score
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        
        selected = scored_skills[0][1]
        
        logger.info(
            "skill_selected_by_policy",
            skill_id=getattr(selected, 'id', 'unknown'),
            score=scored_skills[0][0],
            candidates=len(scored_skills)
        )
        
        return selected
    
    def should_retry(
        self,
        result: ExecutionResult,
        attempt: int,
        max_attempts: int = 3
    ) -> bool:
        """Retry if not success and attempts remain."""
        if result.success:
            return False
        if attempt >= max_attempts:
            return False
        
        # Don't retry on certain errors
        if result.error and any(x in result.error.lower() for x in ['timeout', 'not found', 'invalid']):
            return False
        
        return True
    
    def select_fallback(
        self,
        failed_skill: Any,
        requirements: Dict[str, Any],
        available_skills: List[Any]
    ) -> Optional[Any]:
        """Select fallback - try next best skill.
        
        NO EchoSkill fallback - raise error to signal capability gap.
        This forces the system to learn new strategies instead of falling back.
        """
        if not available_skills:
            raise SkillNotFoundError(
                f"No fallback skills available after {getattr(failed_skill, 'id', 'unknown')}"
            )
        
        failed_id = getattr(failed_skill, 'id', '') if failed_skill else ''
        
        # Find alternative skills
        alternatives = [
            s for s in available_skills
            if getattr(s, 'id', '') != failed_id
            and 'echo' not in getattr(s, 'id', '').lower()
        ]
        
        if not alternatives:
            raise SkillNotFoundError(
                f"No suitable fallback for failed skill: {failed_id}"
            )
        
        # Simple fallback: use first alternative
        return alternatives[0]


class LearningExecutionPolicy(ExecutionPolicy):
    """
    Execution policy that learns from history.
    
    Considers:
    - Historical success rate of skills
    - Average latency
    - Confidence patterns
    """
    
    def __init__(self):
        self._skill_history: Dict[str, Dict[str, Any]] = {}
    
    def select_skill(
        self,
        requirements: Dict[str, Any],
        context: ExecutionContext,
        available_skills: List[Any]
    ) -> Optional[Any]:
        """Select skill considering historical performance."""
        from canonical_skills.echo import EchoSkill
        
        # Use default policy for now
        default_policy = DefaultExecutionPolicy()
        selected = default_policy.select_skill(requirements, context, available_skills)
        
        if not selected:
            return EchoSkill()
        
        # Boost score based on historical success
        skill_id = getattr(selected, 'id', 'unknown')
        history = self._skill_history.get(skill_id, {})
        
        if history:
            success_rate = history.get('success_rate', 0.5)
            avg_latency = history.get('avg_latency_ms', 1000)
            
            logger.info(
                "skill_selected_with_history",
                skill_id=skill_id,
                success_rate=success_rate,
                avg_latency=avg_latency
            )
        
        return selected
    
    def should_retry(self, result: ExecutionResult, attempt: int, max_attempts: int = 3) -> bool:
        """Use default retry logic."""
        default_policy = DefaultExecutionPolicy()
        return default_policy.should_retry(result, attempt, max_attempts)
    
    def select_fallback(self, failed_skill: Any, requirements: Dict[str, Any], available_skills: List[Any]) -> Optional[Any]:
        """Use default fallback logic."""
        default_policy = DefaultExecutionPolicy()
        return default_policy.select_fallback(failed_skill, requirements, available_skills)
    
    def record_execution(self, skill_id: str, success: bool, duration_ms: int, confidence: float):
        """Record execution for learning."""
        if skill_id not in self._skill_history:
            self._skill_history[skill_id] = {
                'total': 0,
                'successes': 0,
                'total_duration': 0,
                'total_confidence': 0
            }
        
        h = self._skill_history[skill_id]
        h['total'] += 1
        if success:
            h['successes'] += 1
        h['total_duration'] += duration_ms
        h['total_confidence'] += confidence
        
        h['success_rate'] = h['successes'] / h['total']
        h['avg_latency_ms'] = h['total_duration'] / h['total']
        h['avg_confidence'] = h['total_confidence'] / h['total']


# Global policy instances
_default_policy = DefaultExecutionPolicy()
_learning_policy = LearningExecutionPolicy()

# Current active policy
_active_policy = _default_policy


def get_execution_policy() -> ExecutionPolicy:
    """Get current execution policy."""
    return _active_policy


def set_execution_policy(policy: ExecutionPolicy):
    """Set active execution policy."""
    global _active_policy
    _active_policy = policy
    logger.info("execution_policy_changed", policy=type(policy).__name__)


def use_learning_policy():
    """Switch to learning policy."""
    set_execution_policy(_learning_policy)


def use_default_policy():
    """Switch to default policy."""
    set_execution_policy(_default_policy)
