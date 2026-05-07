# Control Plane v1.0 - Architecture Specification

## Overview

Adaptive Economic Router for LLM model selection with goal-type specific scoring and fallback chains.

## Components

### 1. Scoring Formula

```
adjusted_score = combined_score × confidence

combined_score = success × w_success + cost × w_cost + latency × w_latency
```

### 2. Normalization (min-max to [0,1])

- **cost_score**: `(max_cost - cost) / (max_cost - min_cost)` → higher = cheaper
- **latency_score**: `(max_latency - latency) / (max_latency - min_latency)` → higher = faster  
- **success_score**: `success_rate` (already [0,1])

### 3. Confidence Penalty

Prevents decisions on insufficient data:

| Sample Size | Confidence |
|-------------|------------|
| ≤10 | 0.1 (severe penalty) |
| 10-50 | Linear interpolation (0.1 → 1.0) |
| ≥50 | 1.0 (full confidence) |

### 4. Goal-Type Specific Weights (v1.0)

| Goal Type | Success | Latency | Cost |
|----------|---------|---------|------|
| precise_reasoning | 0.6 | 0.2 | 0.2 |
| cheap_generation | 0.2 | 0.5 | 0.3 |
| creative_writing | 0.7 | 0.15 | 0.15 |
| long_context | 0.5 | 0.25 | 0.25 |
| default | 0.5 | 0.2 | 0.3 |

### 5. Fallback Chain

```
qwen2.5-coder:latest → deepseek-v3.1:671b-cloud → minimax-m2:cloud
```

**Rationale:**
- qwen2.5: Local, fast (~1.5s), stable
- deepseek: Cloud backup (~1-2s), good reasoning
- minimax: Light fallback (~0.5s), minimal resource usage

## API Endpoints

### GET /llm/control/decision/trace

Returns detailed decision trace with scoring breakdown.

**Parameters:**
- `goal_type`: Task category (precise_reasoning, cheap_generation, etc.)
- `min_success_rate`: Minimum success rate filter (0.0-1.0)
- `max_latency_ms`: Maximum latency constraint
- `max_cost_per_goal`: Maximum cost per goal

**Response:**
```json
{
  "goal_type": "precise_reasoning",
  "selected_model": "ollama/qwen2.5-coder:latest",
  "candidates": [
    {
      "model_name": "ollama/qwen2.5-coder:latest",
      "eligible": true,
      "success_rate": 0.95,
      "avg_latency_ms": 1500,
      "cost_score": 0.8,
      "latency_score": 0.9,
      "combined_score": 0.85,
      "sample_confidence": 0.8,
      "adjusted_score": 0.68
    }
  ]
}
```

### GET /llm/control/recommend-model

Returns recommended model with confidence.

## Guardrails

1. **Weight Validation**: All weight sets must sum to 1.0 (checked at startup)
2. **Sample Confidence**: Minimum 10 calls required for decisions
3. **Supported Goal Types**: Frozen set (v1.0) - no dynamic expansion
4. **Fallback**: Always available if primary fails

## Test Files

- `tests/validation/test_routing_profiles.py` - Goal-type routing tests
- `tests/validation/test_rate_limit.py` - Rate limit detection
- `tests/validation/test_fallback_chain.py` - Fallback chain validation

## Production Checklist

- [x] Weights validation at startup
- [x] Goal-type specific scoring
- [x] Confidence penalty for low sample sizes
- [x] Fallback chain defined
- [ ] Real-time metrics dashboard
- [ ] A/B testing (shadow mode)
- [ ] Cost tracking per model
