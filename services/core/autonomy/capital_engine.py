"""
CAPITAL ENGINE - Stage 4 Economic Layer
=======================================

Transforms utility-based arbitration into portfolio capital allocation.

Architecture:
    Stage 3: argmax(utility) → 1 winner
    Stage 4: softmax(RAR) → capital allocation with compound growth

Key Concepts:
    - Capital can grow or die
    - Strategies are investment assets
    - Diversity = insurance premium
    - Bankruptcy is possible

Formula:
    RAR_i = EMA_success_i × payoff_i - cost_i - λ × variance_i
    allocation_i = softmax(RAR_i / temperature)
    capital_{t+1} = capital_t + Σ(realized_profits) - Σ(costs)

Alert System:
    - AlertRule: Define threshold + action
    - AlertEngine: Check rules on each cycle
    - Alerts: drawdown, concentration, crisis_duration, bankruptcy_proximity

Author: AI-OS Team
Date: 2026-02-21
Version: 1.0.0
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from uuid import UUID
from enum import Enum
import math
import json

from logging_config import get_logger

logger = get_logger(__name__)


# ============================================================
# ALERT SYSTEM
# ============================================================

class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class Alert:
    """A triggered alert."""
    rule_name: str
    severity: AlertSeverity
    message: str
    value: float
    threshold: float
    timestamp: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class AlertRule:
    """Rule for triggering alerts."""
    name: str
    description: str
    check_fn: Callable[[], Tuple[bool, float, str]]  # (triggered, value, message)
    severity: AlertSeverity
    cooldown_cycles: int = 10  # Don't re-alert for N cycles
    last_triggered_cycle: int = -100


class AlertEngine:
    """
    Monitors capital engine and triggers alerts.
    
    Alert Rules:
    1. drawdown_high: drawdown > 8%
    2. concentration_high: max allocation > 55%
    3. crisis_extended: crisis mode > 50 cycles
    4. bankruptcy_proximity: capital < 20% of initial
    5. ema_mass_degradation: > 50% strategies with EMA < 0.5
    """
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: List[Alert] = []
        self._cycle = 0
        
        # Register default rules
        self._register_default_rules()
    
    def _register_default_rules(self):
        """Register built-in alert rules."""
        pass  # Rules registered dynamically with check_fn
    
    def register_rule(
        self,
        name: str,
        description: str,
        check_fn: Callable[[], Tuple[bool, float, str]],
        severity: AlertSeverity,
        cooldown_cycles: int = 10
    ):
        """Register a new alert rule."""
        self.rules[name] = AlertRule(
            name=name,
            description=description,
            check_fn=check_fn,
            severity=severity,
            cooldown_cycles=cooldown_cycles
        )
    
    def check_all(self, cycle: int) -> List[Alert]:
        """
        Check all rules and return triggered alerts.
        
        Args:
            cycle: Current cycle number
            
        Returns:
            List of newly triggered alerts
        """
        self._cycle = cycle
        new_alerts = []
        
        for rule in self.rules.values():
            # Check cooldown
            if cycle - rule.last_triggered_cycle < rule.cooldown_cycles:
                continue
            
            # Run check
            try:
                triggered, value, message = rule.check_fn()
                
                if triggered:
                    alert = Alert(
                        rule_name=rule.name,
                        severity=rule.severity,
                        message=message,
                        value=value,
                        threshold=0.0,  # Set by check_fn
                        timestamp=datetime.utcnow().isoformat()
                    )
                    
                    new_alerts.append(alert)
                    self.alerts.append(alert)
                    rule.last_triggered_cycle = cycle
                    
                    # Log alert
                    log_level = {
                        AlertSeverity.INFO: logger.info,
                        AlertSeverity.WARNING: logger.warning,
                        AlertSeverity.CRITICAL: logger.error,
                        AlertSeverity.EMERGENCY: logger.critical
                    }[rule.severity]
                    
                    log_level(
                        "capital_alert",
                        rule=rule.name,
                        severity=rule.severity.value,
                        value=round(value, 3),
                        message=message,
                        cycle=cycle
                    )
            
            except Exception as e:
                logger.error("alert_check_failed", rule=rule.name, error=str(e))
        
        return new_alerts
    
    def get_active_alerts(self, last_n: int = 10) -> List[Alert]:
        """Get recent alerts."""
        return self.alerts[-last_n:]
    
    def clear_alerts(self):
        """Clear all alerts."""
        self.alerts.clear()


def create_alert_engine(allocator: 'CapitalAllocator') -> AlertEngine:
    """
    Create alert engine with rules bound to a specific allocator.
    
    Args:
        allocator: CapitalAllocator to monitor
        
    Returns:
        Configured AlertEngine
    """
    from autonomy.stability_guards import get_anti_monopoly_guard, get_failure_shock_absorber
    
    engine = AlertEngine()
    guard = get_anti_monopoly_guard()
    shock_absorber = get_failure_shock_absorber()
    
    # Rule 1: High drawdown
    def check_drawdown() -> Tuple[bool, float, str]:
        dd = allocator.drawdown
        threshold = 0.08
        triggered = dd > threshold
        msg = f"Drawdown {dd*100:.1f}% exceeds {threshold*100:.0f}%"
        return triggered, dd, msg
    
    engine.register_rule(
        name="drawdown_high",
        description="Drawdown exceeds 8%",
        check_fn=check_drawdown,
        severity=AlertSeverity.WARNING,
        cooldown_cycles=20
    )
    
    # Rule 2: High concentration
    def check_concentration() -> Tuple[bool, float, str]:
        stats = guard.get_stats()
        dist = stats.get('distribution', {})
        if not dist:
            return False, 0.0, "No distribution data"
        
        total = sum(dist.values())
        if total == 0:
            return False, 0.0, "No allocations"
        
        max_alloc = max(dist.values()) / total
        threshold = 0.55
        triggered = max_alloc > threshold
        msg = f"Concentration {max_alloc*100:.1f}% exceeds {threshold*100:.0f}%"
        return triggered, max_alloc, msg
    
    engine.register_rule(
        name="concentration_high",
        description="Single strategy exceeds 55% allocation",
        check_fn=check_concentration,
        severity=AlertSeverity.WARNING,
        cooldown_cycles=30
    )
    
    # Rule 3: Extended crisis mode
    def check_crisis_duration() -> Tuple[bool, float, str]:
        # Count recent cycles in crisis
        crisis_threshold = allocator.config.drawdown_threshold_for_crisis
        # This is approximate - we check if currently in crisis
        in_crisis = allocator.drawdown > crisis_threshold
        if not in_crisis:
            return False, 0.0, "Not in crisis"
        
        # For now, just alert if in crisis at all
        # Full implementation would track crisis duration
        threshold = 1
        msg = f"System in crisis mode (DD > {crisis_threshold*100:.0f}%)"
        return True, allocator.drawdown, msg
    
    engine.register_rule(
        name="crisis_mode",
        description="System is in crisis mode",
        check_fn=check_crisis_duration,
        severity=AlertSeverity.WARNING,
        cooldown_cycles=50
    )
    
    # Rule 4: Bankruptcy proximity
    def check_bankruptcy_proximity() -> Tuple[bool, float, str]:
        proximity = allocator.capital / allocator.config.initial_capital
        threshold = 0.2
        triggered = proximity < threshold
        msg = f"Capital at {proximity*100:.1f}% of initial (bankruptcy at 10%)"
        return triggered, proximity, msg
    
    engine.register_rule(
        name="bankruptcy_proximity",
        description="Capital below 20% of initial",
        check_fn=check_bankruptcy_proximity,
        severity=AlertSeverity.CRITICAL,
        cooldown_cycles=10
    )
    
    # Rule 5: Mass EMA degradation
    def check_ema_degradation() -> Tuple[bool, float, str]:
        stats = guard.get_stats()
        dist = stats.get('distribution', {})
        
        if not dist:
            return False, 0.0, "No distribution data"
        
        degraded_count = 0
        for strategy_id in dist.keys():
            ema = shock_absorber.get_ema_success(strategy_id)
            if ema < 0.5:
                degraded_count += 1
        
        total = len(dist)
        if total == 0:
            return False, 0.0, "No strategies"
        
        degraded_ratio = degraded_count / total
        threshold = 0.5
        triggered = degraded_ratio > threshold
        msg = f"{degraded_count}/{total} strategies have EMA < 0.5"
        return triggered, degraded_ratio, msg
    
    engine.register_rule(
        name="ema_mass_degradation",
        description=">50% strategies with EMA below 0.5",
        check_fn=check_ema_degradation,
        severity=AlertSeverity.WARNING,
        cooldown_cycles=25
    )
    
    # Rule 6: Critical drawdown
    def check_critical_drawdown() -> Tuple[bool, float, str]:
        dd = allocator.drawdown
        threshold = 0.20
        triggered = dd > threshold
        msg = f"CRITICAL: Drawdown {dd*100:.1f}% exceeds {threshold*100:.0f}%"
        return triggered, dd, msg
    
    engine.register_rule(
        name="drawdown_critical",
        description="Drawdown exceeds 20%",
        check_fn=check_critical_drawdown,
        severity=AlertSeverity.CRITICAL,
        cooldown_cycles=5
    )
    
    return engine


# Global alert engine (created on demand)
_alert_engine: Optional[AlertEngine] = None


def get_alert_engine() -> AlertEngine:
    """Get or create global alert engine."""
    global _alert_engine
    if _alert_engine is None:
        from autonomy.capital_engine import get_capital_allocator
        allocator = get_capital_allocator()
        _alert_engine = create_alert_engine(allocator)
    return _alert_engine


# ============================================================
# CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class CapitalConfig:
    """
    Immutable configuration for capital engine.
    
    REALISTIC baseline for economic viability:
    - Initial capital: 1000
    - Payoff: +0.8% per success (THIN margins)
    - Loss: -0.7% per failure
    - Cost: 0.2% per execution
    - Utilization: 15% per cycle (liquidity constraint)
    - Stochastic returns: YES (real variance)
    - Adaptive temperature: YES (drawdown-responsive)
    - Degradation penalty: YES (EMA-drop triggered)
    
    CRITICAL: EV is thin (~0.1-0.3% per cycle).
    System CAN grow, but CAN also die.
    Survival > Growth.
    Adaptability = Recovery capability.
    """
    initial_capital: float = 1000.0
    
    payoff_per_success: float = 0.008      # +0.8%
    loss_per_failure: float = 0.007        # -0.7%
    execution_cost: float = 0.002          # 0.2%
    
    capital_utilization_rate: float = 0.15  # Only 15% per cycle
    
    risk_aversion_lambda: float = 0.5
    max_allocation_per_strategy: float = 0.5
    min_allocation_per_strategy: float = 0.01
    
    # Adaptive temperature
    softmax_temperature_base: float = 0.7
    softmax_temperature_crisis: float = 0.25  # Sharper during drawdown (was 0.35)
    drawdown_threshold_for_crisis: float = 0.05  # 5% drawdown triggers crisis mode
    
    # Degradation penalty
    enable_degradation_penalty: bool = True
    ema_drop_threshold: float = 0.15  # 15% EMA drop triggers penalty
    ema_drop_penalty_factor: float = 0.4  # 60% allocation reduction (was 0.6)
    ema_drop_lookback: int = 50  # Cycles to look back for EMA drop
    
    # Recovery boost
    enable_momentum_boost: bool = True
    momentum_boost_threshold: float = 0.55  # EMA > this gets boost
    momentum_boost_factor: float = 1.2  # 20% boost
    momentum_boost_max_allocation: float = 0.4  # Only if current allocation < this
    
    # Hard cap for weak strategies
    weak_strategy_ema_threshold: float = 0.5  # EMA < this is weak
    weak_strategy_max_allocation: float = 0.25  # Max 25% for weak
    
    bankruptcy_threshold: float = 0.1  # 10% of initial = bankrupt
    
    enable_stochastic_returns: bool = True
    return_noise_sigma: float = 0.003  # 0.3% noise


# ============================================================
# STRATEGY AS ASSET
# ============================================================

@dataclass
class StrategyAsset:
    """
    A strategy as an investment asset.
    
    Each strategy has:
    - EMA success rate (from FailureShockAbsorber)
    - Payoff profile
    - Cost profile
    - Variance proxy
    - EMA drop penalty flag (for adaptive allocation)
    """
    strategy_id: UUID
    name: str
    ema_success: float
    
    payoff: float
    cost: float
    variance_proxy: float
    
    allocation: float = 0.0
    capital_allocated: float = 0.0
    ema_drop_penalty: bool = False  # Flag for degradation penalty
    
    @property
    def expected_value(self) -> float:
        """Expected value = EMA_success × payoff - cost"""
        return self.ema_success * self.payoff - self.cost
    
    @property
    def risk_adjusted_return(self) -> float:
        """RAR = EV - λ × variance"""
        return self.expected_value - 0.5 * self.variance_proxy


# ============================================================
# CAPITAL ALLOCATION
# ============================================================

@dataclass
class AllocationResult:
    """Result of capital allocation."""
    cycle: int
    timestamp: str
    
    # Allocations
    allocations: Dict[str, float]
    
    # Capital state
    capital_before: float
    capital_after: float
    
    # Metrics
    total_return: float
    max_drawdown: float
    dominant_capital_share: float
    
    # Strategy details
    strategy_rars: Dict[str, float]
    strategy_returns: Dict[str, float]


class CapitalAllocator:
    """
    Portfolio capital allocator.
    
    Replaces argmax selection with softmax allocation.
    Enforces constraints:
    - Max allocation per strategy
    - Capital budget
    - Diversity floor
    """
    
    def __init__(self, config: Optional[CapitalConfig] = None):
        self.config = config or CapitalConfig()
        self.capital = self.config.initial_capital
        self.peak_capital = self.capital
        
        self._cycle = 0
        self._history: List[AllocationResult] = []
    
    def allocate(
        self,
        strategy_assets: List[StrategyAsset]
    ) -> Dict[UUID, float]:
        """
        Allocate capital across strategies using softmax.
        
        Args:
            strategy_assets: List of strategy assets with EMA, payoff, cost, variance
            
        Returns:
            Dict mapping strategy_id to capital allocated
        """
        self._cycle += 1
        
        if not strategy_assets:
            return {}
        
        # Calculate RAR for each strategy
        rars = {}
        for asset in strategy_assets:
            rars[asset.strategy_id] = asset.risk_adjusted_return
        
        # Softmax allocation (with adaptive temperature and degradation penalty)
        allocations = self._softmax_allocate(rars, strategy_assets)
        
        # Apply constraints
        allocations = self._apply_constraints(allocations)
        
        # Calculate capital per strategy (with utilization cap)
        deployable_capital = self.capital * self.config.capital_utilization_rate
        capital_allocations = {}
        for sid, alloc in allocations.items():
            capital_allocations[sid] = alloc * deployable_capital
        
        # Log allocation
        logger.info(
            "capital_allocated",
            cycle=self._cycle,
            capital=round(self.capital, 2),
            allocations={str(k)[:8]: round(v, 3) for k, v in allocations.items()},
            dominant_share=round(max(allocations.values()), 3)
        )
        
        return capital_allocations
    
    def _softmax_allocate(
        self, 
        rars: Dict[UUID, float],
        strategy_assets: Optional[List] = None
    ) -> Dict[UUID, float]:
        """
        Apply softmax with ADAPTIVE temperature to RAR values.
        
        ADAPTIVE BEHAVIOR (v2 - Recovery-enhanced):
        - Base temperature: 0.7 (moderate)
        - Crisis temperature: 0.25 (sharper) when drawdown > 5%
        - Degradation penalty: 0.4x for strategies with EMA drop > 15%
        - Hard cap: max 25% allocation for strategies with EMA < 0.5
        - Momentum boost: 1.2x for strategies with EMA > 0.55 and low allocation
        
        This makes the system ADAPTIVE + RECOVERY-CAPABLE.
        During crisis → faster redistribution.
        During recovery → momentum boost for rising strategies.
        """
        if not rars:
            return {}
        
        # 1. Determine temperature based on drawdown
        current_drawdown = self.drawdown
        if current_drawdown > self.config.drawdown_threshold_for_crisis:
            temp = self.config.softmax_temperature_crisis
            logger.debug(
                "crisis_mode_temperature",
                drawdown=round(current_drawdown, 3),
                temperature=temp
            )
        else:
            temp = self.config.softmax_temperature_base
        
        # 2. Shift RARs to be positive (for softmax)
        min_rar = min(rars.values())
        shifted_rars = {k: v - min_rar + 0.1 for k, v in rars.items()}
        
        # 3. Apply degradation penalty if enabled
        if self.config.enable_degradation_penalty and strategy_assets:
            for asset in strategy_assets:
                sid = asset.strategy_id
                if sid in shifted_rars:
                    if hasattr(asset, 'ema_drop_penalty') and asset.ema_drop_penalty:
                        shifted_rars[sid] *= self.config.ema_drop_penalty_factor
                        logger.debug(
                            "degradation_penalty_applied",
                            strategy_id=str(sid)[:8],
                            penalty_factor=self.config.ema_drop_penalty_factor
                        )
        
        # 4. Apply temperature
        exp_rars = {k: math.exp(v / temp) for k, v in shifted_rars.items()}
        
        # 5. Normalize
        total = sum(exp_rars.values())
        allocations = {k: v / total for k, v in exp_rars.items()}
        
        # 6. Apply hard cap for weak strategies (EMA < threshold)
        if strategy_assets:
            for asset in strategy_assets:
                sid = asset.strategy_id
                if sid in allocations and asset.ema_success < self.config.weak_strategy_ema_threshold:
                    if allocations[sid] > self.config.weak_strategy_max_allocation:
                        logger.debug(
                            "weak_strategy_capped",
                            strategy_id=str(sid)[:8],
                            ema=round(asset.ema_success, 3),
                            old_alloc=round(allocations[sid], 3),
                            new_alloc=self.config.weak_strategy_max_allocation
                        )
                        allocations[sid] = self.config.weak_strategy_max_allocation
        
        # 7. Apply momentum boost for recovering strategies
        if self.config.enable_momentum_boost and strategy_assets:
            for asset in strategy_assets:
                sid = asset.strategy_id
                if sid in allocations:
                    if (asset.ema_success > self.config.momentum_boost_threshold and
                        allocations[sid] < self.config.momentum_boost_max_allocation):
                        old_alloc = allocations[sid]
                        allocations[sid] *= self.config.momentum_boost_factor
                        logger.debug(
                            "momentum_boost_applied",
                            strategy_id=str(sid)[:8],
                            ema=round(asset.ema_success, 3),
                            old_alloc=round(old_alloc, 3),
                            new_alloc=round(allocations[sid], 3)
                        )
        
        # 8. Re-normalize to ensure sum = 1.0
        total_alloc = sum(allocations.values())
        if total_alloc > 0 and abs(total_alloc - 1.0) > 0.001:
            allocations = {k: v / total_alloc for k, v in allocations.items()}
        
        return allocations
    
    def _apply_constraints(
        self, 
        allocations: Dict[UUID, float]
    ) -> Dict[UUID, float]:
        """
        Apply allocation constraints:
        1. Max allocation per strategy
        2. Min allocation per strategy (diversity floor)
        """
        max_alloc = self.config.max_allocation_per_strategy
        min_alloc = self.config.min_allocation_per_strategy
        
        # Cap allocations above max
        excess = 0.0
        for sid in allocations:
            if allocations[sid] > max_alloc:
                excess += allocations[sid] - max_alloc
                allocations[sid] = max_alloc
        
        # Redistribute excess to strategies below max
        if excess > 0:
            eligible = [sid for sid in allocations if allocations[sid] < max_alloc]
            if eligible:
                per_strategy = excess / len(eligible)
                for sid in eligible:
                    allocations[sid] = min(max_alloc, allocations[sid] + per_strategy)
        
        # Ensure minimum allocation (diversity floor)
        num_strategies = len(allocations)
        if num_strategies > 0:
            min_per_strategy = min(min_alloc, 1.0 / num_strategies)
            for sid in allocations:
                if allocations[sid] < min_per_strategy:
                    allocations[sid] = min_per_strategy
            
            # Renormalize
            total = sum(allocations.values())
            allocations = {k: v / total for k, v in allocations.items()}
        
        return allocations
    
    def record_outcome(
        self,
        strategy_id: UUID,
        capital_allocated: float,
        success: bool,
        variance_proxy: float = 0.0
    ) -> float:
        """
        Record outcome and update capital.
        
        Args:
            strategy_id: Strategy that was executed
            capital_allocated: Capital that was allocated
            success: Whether execution succeeded
            variance_proxy: Variance for stochastic noise
            
        Returns:
            Realized return (positive or negative)
        """
        import random
        
        # Calculate return
        if success:
            gross_return = capital_allocated * self.config.payoff_per_success
        else:
            gross_return = -capital_allocated * self.config.loss_per_failure
        
        # Deduct execution cost
        cost = capital_allocated * self.config.execution_cost
        net_return = gross_return - cost
        
        # Add stochastic noise (real variance)
        if self.config.enable_stochastic_returns:
            sigma = self.config.return_noise_sigma * capital_allocated
            noise = random.gauss(0, sigma)
            net_return += noise
        
        # Update capital
        self.capital += net_return
        
        # Update peak (for drawdown calculation)
        if self.capital > self.peak_capital:
            self.peak_capital = self.capital
        
        logger.debug(
            "outcome_recorded",
            cycle=self._cycle,
            strategy_id=str(strategy_id)[:8],
            success=success,
            allocated=round(capital_allocated, 2),
            gross_return=round(gross_return, 2),
            cost=round(cost, 2),
            net_return=round(net_return, 2),
            capital_after=round(self.capital, 2)
        )
        
        return net_return
    
    @property
    def drawdown(self) -> float:
        """Current drawdown from peak."""
        if self.peak_capital <= 0:
            return 1.0
        return (self.peak_capital - self.capital) / self.peak_capital
    
    @property
    def total_return(self) -> float:
        """Total return from initial capital."""
        return (self.capital - self.config.initial_capital) / self.config.initial_capital
    
    @property
    def is_bankrupt(self) -> bool:
        """Check if system is bankrupt."""
        return self.capital < self.config.initial_capital * self.config.bankruptcy_threshold
    
    def get_statistics(self) -> Dict:
        """Get current capital statistics."""
        return {
            "cycle": self._cycle,
            "capital": round(self.capital, 2),
            "initial_capital": self.config.initial_capital,
            "peak_capital": round(self.peak_capital, 2),
            "total_return_pct": round(self.total_return * 100, 2),
            "drawdown_pct": round(self.drawdown * 100, 2),
            "is_bankrupt": self.is_bankrupt
        }
    
    def reset(self):
        """Reset capital engine."""
        self.capital = self.config.initial_capital
        self.peak_capital = self.capital
        self._cycle = 0
        self._history.clear()


# ============================================================
# SINGLETON
# ============================================================

_capital_allocator: Optional[CapitalAllocator] = None


def get_capital_allocator(config: Optional[CapitalConfig] = None) -> CapitalAllocator:
    """Get or create global capital allocator."""
    global _capital_allocator
    if _capital_allocator is None:
        _capital_allocator = CapitalAllocator(config)
    return _capital_allocator


def reset_capital_allocator():
    """Reset global capital allocator."""
    global _capital_allocator
    if _capital_allocator:
        _capital_allocator.reset()
