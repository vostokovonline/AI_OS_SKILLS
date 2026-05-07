# Learned Forecasting Model - Step 2 Implementation

## 🎯 Summary

**Status:** ✅ COMPLETE

Implemented ML-based emotional forecasting with three-tier safety architecture:
1. **🤖 ML Model** (Random Forest) - Primary when confident
2. **📊 Trajectory Clusters** - Fallback if ML uncertain
3. **📐 Rule-based** - Always available as safety net

---

## 📊 Architecture: Three-Tier Safety System

```
Request → Try ML Model (conf > 0.4)
            ↓ NO
         Try Clusters (conf > 0.3)
            ↓ NO
         Use Rules (always works)
```

### Why Three Tiers?

1. **Safety First:** Rules always work, no black-box failures
2. **Adaptive:** ML improves with data, but gracefully degrades
3. **Transparent:** System knows when it's uncertain

---

## 🔧 Components Created

### 1. ML Model (`emotional_forecasting_model.py`)

```python
class EmotionalForecastingModel:
    """
    RandomForestRegressor для предсказания emotional deltas.

    Features (20+):
    - Current state (4): arousal, valence, focus, confidence
    - Action type (6): one-hot encoding
    - Pattern context (10+): risk_profile, correlations, patterns

    Target (4):
    - arousal_delta, valence_delta, focus_delta, confidence_delta
    """

    def __init__(self):
        self.model = None  # RandomForestRegressor
        self.scaler = None  # StandardScaler
        self.metadata = {
            "trained": False,
            "training_samples": 0,
            "feature_importance": {},
            "metrics": {},
            "trained_at": None
        }

    async def train(self, min_samples: int = 20, test_size: float = 0.2):
        """
        Обучает на Affective Memory данных.

        Process:
        1. Extract X, y from affective_memory entries
        2. Split train/test
        3. Scale features
        4. Train RandomForest (50 trees, max_depth=10)
        5. Evaluate (MSE, R2)
        6. Save model to /tmp/*.pkl
        """

    def predict(self, current_state, action_type, pattern_context):
        """
        Предсказывает emotional deltas.

        Returns:
            (predicted_deltas, confidence)

        Confidence = 1 - std_dev / max_std
        (measures tree agreement)
        """
```

### 2. Feature Extraction

```python
class TrajectoryFeatures:
    @staticmethod
    def extract_features(current_state, action_type, pattern_context):
        """
        Извлекает feature vector (20+ dimensions).

        Example:
        [0.5, 0.0, 0.4, 0.6,  # current state
         1, 0, 0, 0, 0, 0,    # action: deep_goal_decomposition
         0.72, 0.65, 0.40,    # risk_profile
         0.85, 0.70,          # success_correlations
         1, 0, 1]             # dominant_patterns (binary)
        """
        ...

    @staticmethod
    def extract_target(before_state, after_state):
        """
        Извлекает target vector (emotional deltas).

        Example:
        [+0.12, -0.03, -0.08, -0.15]  # 4 deltas
        """
        ...
```

### 3. Integration with EIE v2

**File:** `emotional_inference_v2.py`

