# Stage 4: Capital Engine - Production Documentation

**Version:** 1.0.0  
**Status:** Production Ready  
**Date:** 2026-02-21

---

## Overview

Stage 4 introduces **portfolio-based capital allocation** to AI-OS, replacing the traditional winner-takes-all arbitration with an adaptive economic organism that:

- Allocates capital across ALL strategies based on Risk-Adjusted Return (RAR)
- Adapts to regime shifts and strategy degradation
- Survives crises with controlled drawdown
- Recovers from shocks through momentum boost

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARBITRATION LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Mode A: Single Winner (default)                              │
│   └─→ argmax(utility) → ONE strategy selected                  │
│                                                                 │
│   Mode B: Portfolio Allocation (Stage 4)                       │
│   └─→ softmax(RAR) → Capital allocated to ALL strategies       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CAPITAL ENGINE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Components:                                                   │
│   ├── CapitalAllocator (portfolio management)                  │
│   ├── AntiMonopolyGuard (diversity enforcement)               │
│   ├── FailureShockAbsorber (EMA smoothing)                    │
│   └── Adaptive Temperature (crisis response)                  │
│                                                                 │
│   Formula:                                                      │
│   RAR_i = EMA_success × payoff - cost - λ × variance          │
│   allocation_i = softmax(RAR / temperature)                    │
│   capital_{t+1} = capital_t + Σ(realized_returns)             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Modes of Operation

### Mode A: Single Winner (Default)

Traditional arbitration - best strategy wins.

```python
from autonomy.arbitration import ActionArbitrator, ArbitrationConfig

config = ArbitrationConfig(enable_capital_allocation=False)
arbitrator = ActionArbitrator(config)
result = arbitrator.resolve(actions, context)
# → Returns ONE winner
```

**Use when:**
- Simple decision making
- Only one action can execute
- Backward compatibility required

### Mode B: Portfolio Allocation (Stage 4)

Capital allocated across all strategies.

```python
from autonomy.arbitration import ActionArbitrator, ArbitrationConfig

config = ArbitrationConfig(enable_capital_allocation=True)
arbitrator = ActionArbitrator(config)
result = arbitrator.resolve_with_allocation(actions, context)
# → Returns allocations for ALL strategies
```

**Use when:**
- Multiple strategies can execute in parallel
- Economic pressure needed on underperformers
- Recovery capability required

---

## Adaptive Mechanisms

### 1. Dynamic Temperature

| State | Temperature | Behavior |
|-------|-------------|----------|
| Normal | 0.7 | Moderate redistribution |
| Crisis (DD > 5%) | 0.25 | Aggressive redistribution |

Lower temperature = more concentrated = faster adaptation.

### 2. Degradation Penalty

When EMA drops > 15% in 50 cycles:
- Allocation multiplied by 0.4 (60% reduction)
- Prevents capital drain to failing strategies

### 3. Momentum Boost

When EMA > 0.55 and allocation < 40%:
- Allocation multiplied by 1.2 (20% boost)
- Accelerates recovery of rising strategies

### 4. Hard Cap for Weak Strategies

When EMA < 0.5:
- Max allocation = 25%
- Forces capital to better performers

---

## Configuration

### Default Values (Production-Tuned)

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `initial_capital` | 1000 | Starting capital |
| `payoff_per_success` | 0.008 (+0.8%) | Return on success |
| `loss_per_failure` | 0.007 (-0.7%) | Loss on failure |
| `execution_cost` | 0.002 (0.2%) | Transaction cost |
| `capital_utilization_rate` | 0.15 (15%) | Capital per cycle |
| `softmax_temperature_base` | 0.7 | Normal temperature |
| `softmax_temperature_crisis` | 0.25 | Crisis temperature |
| `ema_drop_penalty_factor` | 0.4 | Degradation penalty |
| `weak_strategy_max_allocation` | 0.25 | Hard cap |
| `bankruptcy_threshold` | 0.1 (10%) | Death threshold |

---

## API Endpoints

### Status Monitoring

```bash
# Get current capital status
GET /capital/status

Response:
{
  "capital": {
    "current": 1040.23,
    "initial": 1000.0,
    "peak": 1095.81,
    "total_return_pct": 4.02,
    "drawdown_pct": 5.07,
    "is_bankrupt": false
  },
  "mode": {
    "temperature": "crisis",
    "utilization_rate": 0.15,
    "cycle": 1000
  }
}
```

### Allocation Distribution

```bash
# Get current allocations
GET /capital/allocations

Response:
{
  "allocations": {
    "distribution": {"strategy_a": 354, "strategy_b": 393, "strategy_c": 253},
    "normalized": {"strategy_a": 0.354, "strategy_b": 0.393, "strategy_c": 0.253}
  },
  "metrics": {
    "top_strategy": "strategy_b",
    "concentration_pct": 39.3,
    "diversity_entropy": 1.52,
    "unique_strategies": 3
  }
}
```

### EMA Tracking

```bash
# Get EMA values
GET /capital/ema

Response:
{
  "ema": {
    "values": {"strategy_a": 0.653, "strategy_b": 0.687, "strategy_c": 0.616},
    "drop_flags": {"strategy_a": false, "strategy_b": false, "strategy_c": false},
    "shock_status": {"strategy_a": false, "strategy_b": false, "strategy_c": false}
  }
}
```

### Configuration

```bash
# Get current config
GET /capital/config
```

### History

```bash
# Get recent history
GET /capital/history?last_n=100
```

### Reset

```bash
# Reset to initial state (WARNING: clears all history)
POST /capital/reset
```

---

## Validation Results

### Monte-Carlo (3000 cycles)

| Scenario | Regime Shifts | Max DD | Return | Result |
|----------|---------------|--------|--------|--------|
| Adversarial | 5 + noise | 46.8% | -42.8% | Stress test |
| **Realistic** | 2 shifts | **17.5%** | **-1.5%** | ✅ PASS |

### Regime Shift Test (1000 cycles)

| Metric | Result |
|--------|--------|
| Survival | ✅ Yes |
| Max Drawdown | 5.1% |
| Crisis Adaptation | 38% → 27% → 35% |
| Concentration | 39% (no monopoly) |

---

## Survival Assumptions

The system assumes:

1. **Maximum 50% drawdown** is survivable
2. **Bankruptcy threshold = 10%** of initial capital
3. **Regime shifts are temporary** - recovery is possible
4. **Multiple strategies exist** - diversity is possible
5. **Costs are known** - predictable economics

---

## Known Limitations

1. **No recovery to peak** after permanent alpha degradation
2. **Adaptation lag** of ~50 cycles (EMA window)
3. **Assumes independent strategies** (no correlation tracking)
4. **Single currency** (no multi-asset support)

---

## Future Enhancements (Stage 5)

- Multi-asset correlation tracking
- Cross-strategy risk analysis
- Tail event modeling
- Dynamic payoff estimation
- Portfolio optimization

---

## Changelog

### v1.0.0 (2026-02-21)
- Initial production release
- Monte-Carlo validation complete
- API endpoints operational
- Integration with arbitration.py

---

## References

- Stage 3 Documentation: `/docs/stage3_arbitration.md`
- Test Suite: `/tests/stress/test_capital.py`
- Monte-Carlo: `/tests/stress/test_monte_carlo.py`
- Integration Test: `/tests/stress/test_integration_smoke.py`
