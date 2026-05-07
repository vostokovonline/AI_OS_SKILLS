"""
Arbitration Layer - Decision boundary between thinking and acting.

ARCHITECTURE:
    COLLECT → ESTIMATE → POLICY → SELECT → APPLY

CRITICAL INVARIANTS:
    1. ScoredIntent has NO decisions (observations only)
    2. Strategy lives in Policy, not Arbitrator
    3. Budget is state (CapitalAllocator), not config
    4. Rejected = decision trace, not garbage

USAGE:
    from application.arbitration import (
        BatchArbitrator,
        GreedyUtilityPolicy,
        ConfidenceUtilityEstimator,
        ConstantCostEstimator,
        ConfidenceRiskEstimator,
        FixedBudgetAllocator,
        InMemoryArbitrationLog,
    )

    arbitrator = BatchArbitrator(
        utility_estimator=ConfidenceUtilityEstimator(),
        cost_estimator=ConstantCostEstimator(cost=1.0),
        risk_estimator=ConfidenceRiskEstimator(),
        policy=GreedyUtilityPolicy(),
        arbitration_log=InMemoryArbitrationLog(max_size=100),
    )

    result = await arbitrator.evaluate(intents, budget=10.0)

Author: AI-OS Core Team
Date: 2026-03-01
Version: 1.0.0 - Decision boundary implementation
"""

# Core components
from .batch_arbitrator import BatchArbitrator
from .scored_intent import ScoredIntent
from .arbitration_result import ArbitrationResult

# Strategies
from .policy import DecisionPolicy, GreedyUtilityPolicy

# Estimators
from .estimators import (
    UtilityEstimator,
    CostEstimator,
    RiskEstimator,
    ConfidenceUtilityEstimator,
    ConstantCostEstimator,
    ConfidenceRiskEstimator,
)

# Budget
from .capital_allocator import CapitalAllocator, FixedBudgetAllocator

# Logging
from .arbitration_log import ArbitrationLog, NoopArbitrationLog, InMemoryArbitrationLog

__all__ = [
    # Core
    "BatchArbitrator",
    "ScoredIntent",
    "ArbitrationResult",
    # Policies
    "DecisionPolicy",
    "GreedyUtilityPolicy",
    # Estimators
    "UtilityEstimator",
    "CostEstimator",
    "RiskEstimator",
    "ConfidenceUtilityEstimator",
    "ConstantCostEstimator",
    "ConfidenceRiskEstimator",
    # Budget
    "CapitalAllocator",
    "FixedBudgetAllocator",
    # Logging
    "ArbitrationLog",
    "NoopArbitrationLog",
    "InMemoryArbitrationLog",
]