```python
class EmotionalForecastingEngine:
    def simulate(self, current_state, action, pattern_context, user_id=None):
        """
        THREE-TIER FORECASTING
        """

        # TIER 1: ML Model
        ml_impact = {}
        ml_confidence = 0.0

        try:
            if emotional_forecasting_model.is_available():
                ml_deltas, ml_conf = emotional_forecasting_model.predict(...)
                if ml_conf > 0.4:
                    ml_impact = ml_deltas
                    print(f"🤖 [ML Model] Using ML forecast (confidence={ml_conf:.2f})")
        except:
            pass

        # TIER 2: Trajectory Clusters (если ML не сработал)
        cluster_impact = {}
        if not ml_impact:
            try:
                cluster_outcome, cluster_confidence, cluster_deltas = (
                    trajectory_clusterer.predict_trajectory_outcome(...)
                )
                if cluster_confidence > 0.3:
                    cluster_impact = cluster_deltas
            except:
                pass

        # TIER 3: Rules (SAFETY NET)
        base_impact = self.ACTION_IMPACTS.get(action, {})
        adjusted_impact = self._adjust_for_patterns(base_impact, pattern_context)

        # Смешиваем
        if ml_impact and ml_confidence > 0.4:
            # ML + rules
            weight = ml_confidence
            final_impact = {
                dim: (1-weight) * rule_value + weight * ml_value
                for dim in ["arousal", "valence", "focus", "confidence"]
            }
            print(f"🔀 [Mixed Forecast] ML + Rules (weight={weight:.2f})")

        elif cluster_impact and cluster_confidence > 0.3:
            # Clusters + rules
            weight = cluster_confidence
            final_impact = {...}
            print(f"🔀 [Mixed Forecast] Clusters + Rules (weight={weight:.2f})")

        else:
            # Rules only
            final_impact = adjusted_impact

        print(f"📊 [Forecast Tiers] {' → '.join(used_tiers)}")

        return EmotionalForecast(...)
```

---

## 🌐 API Endpoints

### POST /emotional/v2/model/train

Обучить ML модель на Affective Memory данных.

```bash
curl -X POST "http://localhost:8000/emotional/v2/model/train?min_samples=20&test_size=0.2"
```

**Response:**
```json
{
  "status": "ok",
  "message": "ML model trained successfully",
  "metrics": {
    "mse": 0.0234,
    "r2": 0.6789,
    "training_samples": 45,
    "test_samples": 9
  },
  "metadata": {
    "trained": true,
    "training_samples": 45,
    "trained_at": "2026-02-01T12:34:56+00:00"
  },
  "top_features": [
    {"feature": "confidence", "importance": 0.234},
    {"feature": "arousal", "importance": 0.189},
    {"feature": "action_decompose", "importance": 0.156},
    ...
  ]
}
```

### GET /emotional/v2/model

Получить информацию о ML модели.

```bash
curl "http://localhost:8000/emotional/v2/model"
```

**Response:**
```json
{
  "status": "ok",
  "model": {
    "available": true,
    "trained": true,
    "training_samples": 45,
    "trained_at": "2026-02-01T12:34:56+00:00",
    "metrics": {
      "mse": 0.0234,
      "r2": 0.6789
    },
    "top_features": [
      {"feature": "confidence", "importance": 0.234},
      {"feature": "arousal", "importance": 0.189}
    ]
  }
}
```

---

## 📈 How It Works

### Scenario 1: No Data (Initial State)

```
User: "I want to decompose this goal"
  ↓
System: Try ML → Not trained
  ↓
System: Try Clusters → No data
  ↓
System: Use Rules → Works! ✅
```

### Scenario 2: Some Data (Clusters Exist)

```
User: "I want to decompose this goal"
  ↓
System: Try ML → Not trained yet
  ↓
System: Try Clusters → Found! (confidence=0.72)
  ↓
System: Mix Clusters + Rules → Optimized forecast ✅
```

### Scenario 3: ML Trained

```
User: "I want to decompose this goal"
  ↓
System: Try ML → Available! (confidence=0.85)
  ↓
System: Mix ML + Rules → Best forecast ✅
```

---

## 🎯 Key Benefits

### 1. **Adaptive Learning**
- Starts with rules (always works)
- Adds clusters as data accumulates
- Adds ML as patterns emerge
- Seamless transitions between tiers

### 2. **Safety-First Design**
- Rules never break
- ML degrades gracefully
- System always functional

### 3. **Confidence Awareness**
- ML knows when uncertain (std dev across trees)
- Clusters know when small (few samples)
- System chooses best tier automatically

### 4. **Interpretability**
- Feature importance shows what matters
- Tree agreement measures confidence
- Rules provide baseline behavior

---

## 📁 Files Created/Modified

