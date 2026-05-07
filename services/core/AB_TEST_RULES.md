# A/B Test: Retry Strategy Effectiveness

## Decision Rule (NON-NEGOTIABLE)

```
If absolute completion delta < 5%:
    DELETE retry layer
    Simplify system
    No reinterpretation
    No "but maybe..."
```

## Metrics

| Metric | Definition |
|--------|------------|
| `completion_A` | Completion rate with max_attempts=1 |
| `completion_B` | Completion rate with max_attempts=2 |
| `delta` | completion_B - completion_A (absolute, not relative) |

## Decision Matrix

| Delta | Action |
|-------|--------|
| ≥ 8% | Keep retry, freeze implementation |
| 5-8% | Keep retry, NO enhancements |
| < 5% | DELETE retry layer immediately |

## Test Configuration

- **Sample size**: 300 goals minimum
- **Assignment**: Random 50/50 per goal
- **Seed**: Logged per goal in execution_trace
- **Duration**: 48 hours
- **Execution**: Gradual, not burst

## Protected Values

These will NOT change during test:
- MAX_ATTEMPTS = 2
- CONFIDENCE_THRESHOLD = 0.6
- Soft/hard classification logic
- Retry feedback incorporation

## Result Interpretation

- delta = 3% is a WIN (simplification justified)
- delta = 12% is a WIN (feature validated)
- delta = 5-8% is INCONCLUSIVE (keep simple, monitor longer)

**NO COGNITIVE BIAS ALLOWED**

Date frozen: 2026-02-24
Next review: 2026-02-26 (48 hours)
