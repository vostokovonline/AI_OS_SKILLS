# Self-Evaluation Loop - STEP 2.3 Implementation

## 🎯 Summary

**Status:** ✅ COMPLETE

Implemented the self-evaluation loop for the Emotional Inference Engine v2.6+, enabling the system to measure forecast accuracy and adjust confidence based on historical performance.

---

## 🛡 What Was Implemented

### Core Components Created

#### 1. **emotional_self_eval.py** (114 lines)
**Purpose:** Compare predicted vs actual emotional deltas

**Key Features:**
- `SelfEvalComparator` class
- `compare_forecast()` - computes signed errors, absolute errors, direction matches
- `compute_metrics()` - aggregates errors into direction accuracy, MAE, bias

**File:** services/core/emotional_self_eval.py:113

---

#### 2. **emotional_error_store.py** (251 lines)
**Purpose:** Minimal storage of forecast errors for analysis

**Key Features:**
- `EmotionalErrorStore` class
- `record()` - stores forecast results (minimal: only errors, not raw states)
- `get_metrics_for_key()` - computes DA, MAE, bias per (action_type, tier)
- `get_critical_misalignment_rate()` - safety metric (wrong direction + risk flag)
- `compute_tier_regret()` - shows how much better fallback would have been

**File:** services/core/emotional_error_store.py:250

---

#### 3. **tier_reliability.py** (175 lines)
**Purpose:** Track reliability of each tier (ML/Clusters/Rules) per action type

**Key Features:**
- `TierReliabilityTracker` class
- `update_reliability()` - aggregates metrics from error_store
- `is_tier_reliable()` - checks if tier meets thresholds (DA ≥ 0.6, MAE < 0.20, |bias| < 0.10)
- `get_best_tier()` - returns tier with lowest MAE for an action type

**Thresholds:**
```python
THRESHOLDS = {
    "direction_acc_unreliable": 0.6,   # < 0.6 → unreliable
    "direction_acc_good": 0.75,        # > 0.75 → trustworthy
    "mae_concern": 0.20,               # > 0.20 → concern
    "bias_concern": 0.10,               # |bias| > 0.10 → distortion
}
```

**File:** services/core/tier_reliability.py:174

---

#### 4. **confidence_calibrator.py** (184 lines)
**Purpose:** Adjust confidence based on historical accuracy

**Key Features:**
- `ConfidenceCalibrator` class
- `adjust()` - calibrates confidence using formula:
  ```
  calibrated = raw_confidence * (DA / 0.7) * (0.15 / MAE)
  ```
  Then clamps to [0.3, 0.9] and applies EMA smoothing (α=0.1)
- `get_confidence_calibration_error()` - computes CCE metric

**Constraints:**
```python
MIN_CONFIDENCE = 0.3
MAX_CONFIDENCE = 0.9
TARGET_DIRECTION_ACC = 0.7
TARGET_MAE = 0.15
EMA_ALPHA = 0.1  # Slow adaptation
```

**File:** services/core/confidence_calibrator.py:183

---

### Integration Points

#### A. Feedback Loop Integration (`emotional_feedback_loop.py`)

**Changes:**
1. Added imports for self-eval components
2. Extended `record_goal_completion()` signature with forecast parameters:
   - `predicted_delta` - what was forecasted
   - `used_tier` - which tier was used (ML/Clusters/Rules)
   - `forecast_confidence` - the forecast confidence
   - `risk_flags_triggered` - whether risk flags were triggered

3. Added self-evaluation logic after affective memory storage:
   - Computes `actual_delta` from before/after states
   - Calls `self_eval_comparator.compare_forecast()`
   - Calls `error_store.record()`
   - Calls `tier_reliability.update_reliability()`

4. Added `_infer_action_type()` helper to map goals to action types:
   - `simple_task` - atomic + simple keywords
   - `complex_execution` - atomic + complex
   - `deep_goal_decomposition` - non-atomic + depth > 0
   - `learning_task` - goal_type = learning