### Created:
- `services/core/emotional_forecasting_model.py` (450 lines)
  - `TrajectoryFeatures` - feature extraction
  - `EmotionalForecastingModel` - ML model wrapper
  - `emotional_forecasting_model` - global instance

### Modified:
- `services/core/emotional_inference_v2.py`
  - `EmotionalForecastingEngine.simulate()` - added three-tier forecasting

- `services/core/main.py`
  - Added `POST /emotional/v2/model/train`
  - Added `GET /emotional/v2/model`

---

## 🧪 Testing

### Test 1: Check Model Status
```bash
curl "http://localhost:8000/emotional/v2/model"
```
✅ **Expected:** Model not trained yet

### Test 2: Train Model (если есть данные)
```bash
curl -X POST "http://localhost:8000/emotional/v2/model/train"
```
✅ **Expected:** Training metrics or "Insufficient data" error

### Test 3: Inference with ML
```bash
curl -X POST "http://localhost:8000/emotional/v2/infer" \
  -d '{"user_id": "...", "proposed_action": "complex_execution"}'
```
✅ **Expected:** Logs show which tier was used

---

## 📊 Performance

**Model Architecture:**
- Algorithm: RandomForestRegressor
- Trees: 50
- Max Depth: 10
- Features: 20+
- Training data: Affective Memory entries

**Expected Metrics (with 50+ samples):**
- MSE: < 0.03
- R2: > 0.6
- Inference time: < 10ms

**Confidence Calculation:**
```
confidence = 1 - (std_dev_across_trees / 0.5)
```
- High agreement (std=0.05) → confidence=0.90
- Low agreement (std=0.20) → confidence=0.60
- Use threshold 0.4 for ML tier

---

## 🚀 Deployment

### Prerequisites

```bash
# Install scikit-learn in container
docker exec ns_core pip3 install scikit-learn
```

### Training Workflow

```bash
# 1. Accumulate data (run goals, record outcomes)
# 2. Rebuild clusters
curl -X POST "http://localhost:8000/emotional/v2/clusters/rebuild"

# 3. Train ML model
curl -X POST "http://localhost:8000/emotional/v2/model/train"

# 4. Check model status
curl "http://localhost:8000/emotional/v2/model"

# 5. Test inference
curl -X POST "http://localhost:8000/emotional/v2/infer" \
  -d '{"user_id": "...", "proposed_action": "complex_execution"}'
```

---

## 🛡 Safety Guarantees

### Rule-Based Safety Net

**Rules ALWAYS work:**
1. ✅ No data requirement
2. ✅ No external dependencies
3. ✅ Deterministic behavior
4. ✅ Expert-defined logic

**ML adds value but never replaces:**
- If ML trained → use it (with confidence check)
- If ML uncertain → fallback to clusters
- If clusters empty → fallback to rules
- If everything fails → rules still work

**Example log flow:**
```
ℹ️  [ML Model] Not available, trying next tier
⚠️  [Trajectory Clustering] Low confidence, falling back to rules
📊 [Forecast Tiers] Rules only
```

---

## 🏁 Summary

**Learned Forecasting Model (Step 2) is complete and integrated.**

The system now:
1. ✅ Trains ML model on Affective Memory data
2. ✅ Uses three-tier forecasting (ML → Clusters → Rules)
3. ✅ Provides confidence-aware predictions
4. ✅ Falls back gracefully if ML uncertain
5. ✅ Never breaks (rules always available)

**Ready for:**
- Step 3: Explainability Layer

---

## 💡 Key Insight

**Rules are NOT replaced, they're augmented:**

| Tier | When Used | Confidence | Typical Scenario |
|------|-----------|------------|------------------|
| ML | conf > 0.4 | 0.4-1.0 | Plenty of data, trees agree |
| Clusters | conf > 0.3 | 0.3-1.0 | Some data, similar patterns found |
| Rules | always | 1.0 | No data or low confidence |

**Result:** Adaptive system that improves with data but never breaks!
