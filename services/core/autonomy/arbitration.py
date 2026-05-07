"""
ARBITRATION LAYER - Context-Aware Utility Resolver
====================================================

Production-grade arbitration for autonomous decision making.

Core Principle:
    Always select ONE action from many candidates.
    Never explode utility.
    Never stagnate on one strategy.
    Deterministic and reproducible.

Architecture:
    - ArbitrationContext: immutable snapshot of system state
    - ArbitrationConfig: configuration parameters
    - StrategyRuntimeStats: runtime performance tracking
    - ActionArbitrator: core resolver

Author: AI-OS Team
Date: 2026-02-20
Version: 1.0.0
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

from autonomy.policy_engine import ActionType
from logging_config import get_logger

logger = get_logger(__name__)


class RiskLevel(int, Enum):
    """Risk levels for actions"""
    MINIMAL = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


@dataclass(frozen=True)
class ArbitrationConfig:
    """
    Configuration for arbitration behavior.
    
    Immutable - loaded from config/environment.
    
    IMPORTANT: exploration_rate = 0.0 by default for deterministic behavior.
    Production autonomous agents should keep deterministic core.
    Exploration is a POLICY decision, not arbitration behavior.
    
    CRITICAL: tie_threshold must be tiny (1e-6) for pure argmax behavior.
    Selection = argmax(final_utility), no policy overrides.
    
    NEW: enable_capital_allocation switches between:
    - False (default): Single winner selection (argmax)
    - True: Portfolio allocation (Capital Engine)
    """
    tie_threshold: float = 1e-6  # Near-zero for pure argmax
    risk_penalty_alpha: float = 0.5
    recency_penalty_beta: float = 0.3
    max_emotion_influence: float = 0.3
    emotion_range_min: float = 0.7
    emotion_range_max: float = 1.3
    max_utility_cap: float = 2.0
    min_utility_floor: float = 0.0
    stagnation_threshold: int = 5
    stagnation_penalty: float = 0.5
    exploration_rate: float = 0.0
    exploration_top_k: int = 3
    
    # Capital allocation mode (Stage 4 integration)
    enable_capital_allocation: bool = False
    
    # Modifier weights (must sum to 1.0)
    emotion_weight: float = 0.30
    resource_weight: float = 0.35
    risk_weight: float = 0.20
    recency_weight: float = 0.15
    
    def __post_init__(self):
        """Validate weights sum to 1.0"""
        total = self.emotion_weight + self.resource_weight + self.risk_weight + self.recency_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Modifier weights must sum to 1.0, got {total}")


@dataclass(frozen=True)
class EmotionalSnapshot:
    """
    Immutable snapshot of emotional state.
    
    From emotional_layer.
    """
    valence: float  # -1.0 to 1.0 (negative to positive)
    arousal: float  # 0.0 to 1.0 (calm to excited)
    stress: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    momentum: float  # 0.0 to 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ResourceSnapshot:
    """
    Immutable snapshot of resource availability.
    
    From system_state.
    """
    budget_remaining: float  # USD
    budget_limit: float  # USD
    concurrent_goals: int
    max_concurrent_goals: int
    compute_available: float  # 0.0 to 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def budget_factor(self) -> float:
        """Budget availability factor (0.0 to 1.0)"""
        if self.budget_limit <= 0:
            return 0.0
        return min(1.0, self.budget_remaining / self.budget_limit)
    
    @property
    def capacity_factor(self) -> float:
        """Goal capacity factor (0.0 to 1.0)"""
        if self.max_concurrent_goals <= 0:
            return 0.0
        return max(0.0, 1.0 - (self.concurrent_goals / self.max_concurrent_goals))


@dataclass(frozen=True)
class StrategyConfig:
    """
    Static configuration for a strategy (from DB).
    
    Immutable per strategy.
    """
    strategy_id: UUID
    name: str
    priority: float  # 0.5 to 2.0
    default_risk_level: RiskLevel
    cost_estimate: float  # estimated resource cost
    description: str = ""


@dataclass
class StrategyRuntimeStats:
    """
    Runtime statistics for a strategy.
    
    Mutable - updated during execution.
    """
    strategy_id: UUID
    activation_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    cumulative_cost: float = 0.0
    last_activated_at: Optional[datetime] = None
    recent_activations: List[datetime] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Success rate (0.0 to 1.0)"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0  # Default to 1.0 for untested strategies
        return self.success_count / total
    
    @property
    def recent_activation_count(self) -> int:
        """Count of recent activations (last hour)"""
        cutoff = datetime.utcnow() - timedelta(hours=1)
        return len([t for t in self.recent_activations if t >= cutoff])
    
    def record_activation(self, cost: float = 0.0):
        """Record a new activation"""
        self.activation_count += 1
        self.last_activated_at = datetime.utcnow()
        self.recent_activations.append(datetime.utcnow())
        self.cumulative_cost += cost
        
        # Keep only last 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.recent_activations = [t for t in self.recent_activations if t >= cutoff]
    
    def record_success(self):
        """Record a successful outcome"""
        self.success_count += 1
    
    def record_failure(self):
        """Record a failed outcome"""
        self.failure_count += 1


@dataclass(frozen=True)
class SystemStateSnapshot:
    """
    Immutable snapshot of system state.
    
    From system_state table.
    """
    metrics: Dict[str, float]
    trends: Dict[str, str]  # "up", "down", "stable"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ArbitrationContext:
    """
    Complete context for arbitration decision.
    
    Immutable snapshot at decision time.
    """
    system_state: SystemStateSnapshot
    emotion: EmotionalSnapshot
    resources: ResourceSnapshot
    strategy_configs: Dict[UUID, StrategyConfig]
    strategy_stats: Dict[UUID, StrategyRuntimeStats]
    config: ArbitrationConfig
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def get_strategy_config(self, strategy_id: UUID) -> Optional[StrategyConfig]:
        """Get strategy config by ID"""
        return self.strategy_configs.get(strategy_id)
    
    def get_strategy_stats(self, strategy_id: UUID) -> StrategyRuntimeStats:
        """Get strategy stats by ID (returns empty stats if not found)"""
        if strategy_id not in self.strategy_stats:
            return StrategyRuntimeStats(strategy_id=strategy_id)
        return self.strategy_stats[strategy_id]


@dataclass
class DecisionAction:
    """
    An action candidate for arbitration.
    
    Generated by policy engine.
    """
    id: UUID
    action_type: ActionType
    action_payload: Dict[str, Any]
    strategy_id: UUID
    source_rule_name: str
    reason: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    cost_estimate: float = 0.0
    approved: bool = False
    executed: bool = False
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class UtilityBreakdown:
    """
    Detailed breakdown of utility calculation.
    
    Critical for debugging and analysis.
    """
    action_id: UUID
    strategy_id: UUID
    strategy_name: str
    
    performance: float
    priority: float
    emotion_modifier: float
    resource_factor: float
    risk_adjustment: float
    recency_penalty: float
    
    final_score: float
    
    strategy_activation_count: int
    strategy_success_rate: float
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": str(self.action_id),
            "strategy_id": str(self.strategy_id),
            "strategy_name": self.strategy_name,
            "performance": self.performance,
            "priority": self.priority,
            "emotion_modifier": self.emotion_modifier,
            "resource_factor": self.resource_factor,
            "risk_adjustment": self.risk_adjustment,
            "recency_penalty": self.recency_penalty,
            "final_score": self.final_score,
            "strategy_activation_count": self.strategy_activation_count,
            "strategy_success_rate": self.strategy_success_rate,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass(frozen=True)
class ArbitrationResult:
    """
    Result of arbitration process.
    """
    selected_action: Optional[DecisionAction]
    candidates_count: int
    breakdowns: List[UtilityBreakdown]
    tie_broken: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_action_id": str(self.selected_action.id) if self.selected_action else None,
            "candidates_count": self.candidates_count,
            "breakdowns": [b.to_dict() for b in self.breakdowns],
            "tie_broken": self.tie_broken,
            "timestamp": self.timestamp.isoformat()
        }


class ActionArbitrator:
    """
    Context-Aware Utility Resolver.
    
    Core Principles:
    - Always select ONE action (or None if no candidates)
    - Never explode utility (capped at config.max_utility_cap)
    - Never stagnate (recency penalty)
    - Deterministic (same input → same output)
    - No binary filtering (only penalties)
    
    Utility Formula:
        Utility = 
            StrategyPerformanceScore (success_rate)
            × StrategyPriority (0.5-2.0)
            × EmotionalModifier (0.7-1.3, max 30% influence)
            × ResourceFactor (0.0-1.0)
            × RiskAdjustment (penalty, not filter)
            × RecencyPenalty (anti-stagnation)
    """
    
    def __init__(self, config: Optional[ArbitrationConfig] = None):
        self.config = config or ArbitrationConfig()
    
    def resolve(
        self, 
        actions: List[DecisionAction], 
        context: ArbitrationContext
    ) -> ArbitrationResult:
        """
        Select ONE action from candidates.
        
        Args:
            actions: List of candidate actions
            context: Complete arbitration context
            
        Returns:
            ArbitrationResult with selected action and breakdowns
        """
        from autonomy.stability_guards import (
            get_anti_monopoly_guard, 
            get_observability_tracker,
            CycleObservation
        )
        
        if not actions:
            return ArbitrationResult(
                selected_action=None,
                candidates_count=0,
                breakdowns=[],
                tie_broken=False
            )
        
        if len(actions) == 1:
            breakdown = self._compute_utility(actions[0], context)
            
            # Record activation
            get_anti_monopoly_guard().record_activation(str(actions[0].strategy_id))
            
            return ArbitrationResult(
                selected_action=actions[0],
                candidates_count=1,
                breakdowns=[breakdown],
                tie_broken=False
            )
        
        # Start observability cycle
        observability = get_observability_tracker()
        cycle_id = observability.start_cycle()
        
        # Compute utility for each action
        scored: List[tuple[DecisionAction, UtilityBreakdown]] = []
        for action in actions:
            breakdown = self._compute_utility(action, context)
            scored.append((action, breakdown))
        
        # Sort by final score (descending)
        scored.sort(key=lambda x: x[1].final_score, reverse=True)
        
        # Exploration injection (POLICY LAYER, not core arbitration)
        # Default = 0.0 = deterministic, same input → same output
        # Only enabled when explicitly configured
        tie_broken = False
        selected_action = scored[0][0]
        selected_breakdown = scored[0][1]
        
        if self.config.exploration_rate > 0 and len(scored) > 1:
            import random
            if random.random() < self.config.exploration_rate:
                # Exploration: randomly select from top-k instead of top-1
                top_k = min(self.config.exploration_top_k, len(scored))
                exploration_idx = random.randint(0, top_k - 1)
                selected_action = scored[exploration_idx][0]
                selected_breakdown = scored[exploration_idx][1]
                logger.info(
                    "exploration_injection",
                    cycle=cycle_id,
                    selected_rank=exploration_idx + 1,
                    candidates=len(scored)
                )
        
        # Check for tie (after potential exploration)
        if len(scored) >= 2 and not tie_broken:
            top1_score = scored[0][1].final_score
            top2_score = scored[1][1].final_score
            
            if abs(top1_score - top2_score) < self.config.tie_threshold:
                # Tie-break required
                selected_action = self._tie_break(
                    scored[0][0], 
                    scored[1][0], 
                    context
                )
                tie_broken = True
                # Update selected breakdown
                for action, breakdown in scored:
                    if action == selected_action:
                        selected_breakdown = breakdown
                        break
        
        # CRITICAL: Verify argmax behavior
        # Selected action MUST have the highest utility (within epsilon)
        max_utility = max(s[1].final_score for s in scored)
        assert selected_breakdown.final_score >= max_utility - 1e-6, (
            f"ARGMAX VIOLATION: selected={selected_breakdown.final_score:.6f}, "
            f"max={max_utility:.6f}, delta={max_utility - selected_breakdown.final_score:.6f}"
        )
        
        # Record activation in anti-monopoly guard
        strategy_id_str = str(selected_action.strategy_id)
        get_anti_monopoly_guard().record_activation(strategy_id_str)
        
        return ArbitrationResult(
            selected_action=selected_action,
            candidates_count=len(actions),
            breakdowns=[s[1] for s in scored],
            tie_broken=tie_broken
        )
    
    def _compute_utility(
        self, 
        action: DecisionAction, 
        context: ArbitrationContext
    ) -> UtilityBreakdown:
        """
        Compute full utility breakdown for an action.
        
        All factors are penalties/bonuses, not filters.
        Final score is clamped to [min_utility_floor, max_utility_cap].
        """
        strategy_config = context.get_strategy_config(action.strategy_id)
        strategy_stats = context.get_strategy_stats(action.strategy_id)
        
        # 1. Performance score (from strategy runtime stats)
        performance = self._strategy_performance(strategy_stats)
        
        # 2. Priority (from strategy config, adjusted by performance)
        priority = self._strategy_priority(strategy_config, strategy_stats)
        
        # 3. Emotional modifier (from emotional layer)
        emotion_modifier = self._emotional_modifier(context, action)
        
        # 4. Resource factor (from resource snapshot)
        resource_factor = self._resource_factor(context, action)
        
        # 5. Risk adjustment (penalty, not filter)
        risk_adjustment = self._risk_adjustment(context, action)
        
        # 6. Recency penalty (anti-stagnation)
        recency_penalty = self._recency_penalty(strategy_stats)
        
        # === UTILITY CALCULATION ===
        # Architecture: 3-layer model for safety-critical decisions
        #
        # Layer 1: Base Value (core strategy worth)
        #   base_value = performance × priority
        #
        # Layer 2: Context Modifiers (weighted average to prevent cascade)
        #   modifiers = weighted_average(emotion, resource, recency)
        #
        # Layer 3: Safety Gate (risk can override)
        #   safety_gate = risk_adjustment
        #
        # Final: utility = base_value × modifiers × safety_gate
        #
        # Why 3 layers?
        # - Layer 1+2 prevent cascade collapse (weighted avg instead of multiplication)
        # - Layer 3 ensures risk can override priority in extreme cases
        # - Risk is safety-critical, not just a "modifier"
        
        # Base value: core strategy worth
        base_value = performance * priority
        
        # Context modifiers: weighted average (emotion, resource, recency)
        # These are "soft" factors that adjust behavior
        context_modifiers = (
            self.config.emotion_weight * emotion_modifier +
            self.config.resource_weight * resource_factor +
            self.config.recency_weight * recency_penalty
        ) / (self.config.emotion_weight + self.config.resource_weight + self.config.recency_weight)
        
        # Safety gate: risk adjustment (applied separately for override capability)
        # This is a "hard" factor that can override in extreme cases
        safety_gate = risk_adjustment
        
        # Final score: base × context × safety
        raw_score = base_value * context_modifiers * safety_gate
        
        # Clamp to valid range
        final_score = max(
            self.config.min_utility_floor,
            min(self.config.max_utility_cap, raw_score)
        )
        
        # Apply anti-monopoly guard (diminishing returns for frequent use)
        from autonomy.stability_guards import get_anti_monopoly_guard
        
        strategy_id_str = str(action.strategy_id)
        anti_monopoly = get_anti_monopoly_guard()
        final_score, diminishing_factor = anti_monopoly.apply(strategy_id_str, final_score)
        
        # Log breakdown for debugging
        logger.debug(
            "utility_computed",
            action_id=str(action.id),
            strategy_name=strategy_config.name if strategy_config else "unknown",
            base_value=round(base_value, 3),
            context_modifiers=round(context_modifiers, 3),
            safety_gate=round(safety_gate, 3),
            diminishing=round(diminishing_factor, 3),
            final_score=round(final_score, 3)
        )
        
        return UtilityBreakdown(
            action_id=action.id,
            strategy_id=action.strategy_id,
            strategy_name=strategy_config.name if strategy_config else "unknown",
            performance=performance,
            priority=priority,
            emotion_modifier=emotion_modifier,
            resource_factor=resource_factor,
            risk_adjustment=risk_adjustment,
            recency_penalty=recency_penalty,
            final_score=final_score,
            strategy_activation_count=strategy_stats.activation_count,
            strategy_success_rate=strategy_stats.success_rate
        )
    
    def _strategy_performance(self, stats: StrategyRuntimeStats) -> float:
        """
        Performance score based on EMA-smoothed success rate.
        
        CRITICAL: Uses EMA from FailureShockAbsorber, NOT raw success_rate.
        This prevents "death spiral" from single failures.
        
        Returns:
            0.0 to 1.5 (allows above 1.0 for exceptional performance)
        """
        from autonomy.stability_guards import get_failure_shock_absorber
        
        if stats.activation_count == 0:
            return 1.0  # Default for untested strategies
        
        # Use EMA-smoothed success rate, not raw
        shock_absorber = get_failure_shock_absorber()
        ema_success = shock_absorber.get_ema_success(str(stats.strategy_id))
        
        return ema_success
    
    def _strategy_priority(
        self, 
        config: Optional[StrategyConfig],
        stats: Optional[StrategyRuntimeStats] = None
    ) -> float:
        """
        Priority from strategy config with adaptive weighting.
        
        If runtime stats are provided, priority is adjusted based on
        observed performance (success rate, trend).
        
        Returns:
            0.5 to 2.0
        """
        if not config:
            return 1.0
        
        base_priority = max(0.5, min(2.0, config.priority))
        
        # Apply adaptive weighting if stats available
        if stats and stats.activation_count >= 5:
            from autonomy.adaptive_weights import get_adaptive_weight_calculator
            
            calculator = get_adaptive_weight_calculator()
            effective_priority = calculator.calculate_effective_priority(
                base_priority,
                stats
            )
            return max(0.5, min(2.0, effective_priority))
        
        return base_priority
    
    def _emotional_modifier(
        self, 
        context: ArbitrationContext, 
        action: DecisionAction
    ) -> float:
        """
        Emotional influence on action selection.
        
        Rules:
        - Modifier in range [emotion_range_min, emotion_range_max]
        - Max influence is max_emotion_influence (default 30%)
        - Deterministic
        
        Emotional Logic:
        - High stress → risky actions penalized
        - Low momentum → active actions boosted
        - Low confidence → conservative actions boosted
        """
        emotion = context.emotion
        modifier = 1.0
        
        # High stress → penalize risky actions
        if emotion.stress > 0.7:
            if action.risk_level >= RiskLevel.HIGH:
                modifier *= 0.8
            elif action.risk_level >= RiskLevel.MEDIUM:
                modifier *= 0.9
        
        # Low momentum → boost active actions
        if emotion.momentum < 0.3:
            if action.action_type in [
                ActionType.CREATE_GOAL, 
                ActionType.ACTIVATE_STRATEGY,
                ActionType.SPAWN_EXPERIMENT
            ]:
                modifier *= 1.2
        
        # Low confidence → boost conservative actions
        if emotion.confidence < 0.4:
            if action.risk_level <= RiskLevel.LOW:
                modifier *= 1.15
        
        # Clamp to allowed range
        modifier = max(
            self.config.emotion_range_min,
            min(self.config.emotion_range_max, modifier)
        )
        
        return modifier
    
    def _resource_factor(
        self, 
        context: ArbitrationContext, 
        action: DecisionAction
    ) -> float:
        """
        Resource availability factor.
        
        Returns:
            0.0 to 1.0
        
        Logic:
        - If action requires budget and budget is low → penalty
        - If action requires capacity and capacity is low → penalty
        - Never zero (prevents complete blocking)
        """
        resources = context.resources
        factor = 1.0
        
        # Budget constraint
        if action.cost_estimate > 0:
            if resources.budget_remaining < action.cost_estimate:
                # Can't afford - severe penalty but not zero
                factor *= 0.1
            elif resources.budget_factor < 0.3:
                # Budget stressed
                factor *= 0.5 * resources.budget_factor
        
        # Capacity constraint
        if action.action_type == ActionType.CREATE_GOAL:
            if resources.capacity_factor < 0.2:
                # Near capacity limit
                factor *= 0.3
            elif resources.capacity_factor < 0.5:
                factor *= 0.7
        
        return max(0.01, factor)  # Never zero
    
    def _risk_adjustment(
        self, 
        context: ArbitrationContext, 
        action: DecisionAction
    ) -> float:
        """
        Risk penalty (NOT filter).
        
        Returns:
            0.0 to 1.0
        
        Formula:
            risk_penalty = exp(-alpha * risk_gap)
            
        Where risk_gap = max(0, action_risk - tolerance)
        
        This ensures:
        - Low risk actions are not penalized
        - High risk actions are penalized but not eliminated
        - Exponential decay, not binary
        """
        # Derive risk tolerance from emotional state
        # High confidence + low stress = higher tolerance
        emotion = context.emotion
        base_tolerance = 2.5  # Default MEDIUM
        confidence_boost = emotion.confidence * 1.5  # 0 to 1.5
        stress_penalty = emotion.stress * 1.5  # 0 to 1.5
        
        tolerance = base_tolerance + confidence_boost - stress_penalty
        tolerance = max(1.0, min(5.0, tolerance))  # Clamp to [1, 5]
        
        risk_gap = max(0, action.risk_level - tolerance)
        
        if risk_gap == 0:
            return 1.0
        
        # Exponential penalty
        penalty = 0.5 ** (self.config.risk_penalty_alpha * risk_gap)
        
        return penalty
    
    def _recency_penalty(self, stats: StrategyRuntimeStats) -> float:
        """
        Anti-stagnation penalty.
        
        Returns:
            0.0 to 1.0
        
        Logic:
        - If strategy activated recently many times → penalty
        - Prevents system from getting stuck in one strategy
        
        Formula:
            penalty = 1 / (1 + beta * recent_count)
        """
        recent_count = stats.recent_activation_count
        
        if recent_count >= self.config.stagnation_threshold:
            # Heavy stagnation
            return self.config.stagnation_penalty
        
        # Gradual penalty
        penalty = 1.0 / (1.0 + self.config.recency_penalty_beta * recent_count)
        
        return penalty
    
    def _tie_break(
        self, 
        action1: DecisionAction, 
        action2: DecisionAction, 
        context: ArbitrationContext
    ) -> DecisionAction:
        """
        Tie-break when scores are within epsilon.
        
        Priority:
        1. Less recently activated strategy (diversity)
        2. Lower cumulative cost (efficiency)
        3. Deterministic fallback (strategy_id sort)
        
        NO RANDOM - fully deterministic.
        """
        stats1 = context.get_strategy_stats(action1.strategy_id)
        stats2 = context.get_strategy_stats(action2.strategy_id)
        
        # 1. Less recently activated
        if stats1.last_activated_at and stats2.last_activated_at:
            if stats1.last_activated_at < stats2.last_activated_at:
                return action1
            elif stats2.last_activated_at < stats1.last_activated_at:
                return action2
        
        # If one never activated, prefer it
        if not stats1.last_activated_at and stats2.last_activated_at:
            return action1
        if not stats2.last_activated_at and stats1.last_activated_at:
            return action2
        
        # 2. Lower cumulative cost
        if stats1.cumulative_cost != stats2.cumulative_cost:
            return action1 if stats1.cumulative_cost < stats2.cumulative_cost else action2
        
        # 3. Deterministic fallback - sort by strategy_id
        return action1 if str(action1.strategy_id) < str(action2.strategy_id) else action2
    
    def resolve_with_allocation(
        self,
        actions: List[DecisionAction],
        context: ArbitrationContext
    ) -> "CapitalAllocationResult":
        """
        Resolve using Capital Engine (portfolio allocation).
        
        Stage 4 integration: Instead of selecting ONE winner,
        allocate capital across ALL strategies based on RAR.
        
        This enables:
        - Multi-strategy execution per cycle
        - Economic pressure on underperformers
        - Recovery capability for degraded strategies
        
        Args:
            actions: Candidate actions (one per strategy)
            context: Arbitration context
            
        Returns:
            CapitalAllocationResult with allocations for all strategies
        """
        from autonomy.capital_engine import (
            get_capital_allocator,
            StrategyAsset
        )
        
        if not actions:
            raise ValueError("No actions to arbitrate")
        
        if len(actions) == 1:
            # Single candidate - full allocation
            return CapitalAllocationResult(
                allocations={actions[0].strategy_id: 1.0},
                capital_allocations={actions[0].strategy_id: 1.0},
                total_capital_deployed=1.0,
                strategy_assets=[]
            )
        
        # Build StrategyAssets for Capital Engine
        assets = []
        for action in actions:
            stats = context.get_strategy_stats(action.strategy_id)
            config = context.get_strategy_config(action.strategy_id)
            
            # Get EMA from shock absorber
            from autonomy.stability_guards import get_failure_shock_absorber
            shock_absorber = get_failure_shock_absorber()
            ema = shock_absorber.get_ema_success(str(action.strategy_id))
            
            # Calculate variance proxy from recent performance
            variance_proxy = 0.1  # Default
            if stats.activation_count > 5:
                # Use success rate variance as proxy
                variance_proxy = min(0.3, max(0.05, 1.0 - ema))
            
            asset = StrategyAsset(
                strategy_id=action.strategy_id,
                name=config.name if config else str(action.strategy_id)[:8],
                ema_success=ema,
                payoff=config.cost_estimate * 2 if config else 0.02,  # Estimate
                cost=config.cost_estimate if config else 0.002,
                variance_proxy=variance_proxy
            )
            
            # Check for EMA drop penalty
            # (This would need EMA history tracking for full implementation)
            asset.ema_drop_penalty = False
            
            assets.append(asset)
        
        # Get capital allocator
        allocator = get_capital_allocator()
        
        # Get allocations from Capital Engine
        capital_allocations = allocator.allocate(assets)
        
        # Normalize to ratios
        total_allocated = sum(capital_allocations.values())
        allocations = {
            sid: cap / total_allocated if total_allocated > 0 else 0
            for sid, cap in capital_allocations.items()
        }
        
        logger.info(
            "capital_allocation_resolved",
            num_strategies=len(actions),
            allocations={str(k)[:8]: round(v, 3) for k, v in allocations.items()},
            total_capital=round(allocator.capital, 2)
        )
        
        # Check alerts after allocation
        try:
            from autonomy.capital_engine import get_alert_engine
            alert_engine = get_alert_engine()
            alerts = alert_engine.check_all(allocator._cycle)
            if alerts:
                logger.warning(
                    "capital_alerts_triggered",
                    num_alerts=len(alerts),
                    alerts=[(a.rule_name, a.severity.value) for a in alerts]
                )
        except Exception as e:
            logger.error("alert_check_failed", error=str(e))
        
        return CapitalAllocationResult(
            allocations=allocations,
            capital_allocations=capital_allocations,
            total_capital_deployed=total_allocated,
            strategy_assets=assets
        )


@dataclass
class CapitalAllocationResult:
    """
    Result of portfolio-based capital allocation.
    
    Stage 4: Multiple strategies can execute in parallel,
    each with allocated capital.
    """
    allocations: Dict[UUID, float]  # Ratio per strategy (sum = 1.0)
    capital_allocations: Dict[UUID, float]  # Actual capital per strategy
    total_capital_deployed: float
    strategy_assets: List[Any]  # StrategyAsset objects
    
    def get_top_strategy(self) -> Optional[UUID]:
        """Get strategy with highest allocation."""
        if not self.allocations:
            return None
        return max(self.allocations.items(), key=lambda x: x[1])[0]
    
    def get_allocation_for(self, strategy_id: UUID) -> float:
        """Get allocation ratio for a specific strategy."""
        return self.allocations.get(strategy_id, 0.0)
    
    def get_capital_for(self, strategy_id: UUID) -> float:
        """Get actual capital for a specific strategy."""
        return self.capital_allocations.get(strategy_id, 0.0)