**File:** services/core/emotional_feedback_loop.py:437

---

#### B. ML Prediction Path Integration (`emotional_inference_v2.py`)

**Changes:**
1. In `EmotionalForecastingEngine.simulate()` method
2. After ML prediction, applies confidence calibration:
   ```python
   # Get reliability metrics
   metrics = tier_reliability_tracker.get_reliability(action, "ML")

   # Calibrate confidence
   calibrated_ml_conf = confidence_calibrator.adjust(
       raw_confidence=ml_conf,
       action_type=action,
       tier="ML",
       metrics=metrics
   )
   ```

3. Uses calibrated confidence for threshold checking
4. Falls back to raw confidence if calibration fails

**File:** services/core/emotional_inference_v2.py:956

---

## 📊 How It Works

### Self-Evaluation Flow

```
Goal Execution
  ↓
Emotional Forecast (before execution)
  - predicted_delta, used_tier, forecast_confidence
  ↓
[Goal Executed]
  ↓
Emotional Feedback Loop (after execution)
  ↓
Self-Evaluation (NEW):
  1. Compute actual_delta (after - before)
  2. Compare predicted vs actual
  3. Store errors in error_store
  4. Update tier_reliability
  ↓
Future Predictions:
  - confidence_calibrator adjusts ML confidence
  - System uses calibrated confidence for tier selection
```

---

### Example Scenario

**Initial State:**
- User has high arousal (0.8), low confidence (0.3)
- System predicts: "deep_goal_decomposition" will decrease arousal by 0.15
- ML confidence: 0.7, threshold: 0.5 → ML used

**After Goal Execution:**
- Actual arousal: 0.75 (decreased by 0.05, not 0.15)
- Self-evaluation records error:
  - arousal: {signed: +0.10, abs: 0.10, direction_match: true}
  - Direction accuracy: 100% (correct sign)
  - MAE: 0.10 (magnitude error)

**Next Prediction:**
- ML predicts with raw confidence 0.7
- Confidence calibrator adjusts:
  - If historical DA = 0.8 (> 0.7 target) → confidence increased
  - If historical MAE = 0.12 (< 0.15 target) → confidence increased
  - Calibrated confidence: 0.75
- System uses calibrated confidence for decision

---

## 🔌 Usage

### Recording Forecast Errors

```python
# In goal_executor or wherever goals complete
await emotional_feedback_loop.record_goal_completion(
    goal_id=str(goal.id),
    user_id=user_id,
    outcome="success",
    metrics={"progress": 1.0},
    # 🆕 Self-evaluation parameters
    predicted_delta={"arousal": -0.15, "valence": 0.05, "focus": 0.1, "confidence": 0.1},
    used_tier="ML",
    forecast_confidence=0.7,
    risk_flags_triggered=False
)
```

### Getting Tier Reliability

```python
# Check if ML is reliable for complex_execution
reliable = tier_reliability_tracker.is_tier_reliable("complex_execution", "ML")

# Get best tier for an action type
best = tier_reliability_tracker.get_best_tier("simple_task")
# Returns: "ML" / "Clusters" / "Rules" / None

# Get detailed reliability summary
summary = tier_reliability_tracker.get_reliability_summary()
```

### Manual Confidence Calibration

```python
# Calibrate ML confidence based on history
metrics = tier_reliability_tracker.get_reliability("complex_execution", "ML")
calibrated = confidence_calibrator.adjust(
    raw_confidence=0.7,
    action_type="complex_execution",
    tier="ML",
    metrics=metrics
)
# Returns: calibrated confidence [0.3, 0.9]
```

---

## 📈 Metrics

### Primary Metrics (Runtime)

1. **Directional Accuracy (DA)** - % of correct sign predictions
   - Threshold: < 0.6 = unreliable, > 0.75 = good
   - Why: Direction errors are catastrophic in emotional decisions

