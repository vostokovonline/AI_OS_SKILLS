"""
Batch Arbitrator - Decision pipeline orchestrator.

ARCHITECTURE:
    ESTIMATE → POLICY → SELECT → LOG

CRITICAL:
    - Arbitrator knows HOW to run pipeline
    - Policy knows HOW to select
    - Estimators know HOW to estimate features

NO strategy lives here. Only orchestration.
"""
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from application.arbitration.scored_intent import ScoredIntent
from application.arbitration.arbitration_result import ArbitrationResult
from application.arbitration.estimators import (
    UtilityEstimator,
    CostEstimator,
    RiskEstimator,
)
from application.arbitration.policy import DecisionPolicy
from application.arbitration.capital_allocator import CapitalAllocator
from application.arbitration.arbitration_log import ArbitrationLog


class BatchArbitrator:
    """
    Decision pipeline orchestrator.

    Runs: ESTIMATE → POLICY → SELECT → LOG

    Does NOT contain strategy. Only assembles components.
    """

    def __init__(
        self,
        utility_estimator: UtilityEstimator,
        cost_estimator: CostEstimator,
        risk_estimator: RiskEstimator,
        policy: DecisionPolicy,
        arbitration_log: Optional[ArbitrationLog] = None,
    ):
        """
        Initialize arbitrator with components.

        Args:
            utility_estimator: Estimates benefit
            cost_estimator: Estimates resource cost
            risk_estimator: Estimates failure probability
            policy: Selection strategy
            arbitration_log: Decision trace storage (optional)
        """
        self._utility = utility_estimator
        self._cost = cost_estimator
        self._risk = risk_estimator
        self._policy = policy
        self._log = arbitration_log

    async def evaluate(
        self,
        intents: List["application.execution.intents.ExecutionIntent"],
        budget: float | None = None
    ) -> ArbitrationResult:
        """
        Run arbitration pipeline.

        PHASE 1: ESTIMATE features
        PHASE 2: POLICY selects
        PHASE 3: LOG trace

        Args:
            intents: Raw execution intents from executor
            budget: Available budget (None = unlimited)

        Returns:
            ArbitrationResult with selected/rejected intents
        """
        # =====================================================================
        # PHASE 1: ESTIMATE all features
        # =====================================================================
        scored: List[ScoredIntent] = []

        for intent in intents:
            utility = await self._utility.estimate(intent)
            cost = await self._cost.estimate(intent)
            risk = await self._risk.estimate(intent)

            scored.append(ScoredIntent(
                intent=intent,
                utility=utility,
                cost=cost,
                risk=risk,
                confidence=intent.confidence if intent.confidence else 0.0,
            ))

        # =====================================================================
        # PHASE 2: POLICY selects subset
        # =====================================================================
        selected = await self._policy.select(scored, budget)

        # Determine rejection reasons
        rejected_with_reasons = []
        budget_remaining = budget if budget else float('inf')

        for s in scored:
            if s in selected:
                continue

            # Determine why rejected
            reason = None
            if s.cost > budget_remaining:
                reason = "budget_exhausted"
            elif s.utility < 0.4:
                reason = "low_utility"
            elif s.risk > 0.6:
                reason = "high_risk"
            else:
                reason = "lower_priority"

            rejected_with_reasons.append(
                ScoredIntent(
                    intent=s.intent,
                    utility=s.utility,
                    cost=s.cost,
                    risk=s.risk,
                    confidence=s.confidence,
                    rejection_reason=reason
                )
            )

        rejected = rejected_with_reasons

        # =====================================================================
        # PHASE 3: COMPUTE result metadata
        # =====================================================================
        total_utility = sum(s.utility for s in selected)
        total_cost = sum(s.cost for s in selected)
        budget_remaining = (budget - total_cost) if budget is not None else None

        result = ArbitrationResult(
            selected=selected,
            rejected=rejected,
            total_utility=total_utility,
            total_cost=total_cost,
            budget_remaining=budget_remaining,
            timestamp=datetime.utcnow(),
        )

        # =====================================================================
        # PHASE 4: LOG decision trace
        # =====================================================================
        if self._log:
            await self._log.record(result)

        return result
