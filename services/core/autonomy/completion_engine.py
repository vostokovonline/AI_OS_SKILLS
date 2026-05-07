"""
COMPLETION ENGINE v2.0 - Cognitive Core
======================================

Truth-based goal evaluation with confidence scores.

ARCHITECTURE SHIFT v2.0:
- Status is VIEW, not stored truth
- Confidence ∈ [0,1], not boolean
- TruthState = TRUE | FALSE | UNCERTAIN
- Dependencies constrain confidence

RULE #1: Truth is estimated, not assigned.

    truth_estimate = completion_engine.evaluate(goal_id)
    status = truth_estimate.state  # derived from confidence

RULE #2: Confidence = evidence_weight / total_expected

RULE #3: Dependencies bound confidence:
    confidence(A) ≤ confidence(B) if A REQUIRES B

TRUTH MAPPING:
    confidence_true > 0.95  → TRUE
    confidence_true < 0.05  → FALSE
    otherwise              → UNCERTAIN

GOAL TYPES:
    ATOMIC:     confidence from artifact evidence
    AGGREGATE:  confidence = min(children confidence)
    MANUAL:     confidence from DECISION artifact
    STRICT:     confidence from evaluator + evidence

Author: AI-OS Team
Date: 2026-02-22
Version: 2.0.0 - Cognitive Core Evolution
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger

logger = get_logger(__name__)


UNCERTAINTY_THRESHOLD = 0.4


class TruthState(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNCERTAIN = "uncertain"
    
    @classmethod
    def from_estimate(cls, confidence_true: float, uncertainty: float) -> "TruthState":
        """
        Determine truth state from confidence and uncertainty.
        
        Epistemic logic:
        - High uncertainty → UNCERTAIN (we don't know)
        - Low uncertainty + high confidence_true → TRUE
        - Low uncertainty + low confidence_true → FALSE
        - Medium uncertainty → UNCERTAIN
        
        This distinguishes:
        - "No evidence" (uncertain) from "Evidence against" (false)
        """
        if uncertainty > UNCERTAINTY_THRESHOLD:
            return cls.UNCERTAIN
        
        if confidence_true >= 0.6:
            return cls.TRUE
        elif confidence_true <= 0.1:
            return cls.FALSE
        else:
            return cls.UNCERTAIN


class CompletionStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    
    @classmethod
    def from_truth_state(cls, state: TruthState) -> "CompletionStatus":
        mapping = {
            TruthState.TRUE: cls.DONE,
            TruthState.FALSE: cls.FAILED,
            TruthState.UNCERTAIN: cls.PENDING,
        }
        return mapping[state]


class CompletionMode(str, Enum):
    ATOMIC = "atomic"
    AGGREGATE = "aggregate"
    MANUAL = "manual"
    STRICT = "strict"


@dataclass
class TruthEstimate:
    """
    Probabilistic truth estimate for a goal.
    
    Core AGI concept: truth is not binary.
    Agent has degree of belief.
    """
    confidence_true: float
    confidence_false: float
    uncertainty: float
    
    evidence_count: int = 0
    evidence_weight: float = 0.0
    dependency_penalty: float = 0.0
    
    @property
    def state(self) -> TruthState:
        return TruthState.from_estimate(self.confidence_true, self.uncertainty)
    
    @property
    def status(self) -> CompletionStatus:
        return CompletionStatus.from_truth_state(self.state)
    
    @property
    def is_certain(self) -> bool:
        return self.uncertainty < 0.1
    
    def to_dict(self) -> Dict:
        return {
            "confidence_true": round(self.confidence_true, 4),
            "confidence_false": round(self.confidence_false, 4),
            "uncertainty": round(self.uncertainty, 4),
            "state": self.state.value,
            "status": self.status.value,
            "evidence_count": self.evidence_count,
            "evidence_weight": round(self.evidence_weight, 4),
            "dependency_penalty": round(self.dependency_penalty, 4)
        }


class EvaluationContext:
    """
    Graph-aware evaluation context with caching.
    
    Prevents redundant evaluations in recursive goal hierarchies.
    
    Usage:
        ctx = EvaluationContext(session)
        result = await engine.evaluate(session, goal_id, ctx)
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._cache: Dict[str, Any] = {}
        self._in_progress: set = set()
        self._depth: int = 0
        self._max_depth: int = 100
    
    def get_cached(self, goal_id: UUID) -> Optional[Any]:
        return self._cache.get(str(goal_id))
    
    def set_cached(self, goal_id: UUID, result: Any):
        self._cache[str(goal_id)] = result
    
    def is_evaluating(self, goal_id: UUID) -> bool:
        return str(goal_id) in self._in_progress
    
    def begin_evaluating(self, goal_id: UUID) -> bool:
        if self._depth >= self._max_depth:
            return False
        self._in_progress.add(str(goal_id))
        self._depth += 1
        return True
    
    def end_evaluating(self, goal_id: UUID):
        self._in_progress.discard(str(goal_id))
        self._depth = max(0, self._depth - 1)
    
    @property
    def stats(self) -> Dict:
        return {
            "cached": len(self._cache),
            "in_progress": len(self._in_progress),
            "depth": self._depth
        }


@dataclass
class ArtifactSummary:
    artifact_id: UUID
    status: str
    artifact_type: str
    weight: float = 1.0
    description: Optional[str] = None


@dataclass
class ChildSummary:
    goal_id: UUID
    title: Optional[str] = None
    confidence_true: float = 0.0
    state: str = "uncertain"


@dataclass
class DependencySummary:
    goal_id: UUID
    relation_type: str
    constraint_satisfied: bool
    constraint_confidence: float


@dataclass
class CompletionResult:
    evaluated_goal_id: UUID
    truth_estimate: TruthEstimate
    
    completion_mode: CompletionMode
    is_atomic: bool
    
    reason: str
    
    evidence: List[ArtifactSummary] = field(default_factory=list)
    children_status: List[ChildSummary] = field(default_factory=list)
    dependencies: List[DependencySummary] = field(default_factory=list)
    
    strict_evaluator_result: Optional[Dict] = None
    manual_approval: Optional[bool] = None
    
    evaluated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    @property
    def computed_status(self) -> CompletionStatus:
        return self.truth_estimate.status
    
    @property
    def passed(self) -> bool:
        return self.truth_estimate.state == TruthState.TRUE
    
    def to_dict(self) -> Dict:
        return {
            "goal_id": str(self.evaluated_goal_id),
            "truth": self.truth_estimate.to_dict(),
            "computed_status": self.computed_status.value,
            "completion_mode": self.completion_mode.value,
            "is_atomic": self.is_atomic,
            "passed": self.passed,
            "reason": self.reason,
            "evidence": [
                {
                    "artifact_id": str(a.artifact_id),
                    "status": a.status,
                    "type": a.artifact_type,
                    "weight": a.weight
                }
                for a in self.evidence
            ],
            "children_status": [
                {
                    "goal_id": str(c.goal_id),
                    "confidence_true": round(c.confidence_true, 4),
                    "state": c.state
                }
                for c in self.children_status
            ],
            "dependencies": [
                {
                    "goal_id": str(d.goal_id),
                    "relation": d.relation_type,
                    "satisfied": d.constraint_satisfied,
                    "confidence": round(d.constraint_confidence, 4)
                }
                for d in self.dependencies
            ],
            "evaluated_at": self.evaluated_at
        }


class CompletionEngine:
    """
    Cognitive Core v2.0 - Truth-based goal evaluation.
    
    Key differences from v1.0:
    - Returns TruthEstimate, not just status
    - Confidence ∈ [0,1], not boolean
    - Dependencies affect confidence
    - Evidence has weight
    - EvaluationContext for graph caching
    
    Usage:
        engine = CompletionEngine()
        
        # Simple evaluation
        result = await engine.evaluate(session, goal_id)
        
        # With context (for hierarchies)
        ctx = EvaluationContext(session)
        result = await engine.evaluate(session, goal_id, ctx)
        
        if result.truth_estimate.state == TruthState.TRUE:
            # Agent believes goal is achieved
        elif result.truth_estimate.state == TruthState.FALSE:
            # Agent believes goal is impossible/failed
        else:
            # Agent is uncertain
    """
    
    CONFIDENCE_THRESHOLD_TRUE = 0.95
    CONFIDENCE_THRESHOLD_FALSE = 0.05
    
    ARTIFACT_WEIGHTS = {
        "FILE": 1.0,
        "KNOWLEDGE": 0.8,
        "DATASET": 1.0,
        "REPORT": 0.7,
        "LINK": 0.5,
        "EXECUTION_LOG": 0.6,
        "DECISION": 1.0,
    }
    
    def __init__(self):
        self._global_cache: Dict[str, CompletionResult] = {}
    
    async def evaluate(
        self,
        session: AsyncSession,
        goal_id: UUID,
        context: Optional[EvaluationContext] = None
    ) -> CompletionResult:
        """
        Evaluate goal truth state with confidence.
        
        Args:
            session: Database session
            goal_id: Goal to evaluate
            context: Optional EvaluationContext for graph caching
            
        Returns:
            CompletionResult with TruthEstimate
        """
        from models import Goal
        
        # Check cache first
        if context:
            cached = context.get_cached(goal_id)
            if cached:
                return cached
            
            # Detect cycles
            if context.is_evaluating(goal_id):
                logger.warning(
                    "evaluation_cycle_detected",
                    goal_id=str(goal_id)[:8]
                )
                return self._create_uncertain_result(goal_id, "Cycle detected in goal hierarchy")
        
        goal = await session.get(Goal, goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        
        # Mark as in-progress if context provided
        if context:
            if not context.begin_evaluating(goal_id):
                return self._create_uncertain_result(goal_id, "Max evaluation depth exceeded")
        
        try:
            is_atomic = goal.is_atomic
            completion_mode = self._determine_mode(goal)
            
            if is_atomic:
                result = await self._evaluate_atomic(session, goal)
            elif completion_mode == CompletionMode.AGGREGATE:
                result = await self._evaluate_aggregate(session, goal, context)
            elif completion_mode == CompletionMode.MANUAL:
                result = await self._evaluate_manual(session, goal)
            elif completion_mode == CompletionMode.STRICT:
                result = await self._evaluate_strict(session, goal)
            else:
                result = await self._evaluate_atomic(session, goal)
            
            dependencies = await self._evaluate_dependencies(session, goal_id, context)
            if dependencies:
                result = self._apply_dependency_constraints(result, dependencies)
                result.dependencies = dependencies
            
            logger.info(
                "truth_evaluated",
                goal_id=str(goal_id)[:8],
                confidence_true=round(result.truth_estimate.confidence_true, 3),
                state=result.truth_estimate.state.value,
                mode=result.completion_mode.value,
                evidence_count=result.truth_estimate.evidence_count
            )
            
            # Cache result if context provided
            if context:
                context.set_cached(goal_id, result)
            
            return result
        
        finally:
            if context:
                context.end_evaluating(goal_id)
    
    def _create_uncertain_result(self, goal_id: UUID, reason: str) -> CompletionResult:
        """Create an uncertain result for cycle/depth protection."""
        truth_estimate = TruthEstimate(
            confidence_true=0.5,
            confidence_false=0.0,
            uncertainty=1.0,
            evidence_count=0
        )
        return CompletionResult(
            evaluated_goal_id=goal_id,
            truth_estimate=truth_estimate,
            completion_mode=CompletionMode.ATOMIC,
            is_atomic=True,
            reason=reason
        )
    
    def _determine_mode(self, goal) -> CompletionMode:
        if goal.is_atomic:
            return CompletionMode.ATOMIC
        
        mode_str = getattr(goal, 'completion_mode', 'aggregate') or 'aggregate'
        
        if mode_str == 'manual':
            return CompletionMode.MANUAL
        elif mode_str == 'strict':
            return CompletionMode.STRICT
        else:
            return CompletionMode.AGGREGATE
    
    def _get_goal_patterns(self, goal) -> List[Any]:
        """Get patterns for a goal, if defined."""
        patterns = []
        
        # Check if goal has evaluation_pattern defined
        evaluation_pattern = getattr(goal, 'evaluation_pattern', None)
        if evaluation_pattern:
            from autonomy.propositions import GoalPattern
            if isinstance(evaluation_pattern, dict):
                patterns.append(GoalPattern.from_dict(evaluation_pattern))
            elif isinstance(evaluation_pattern, list):
                for p in evaluation_pattern:
                    patterns.append(GoalPattern.from_dict(p))
        
        return patterns
    
    async def _evaluate_atomic(
        self,
        session: AsyncSession,
        goal
    ) -> CompletionResult:
        """
        ATOMIC goal evaluation with confidence.
        
        v2.4: BeliefState-based evaluation (NO MORE PENALTY).
        
        Flow:
        1. Convert artifacts → propositions
        2. Build WorldBeliefState
        3. Evaluate via BeliefState (sees full distribution)
        
        NO conflict penalty.
        NO raw proposition access.
        WorldBeliefState is the ONLY source of truth.
        """
        from models import Artifact
        from autonomy.propositions import (
            get_converter, get_proposition_store,
            GoalPattern, MatchMode
        )
        from autonomy.beliefs import get_belief_builder
        
        # STEP 1: Convert artifacts to propositions
        stmt = select(Artifact).where(Artifact.goal_id == goal.id)
        result = await session.execute(stmt)
        artifacts = result.scalars().all()
        
        converter = get_converter()
        store = get_proposition_store()
        
        propositions = converter.convert_batch(list(artifacts))
        for prop in propositions:
            store.add(prop)
        
        # STEP 2: Build WorldBeliefState (THE ONLY SOURCE OF TRUTH)
        builder = get_belief_builder()
        world_state = builder.build(store.get_all())
        
        # STEP 3: Evaluate via BeliefState
        patterns = self._get_goal_patterns(goal)
        
        if patterns:
            # Pattern-based evaluation via BeliefState
            result = await self._evaluate_by_patterns_with_beliefs(
                goal, patterns, world_state
            )
        else:
            # Legacy: aggregate by goal's artifacts
            result = await self._evaluate_by_artifacts(goal, artifacts)
        
        # Log evaluation
        logger.info(
            "belief_evaluation_complete",
            goal_id=str(goal.id)[:8],
            confidence=round(result.truth_estimate.confidence_true, 3),
            uncertainty=round(result.truth_estimate.uncertainty, 3),
            state=result.truth_estimate.state.value,
            belief_states=world_state.count,
            conflicted=len(world_state.conflicted_keys)
        )
        
        return result
    
    async def _evaluate_by_patterns_with_beliefs(
        self,
        goal,
        patterns: List[Any],
        world_state: Any
    ) -> CompletionResult:
        """
        Evaluate goal using BeliefState (NO RAW PROPOSITIONS).
        
        Goal sees full epistemic distribution via WorldBeliefState.
        Conflict is naturally expressed as uncertainty.
        """
        import math
        
        # Aggregate confidence from all patterns
        confidences = []
        uncertainties = []
        
        for pattern in patterns:
            conf, unc = world_state.aggregate_confidence(
                pattern,
                expected_value=pattern.expected_value,
                match_mode=pattern.match_mode
            )
            confidences.append(conf)
            uncertainties.append(unc)
        
        if not confidences:
            truth_estimate = TruthEstimate(
                confidence_true=0.0,
                confidence_false=0.0,
                uncertainty=1.0,
                evidence_count=0
            )
            return CompletionResult(
                evaluated_goal_id=goal.id,
                truth_estimate=truth_estimate,
                completion_mode=CompletionMode.ATOMIC,
                is_atomic=True,
                reason="No patterns defined"
            )
        
        # Combine patterns: ALL must succeed (product logic)
        # This is strict: one failed pattern = failed goal
        combined_confidence = math.prod(confidences)
        combined_uncertainty = max(uncertainties)  # Worst uncertainty dominates
        
        # Build reason
        satisfied_count = sum(1 for c in confidences if c >= 0.9)
        total_patterns = len(patterns)
        
        if combined_confidence >= 0.95:
            reason = f"All {total_patterns} patterns satisfied (conf: {combined_confidence:.2f})"
        elif satisfied_count == total_patterns:
            reason = f"All patterns OK but combined conf: {combined_confidence:.2f}"
        else:
            reason = f"{satisfied_count}/{total_patterns} patterns satisfied (conf: {combined_confidence:.2f})"
        
        # Add conflict info if present
        conflicted = world_state.conflicted_keys
        if conflicted:
            reason += f" | {len(conflicted)} beliefs conflicted"
        
        # Calculate confidence_false
        # Estimate from uncertainty
        confidence_false = combined_uncertainty * (1 - combined_confidence)
        
        truth_estimate = TruthEstimate(
            confidence_true=combined_confidence,
            confidence_false=confidence_false,
            uncertainty=combined_uncertainty,
            evidence_count=sum(confidences),  # Sum of evidence weights
            evidence_weight=combined_confidence
        )
        
        return CompletionResult(
            evaluated_goal_id=goal.id,
            truth_estimate=truth_estimate,
            completion_mode=CompletionMode.ATOMIC,
            is_atomic=True,
            reason=reason
        )
    
    async def _evaluate_by_patterns(self, goal, patterns: List[Any]) -> CompletionResult:
        """
        Evaluate goal using pattern matching against world state.
        
        This is the universal evaluator: goals query the world,
        not just aggregate their own evidence.
        """
        from autonomy.propositions import get_matcher
        
        matcher = get_matcher()
        results = matcher.match_patterns(patterns)
        
        # Aggregate confidence from all pattern matches
        if not results:
            truth_estimate = TruthEstimate(
                confidence_true=0.0,
                confidence_false=0.0,
                uncertainty=1.0,
                evidence_count=0
            )
            return CompletionResult(
                evaluated_goal_id=goal.id,
                truth_estimate=truth_estimate,
                completion_mode=CompletionMode.ATOMIC,
                is_atomic=True,
                reason="No patterns defined and no evidence"
            )
        
        # Calculate aggregate confidence
        all_satisfied = all(r.satisfied for r in results)
        avg_confidence = sum(r.confidence for r in results) / len(results)
        total_evidence = sum(r.count for r in results)
        
        # Pattern satisfaction determines truth
        if all_satisfied and avg_confidence >= 0.9:
            confidence_true = avg_confidence
            confidence_false = 0.0
            uncertainty = 0.0
            reason = f"All {len(patterns)} patterns satisfied (confidence: {avg_confidence:.2f})"
        else:
            unsatisfied = [r for r in results if not r.satisfied]
            confidence_true = avg_confidence * 0.5
            confidence_false = 0.0
            uncertainty = 1.0 - avg_confidence
            reason = f"{len(unsatisfied)}/{len(patterns)} patterns not satisfied"
        
        truth_estimate = TruthEstimate(
            confidence_true=confidence_true,
            confidence_false=confidence_false,
            uncertainty=uncertainty,
            evidence_count=total_evidence,
            evidence_weight=avg_confidence
        )
        
        return CompletionResult(
            evaluated_goal_id=goal.id,
            truth_estimate=truth_estimate,
            completion_mode=CompletionMode.ATOMIC,
            is_atomic=True,
            reason=reason
        )
    
    async def _evaluate_by_artifacts(self, goal, artifacts) -> CompletionResult:
        """
        Legacy artifact-based evaluation.
        
        Evidence model:
        - Each passed artifact adds weight
        - Each failed artifact subtracts weight
        - Pending artifacts add uncertainty
        - Confidence = tanh(weighted_evidence)
        """
        passed_weight = 0.0
        failed_weight = 0.0
        pending_weight = 0.0
        
        passed_artifacts = []
        failed_artifacts = []
        pending_artifacts = []
        
        for artifact in artifacts:
            status = getattr(artifact, 'verification_status', None) or "pending"
            artifact_type = getattr(artifact, 'type', None) or "FILE"
            weight = self.ARTIFACT_WEIGHTS.get(artifact_type, 1.0)
            
            summary = ArtifactSummary(
                artifact_id=artifact.id,
                status=status,
                artifact_type=artifact_type,
                weight=weight,
                description=getattr(artifact, 'description', None)
            )
            
            if status == "passed":
                passed_weight += weight
                passed_artifacts.append(summary)
            elif status == "failed":
                failed_weight += weight
                failed_artifacts.append(summary)
            else:
                pending_weight += weight * 0.5
                pending_artifacts.append(summary)
        
        import math
        
        total_evidence = passed_weight + failed_weight + pending_weight
        
        if total_evidence == 0:
            confidence_true = 0.0
            confidence_false = 0.0
            uncertainty = 1.0
            reason = "No evidence available"
        else:
            net_evidence = passed_weight - failed_weight * 2.0
            
            confidence_true = (math.tanh(net_evidence) + 1.0) / 2.0
            confidence_true = max(0.0, min(1.0, confidence_true))
            
            if failed_weight > 0:
                confidence_false = min(1.0, failed_weight / (passed_weight + failed_weight + 0.1))
            else:
                confidence_false = 1.0 - confidence_true
            
            uncertainty = pending_weight / (total_evidence + 1.0)
            
            if confidence_true >= self.CONFIDENCE_THRESHOLD_TRUE:
                reason = f"Strong positive evidence: {len(passed_artifacts)} passed artifacts"
            elif confidence_false >= self.CONFIDENCE_THRESHOLD_TRUE:
                reason = f"Negative evidence: {len(failed_artifacts)} failed artifacts"
            else:
                reason = f"Mixed evidence: {len(passed_artifacts)} passed, {len(failed_artifacts)} failed, {len(pending_artifacts)} pending"
        
        truth_estimate = TruthEstimate(
            confidence_true=confidence_true,
            confidence_false=confidence_false,
            uncertainty=uncertainty,
            evidence_count=len(passed_artifacts) + len(failed_artifacts),
            evidence_weight=passed_weight
        )
        
        evidence = passed_artifacts + failed_artifacts + pending_artifacts
        
        return CompletionResult(
            evaluated_goal_id=goal.id,
            truth_estimate=truth_estimate,
            completion_mode=CompletionMode.ATOMIC,
            is_atomic=True,
            reason=reason,
            evidence=evidence
        )
    
    async def _evaluate_aggregate(
        self,
        session: AsyncSession,
        goal,
        context: Optional[EvaluationContext] = None
    ) -> CompletionResult:
        """
        AGGREGATE goal evaluation.
        
        Confidence = min(children confidence)
        This is conservative: composite is only as certain as its weakest child.
        """
        from models import Goal
        
        stmt = select(Goal).where(Goal.parent_id == goal.id)
        result = await session.execute(stmt)
        children = result.scalars().all()
        
        if not children:
            truth_estimate = TruthEstimate(
                confidence_true=0.0,
                confidence_false=0.0,
                uncertainty=1.0,
                evidence_count=0
            )
            return CompletionResult(
                evaluated_goal_id=goal.id,
                truth_estimate=truth_estimate,
                completion_mode=CompletionMode.AGGREGATE,
                is_atomic=False,
                reason="No children to aggregate"
            )
        
        children_summary = []
        min_confidence = 1.0
        max_confidence_false = 0.0
        total_uncertainty = 0.0
        
        for child in children:
            child_result = await self.evaluate(session, child.id, context)
            child_confidence = child_result.truth_estimate.confidence_true
            
            children_summary.append(ChildSummary(
                goal_id=child.id,
                title=child.title,
                confidence_true=child_confidence,
                state=child_result.truth_estimate.state.value
            ))
            
            min_confidence = min(min_confidence, child_confidence)
            max_confidence_false = max(max_confidence_false, child_result.truth_estimate.confidence_false)
            total_uncertainty += child_result.truth_estimate.uncertainty
        
        avg_uncertainty = total_uncertainty / len(children)
        
        truth_estimate = TruthEstimate(
            confidence_true=min_confidence,
            confidence_false=max_confidence_false,
            uncertainty=avg_uncertainty,
            evidence_count=len(children)
        )
        
        done_count = sum(1 for c in children_summary if c.state == "true")
        reason = f"{done_count}/{len(children)} children TRUE, confidence bounded by weakest"
        
        return CompletionResult(
            evaluated_goal_id=goal.id,
            truth_estimate=truth_estimate,
            completion_mode=CompletionMode.AGGREGATE,
            is_atomic=False,
            reason=reason,
            children_status=children_summary
        )
    
    async def _evaluate_manual(
        self,
        session: AsyncSession,
        goal
    ) -> CompletionResult:
        """
        MANUAL goal evaluation.
        
        Confidence from DECISION artifact approval.
        """
        from models import Artifact
        
        stmt = select(Artifact).where(
            Artifact.goal_id == goal.id,
            Artifact.type == "DECISION"
        )
        result = await session.execute(stmt)
        decision_artifacts = result.scalars().all()
        
        approved_artifact = None
        for artifact in decision_artifacts:
            metadata = getattr(artifact, 'metadata', {}) or {}
            if metadata.get("approval") is True:
                approved_artifact = artifact
                break
        
        if approved_artifact:
            truth_estimate = TruthEstimate(
                confidence_true=1.0,
                confidence_false=0.0,
                uncertainty=0.0,
                evidence_count=1,
                evidence_weight=1.0
            )
            
            summary = ArtifactSummary(
                artifact_id=approved_artifact.id,
                status="passed",
                artifact_type="DECISION",
                weight=1.0
            )
            
            return CompletionResult(
                evaluated_goal_id=goal.id,
                truth_estimate=truth_estimate,
                completion_mode=CompletionMode.MANUAL,
                is_atomic=False,
                reason="Manual approval granted",
                evidence=[summary],
                manual_approval=True
            )
        
        truth_estimate = TruthEstimate(
            confidence_true=0.0,
            confidence_false=0.0,
            uncertainty=1.0,
            evidence_count=0
        )
        
        return CompletionResult(
            evaluated_goal_id=goal.id,
            truth_estimate=truth_estimate,
            completion_mode=CompletionMode.MANUAL,
            is_atomic=False,
            reason="No approval decision found",
            manual_approval=False
        )
    
    async def _evaluate_strict(
        self,
        session: AsyncSession,
        goal
    ) -> CompletionResult:
        """
        STRICT goal evaluation.
        
        Confidence from evaluator result + evidence.
        """
        from models import Artifact
        
        evaluator_result = goal.evaluation_result or {}
        success = evaluator_result.get("success")
        confidence_from_evaluator = evaluator_result.get("confidence", 0.5)
        
        stmt = select(Artifact).where(
            Artifact.goal_id == goal.id,
            Artifact.verification_status == "passed"
        )
        result = await session.execute(stmt)
        evidence_artifacts = result.scalars().all()
        
        has_evidence = len(evidence_artifacts) > 0
        
        if success is False:
            truth_estimate = TruthEstimate(
                confidence_true=0.0,
                confidence_false=1.0,
                uncertainty=0.0,
                evidence_count=0
            )
            return CompletionResult(
                evaluated_goal_id=goal.id,
                truth_estimate=truth_estimate,
                completion_mode=CompletionMode.STRICT,
                is_atomic=False,
                reason="Strict evaluator returned failure",
                strict_evaluator_result=evaluator_result
            )
        
        if success is True and has_evidence:
            truth_estimate = TruthEstimate(
                confidence_true=confidence_from_evaluator,
                confidence_false=1.0 - confidence_from_evaluator,
                uncertainty=0.0,
                evidence_count=len(evidence_artifacts),
                evidence_weight=confidence_from_evaluator
            )
            
            evidence = [
                ArtifactSummary(
                    artifact_id=a.id,
                    status="passed",
                    artifact_type=a.type
                )
                for a in evidence_artifacts
            ]
            
            return CompletionResult(
                evaluated_goal_id=goal.id,
                truth_estimate=truth_estimate,
                completion_mode=CompletionMode.STRICT,
                is_atomic=False,
                reason=f"Evaluator passed (confidence: {confidence_from_evaluator:.2f}) with evidence",
                evidence=evidence,
                strict_evaluator_result=evaluator_result
            )
        
        if success is True and not has_evidence:
            truth_estimate = TruthEstimate(
                confidence_true=confidence_from_evaluator * 0.5,
                confidence_false=0.0,
                uncertainty=0.5,
                evidence_count=0
            )
            return CompletionResult(
                evaluated_goal_id=goal.id,
                truth_estimate=truth_estimate,
                completion_mode=CompletionMode.STRICT,
                is_atomic=False,
                reason="Evaluator passed but NO EVIDENCE - confidence reduced",
                strict_evaluator_result=evaluator_result
            )
        
        truth_estimate = TruthEstimate(
            confidence_true=0.0,
            confidence_false=0.0,
            uncertainty=1.0,
            evidence_count=0
        )
        
        return CompletionResult(
            evaluated_goal_id=goal.id,
            truth_estimate=truth_estimate,
            completion_mode=CompletionMode.STRICT,
            is_atomic=False,
            reason="Strict evaluation not yet completed",
            strict_evaluator_result=evaluator_result
        )
    
    async def _evaluate_dependencies(
        self,
        session: AsyncSession,
        goal_id: UUID,
        context: Optional[EvaluationContext] = None
    ) -> List[DependencySummary]:
        """
        Evaluate REQUIRES dependencies.
        
        Rule: confidence(A) <= confidence(B) if A REQUIRES B
        """
        from models import GoalRelation
        
        stmt = select(GoalRelation).where(
            GoalRelation.from_goal_id == goal_id,
            GoalRelation.relation_type == "dependency"
        )
        result = await session.execute(stmt)
        dependencies = result.scalars().all()
        
        summaries = []
        
        for dep in dependencies:
            dep_result = await self.evaluate(session, dep.to_goal_id, context)
            
            summaries.append(DependencySummary(
                goal_id=dep.to_goal_id,
                relation_type=dep.relation_type,
                constraint_satisfied=dep_result.truth_estimate.confidence_true >= 0.5,
                constraint_confidence=dep_result.truth_estimate.confidence_true
            ))
        
        return summaries
    
    def _apply_dependency_constraints(
        self,
        result: CompletionResult,
        dependencies: List[DependencySummary]
    ) -> CompletionResult:
        """
        Apply dependency constraints to confidence.
        
        If A REQUIRES B and B has low confidence:
        confidence(A) is bounded by confidence(B)
        """
        if not dependencies:
            return result
        
        max_allowed_confidence = min(
            (d.constraint_confidence for d in dependencies),
            default=1.0
        )
        
        original_confidence = result.truth_estimate.confidence_true
        
        if original_confidence > max_allowed_confidence:
            penalty = original_confidence - max_allowed_confidence
            result.truth_estimate.confidence_true = max_allowed_confidence
            result.truth_estimate.dependency_penalty = penalty
            
            unsatisfied = [d for d in dependencies if not d.constraint_satisfied]
            if unsatisfied:
                result.reason += f" (bounded by {len(unsatisfied)} unsatisfied dependencies)"
        
        return result
    
    async def can_transition(
        self,
        session: AsyncSession,
        goal_id: UUID,
        target_status: str
    ) -> Tuple[bool, str]:
        """
        Check if transition to target status is valid.
        """
        if target_status not in ("done", "failed"):
            return True, f"Non-terminal status '{target_status}' is always allowed"
        
        result = await self.evaluate(session, goal_id)
        state = result.truth_estimate.state
        
        if target_status == "done":
            if state == TruthState.TRUE:
                return True, "Truth verified with high confidence"
            else:
                return False, f"Truth state is {state.value}, not TRUE (confidence: {result.truth_estimate.confidence_true:.2f})"
        
        if target_status == "failed":
            if state == TruthState.FALSE:
                return True, "Failure verified with high confidence"
            else:
                return True, f"Manual failure override (truth state: {state.value})"
        
        return True, "Unknown case - allowing transition"
    
    def clear_cache(self):
        """Clear evaluation cache."""
        self._cache.clear()


_completion_engine: Optional[CompletionEngine] = None


def get_completion_engine() -> CompletionEngine:
    """Get or create global completion engine."""
    global _completion_engine
    if _completion_engine is None:
        _completion_engine = CompletionEngine()
    return _completion_engine


def reset_completion_engine():
    """Reset global completion engine."""
    global _completion_engine
    if _completion_engine:
        _completion_engine.clear_cache()
    _completion_engine = CompletionEngine()