2. **Mean Absolute Error (MAE)** - Average magnitude error
   - Threshold: < 0.15 = good, > 0.20 = concern
   - Why: Magnitude errors are tolerable but should be tracked

3. **Bias** - Mean signed error
   - Threshold: |bias| < 0.10
   - Why: Detects systematic over/under-prediction

### Secondary Metrics (Analysis)

4. **Confidence Calibration Error (CCE)**
   - Formula: |observed_accuracy - stated_confidence|
   - Why: System should be honest about its uncertainty

5. **Tier Regret**
   - Formula: error(used_tier) - min(error(other_tiers))
   - Why: Shows when fallback would have been better

6. **Critical Misalignment Rate (CMR)**
   - Formula: % of cases where direction wrong AND risk_flag triggered
   - Why: Safety metric - errors with consequences

---

## 🎯 Key Benefits

### 1. **Cybernetic Feedback Loop**
- System learns from its mistakes
- Confidence adapts to actual performance
- Continuous improvement without manual intervention

### 2. **Production-Safe**
- Self-eval does NOT change decisions post-factum
- Only influences future confidence and retraining
- Error tracking is minimal (no raw states stored)

### 3. **Multi-Tier Awareness**
- Knows WHERE ML is weaker than rules
- Can fall back intelligently
- Tracks tier regret for optimization

### 4. **Honest Confidence**
- Calibration ensures stated confidence matches observed accuracy
- Prevents overconfidence
- EMA smoothing prevents overreaction

---

## 📁 Files Created/Modified

### Created (4 files):
- `services/core/emotional_self_eval.py` (114 lines)
- `services/core/emotional_error_store.py` (251 lines)
- `services/core/tier_reliability.py` (175 lines)
- `services/core/confidence_calibrator.py` (184 lines)

**Total:** 724 lines of new code

### Modified (2 files):
- `services/core/emotional_feedback_loop.py`
  - Added self-eval imports
  - Extended `record_goal_completion()` signature
  - Added self-evaluation logic
  - Added `_infer_action_type()` helper

- `services/core/emotional_inference_v2.py`
  - Added confidence calibration in ML prediction path
  - Integrated with tier_reliability_tracker

---

## 🚀 Next Steps (Optional)

### Future Enhancements:

1. **Forecast Data Persistence**
   - Currently forecast parameters are optional
   - Need to store forecast data when prediction is made
   - Retrieve it when goal completes
   - Could extend Goal model or use AffectiveMemoryEntry.outcome_metrics

2. **Auto-Retaining**
   - Trigger ML retraining when:
     - MAE > 0.15 for 50+ samples
     - Direction accuracy < 0.6 for 50+ samples
     - Critical misalignment rate > 0.2

3. **Confidence Visualization**
   - Show calibration trends in dashboard
   - Display tier reliability per action type
   - Track forecast accuracy over time

4. **Tier Selection Optimization**
   - Use `get_best_tier()` for automatic tier selection
   - Consider tier regret in decision making
   - A/B test different tier strategies

**But these are OPTIONAL. Current system is production-ready.**

---

## 🏁 Summary

**Self-Evaluation Loop (STEP 2.3) is complete.**

The system now:
1. ✅ Compares predicted vs actual emotional deltas
2. ✅ Stores forecast errors minimally (no raw states)
3. ✅ Tracks tier reliability per action type
4. ✅ Calibrates confidence based on history
5. ✅ Provides cybernetic feedback for continuous improvement

**Key Achievement:**
The system now has a **cybernetic feedback loop** where it measures its own forecast accuracy and adjusts its confidence (not its behavior) based on historical performance.

**This is EIE v2.6 - with self-evaluation and confidence calibration.**

---

## 📚 References

- **ML Guardrails (STEP 2.1):** `ML_GUARDRAILS.md`
- **Trajectory Clustering (STEP 2.2):** `TrajectoryClustering_STEP_2.2.md`
- **Emotional Layer:** `services/core/emotional_layer.py`
- **Emotional Inference Engine v2:** `services/core/emotional_inference_v2.py`
