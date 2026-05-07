# Emotional Layer MVP — Implementation Plan

**Дата:** 31 января 2026
**Статус:** Design Spec Approved, Ready for Implementation
**Длительность:** 5-7 дней (MVP)

---

## ✅ Design Spec Analysis

### Почему это хороший подход

1. **Функциональный минимум:** 4 измерения покрывают 80% кейсов
2. **Инженерная чистота:** Rule-based + LLM fallback (без ML)
3. **Интеграционная безопасность:** НЕ меняет ядро, только влияет
4. **Тестируемость:** Детерминированный, объяснимый
5. **Постепенная эволюция:** MVP → v2 → v3 без ломки

### Архитектурная совместимость

```
Текущая архитектура                Новая интеграция
─────────────────────────────────────────────────────────
User Input                         User Input
   ↓                                    ↓
Context Builder                   Context Builder
   ↓                                    ↓
Decision Logic ←──[influence]─── Emotional Layer
   ↓                                    ↓
Agent Orchestration              Agent Orchestration
   ↓                                    ↓
Execution                         Execution
```

**Ключевой момент:** Emotional Layer НЕ управляет напрямую, он только **влияет**.

---

## 📋 Implementation Plan

### Phase 0: Preparation (4 часа)

#### Task 0.1: Database Schema
**File:** `services/core/models.py`

```python
class EmotionalState(Base):
    """Текущее эмоциональное состояние системы"""
    __tablename__ = "emotional_states"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, nullable=False, index=True)

    # Core dimensions
    arousal = Column(Float, default=0.5)       # 0..1
    valence = Column(Float, default=0.0)       # -1..1
    focus = Column(Float, default=0.5)         # 0..1
    confidence = Column(Float, default=0.5)    # 0..1

    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50))  # user_input | system_event | inference
    signals = Column(JSON)       # входные сигналы для дебага

    # Relations
    user = relationship("User", back_populates="emotional_states")


class AffectiveMemoryEntry(Base):
    """Эмоциональная память - связь состояние→результат"""
    __tablename__ = "affective_memory"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, nullable=False, index=True)

    # Context
    goal_id = Column(UUID, ForeignKey("goals.id"), nullable=True)
    decision_id = Column(UUID, nullable=True)

    # Emotional states
    emotional_state_before = Column(JSON)  # {arousal, valence, focus, confidence}
    emotional_state_after = Column(JSON)

    # Outcome
    outcome = Column(String(20))  # success | partial | fail | unknown
    outcome_metrics = Column(JSON)  # {duration, retries, artifacts_created}

    timestamp = Column(DateTime, default=datetime.utcnow)
```

#### Task 0.2: Alembic Migration
**File:** `services/core/migrations/versions/xxxx_add_emotional_layer.py`

```bash
alembic revision -m "add emotional layer tables"
alembic upgrade head
```

---

### Phase 1: Core Models (1 день)

#### Task 1.1: Pydantic Models
**File:** `services/core/schemas.py`

```python
class EmotionalStateBase(BaseModel):
    arousal: float = Field(ge=0.0, le=1.0)
    valence: float = Field(ge=-1.0, le=1.0)
    focus: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class EmotionalStateCreate(EmotionalStateBase):
    user_id: str
    source: str
    signals: Optional[Dict[str, Any]] = None


class EmotionalStateResponse(EmotionalStateBase):
    id: str
    user_id: str
    timestamp: datetime
    source: str


class EmotionalInfluence(BaseModel):
    """Влияние эмоций на решения"""
    complexity_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    exploration_bias: float = Field(default=0.0, ge=-1.0, le=1.0)
    explanation_depth: float = Field(default=0.0, ge=-0.0, le=1.0)
    pace_modifier: float = Field(default=0.0, ge=-1.0, le=1.0)


class EmotionalSignals(BaseModel):
    """Входные сигналы для inference"""
    user_text: Optional[str] = None
    goal_events: List[str] = []  # created, aborted, delayed, conflicted
    system_metrics: Optional[Dict[str, Any]] = None
```

---

### Phase 2: Emotional Inference Engine (1-2 дня)

#### Task 2.1: Rule-based Inference
**File:** `services/core/emotional_inference.py` (NEW)

```python
"""
Emotional Inference Engine - Rule-based + LLM fallback
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func
from database import AsyncSessionLocal
from models import Goal, EmotionalState

class EmotionalInferenceEngine:
    """Двигатель эмоционального вывода"""

    def __init__(self):
        # Rule thresholds (настраиваемые)
        self.thresholds = {
            "high_arousal": 0.7,
            "low_valence": -0.4,
            "low_focus": 0.4,
            "low_confidence": 0.3,
        }

    async def infer_from_signals(
        self,
        user_id: str,
        signals: EmotionalSignals
    ) -> EmotionalStateCreate:
        """
        Основной метод вывода эмоционального состояния
        """
        # Начальное состояние (нейтральное)
        state = {
            "arousal": 0.5,
            "valence": 0.0,
            "focus": 0.5,
            "confidence": 0.5,
        }

        # 1. Rule-based inference
        state = await self._apply_rules(user_id, signals, state)

        # 2. LLM fallback (если нужно)
        if self._needs_llm_inference(signals, state):
            state = await self._llm_inference(signals, state)

        return EmotionalStateCreate(
            user_id=user_id,
            **state,
            source="inference",
            signals=signals.dict()
        )

    async def _apply_rules(
        self,
        user_id: str,
        signals: EmotionalSignals,
        state: Dict[str, float]
    ) -> Dict[str, float]:
        """Применить правила к сигналам"""

        # Rule 1: Aborted goals → high arousal, low confidence
        if "aborted" in signals.goal_events:
            async with AsyncSessionLocal() as db:
                stmt = select(func.count(Goal.id)).where(
                    Goal.user_id == user_id,
                    Goal.status == "aborted",
                    Goal.updated_at >= datetime.utcnow() - timedelta(hours=24)
                )
                result = await db.execute(stmt)
                aborted_count = result.scalar() or 0

            if aborted_count >= 3:
                state["arousal"] += 0.2
                state["confidence"] -= 0.2

        # Rule 2: User text "устал" → low valence, low focus
        if signals.user_text:
            text_lower = signals.user_text.lower()
            if any(word in text_lower for word in ["устал", "сложно", "не могу"]):
                state["valence"] -= 0.3
                state["focus"] -= 0.2
                state["arousal"] += 0.1

        # Rule 3: "проще" → lower arousal, higher focus
        if signals.user_text and "проще" in signals.user_text.lower():
            state["arousal"] -= 0.1
            state["focus"] += 0.1

        # Rule 4: High goal complexity → lower focus
        if signals.system_metrics:
            complexity = signals.system_metrics.get("avg_goal_complexity", 0)
            if complexity > self.thresholds.get("focus_threshold", 0.7):
                state["focus"] -= 0.15

        # Rule 5: Positive artifacts ratio → higher valence
        if signals.system_metrics:
            success_ratio = signals.system_metrics.get("positive_artifacts_ratio", 0)
            if success_ratio > 0.7:
                state["valence"] += 0.2
                state["confidence"] += 0.1

        # Clamp values
        for key in state:
            if key in ["arousal", "focus", "confidence"]:
                state[key] = max(0.0, min(1.0, state[key]))
            elif key == "valence":
                state[key] = max(-1.0, min(1.0, state[key]))

        return state

    def _needs_llm_inference(
        self,
        signals: EmotionalSignals,
        rule_based_state: Dict[str, float]
    ) -> bool:
        """Нужен ли LLM для уточнения"""

        # LLM если:
        # 1. Противоречивые сигналы (user_text говорит X, metrics говорят Y)
        # 2. Резкие изменения (> 0.3 за один вызов)

        if not signals.user_text:
            return False

        # Простая эвристика: если user_text есть и он длинный
        if len(signals.user_text) > 100:
            return True

        # TODO: Добавить больше эвристик

        return False

    async def _llm_inference(
        self,
        signals: EmotionalSignals,
        rule_based_state: Dict[str, float]
    ) -> Dict[str, float]:
        """LLM-ассистированный вывод"""

        prompt = f"""
Инференцируй эмоциональное состояние на основе:

User text: {signals.user_text}
Goal events: {signals.goal_events}
System metrics: {signals.system_metrics}

Правило-based вывод: {rule_based_state}

Верни JSON с полями: arousal (0-1), valence (-1 to 1), focus (0-1), confidence (0-1)
"""

        # TODO: Вызвать LLM через langchain_fallback
        # Сейчас просто возвращаем rule-based
        return rule_based_state
```

#### Task 2.2: State Aggregation
**File:** `services/core/emotional_aggregation.py` (NEW)

```python
"""
Emotional State Aggregation - EMA smoothing
"""

def ema(current: float, new: float, alpha: float = 0.3) -> float:
    """Exponential Moving Average"""
    return alpha * new + (1 - alpha) * current


class EmotionalStateAggregator:
    """Агрегация эмоциональных состояний"""

    def aggregate(
        self,
        previous: EmotionalState,
        inferred: EmotionalStateCreate
    ) -> EmotionalStateCreate:
        """Агрегировать с EMA"""

        return EmotionalStateCreate(
            user_id=inferred.user_id,
            arousal=ema(previous.arousal, inferred.arousal, alpha=0.3),
            valence=ema(previous.valence, inferred.valence, alpha=0.3),
            focus=ema(previous.focus, inferred.focus, alpha=0.4),
            confidence=ema(previous.confidence, inferred.confidence, alpha=0.3),
            source=inferred.source,
            signals=inferred.signals
        )
```

---

### Phase 3: Influence Engine (1 день)

#### Task 3.1: Emotional Influence Mapping
**File:** `services/core/emotional_influence.py` (NEW)

```python
"""
Emotional Influence Engine - State → Decision Weights
"""

class EmotionalInfluenceEngine:
    """Преобразование эмоционального состояния в влияние на решения"""

    def __init__(self):
        self.thresholds = {
            "high_arousal": 0.7,
            "low_valence": -0.4,
            "low_focus": 0.4,
            "low_confidence": 0.3,
        }

    def map_to_influence(
        self,
        state: EmotionalState
    ) -> EmotionalInfluence:
        """Преобразовать состояние в влияние"""

        influence = EmotionalInfluence()

        # arousal > 0.7 → перегруз, снижаем сложность
        if state.arousal > self.thresholds["high_arousal"]:
            influence.complexity_penalty += 0.3
            influence.pace_modifier -= 0.2

        # focus < 0.4 → не можем делать сложные вещи
        if state.focus < self.thresholds["low_focus"]:
            influence.complexity_penalty += 0.4

        # confidence < 0.3 → нужны объяснения
        if state.confidence < self.thresholds["low_confidence"]:
            influence.explanation_depth += 0.5

        # valence < -0.4 → негатив, меньше эксплорации
        if state.valence < self.thresholds["low_valence"]:
            influence.exploration_bias -= 0.3
        # valence > 0.4 → позитив, больше эксплорации
        elif state.valence > 0.4:
            influence.exploration_bias += 0.2

        # Clamp
        influence.complexity_penalty = max(0.0, min(1.0, influence.complexity_penalty))
        influence.exploration_bias = max(-1.0, min(1.0, influence.exploration_bias))
        influence.explanation_depth = max(0.0, min(1.0, influence.explanation_depth))
        influence.pace_modifier = max(-1.0, min(1.0, influence.pace_modifier))

        return influence
```

---

### Phase 4: Integration Points (1 день)

#### Task 4.1: Context Builder Integration
**File:** `services/core/agent_graph.py`

```python
# В Supervisor agent

async def build_supervisor_context(
    user_id: str,
    message: str
) -> Dict[str, Any]:
    """Построить контекст для Supervisor с учетом эмоций"""

    # 1. Собрать сигналы
    signals = EmotionalSignals(
        user_text=message,
        goal_events=await get_recent_goal_events(user_id),
        system_metrics=await get_system_metrics(user_id)
    )

    # 2. Инференцировать эмоции
    from emotional_layer import emotional_layer
    influence = await emotional_layer.get_influence(user_id, signals)

    # 3. Применить к контексту
    context = {
        "user_message": message,
        "complexity_limit": 1.0 - influence.complexity_penalty,
        "exploration_bias": influence.exploration_bias,
        "explanation_detail": "high" if influence.explanation_depth > 0.5 else "normal",
        "pace": "slow" if influence.pace_modifier < -0.3 else "normal",
    }

    return context
```

#### Task 4.2: Goal Decomposer Integration
**File:** `services/core/goal_decomposer.py`

```python
# При декомпозиции целей

async def decompose_goal(
    goal_id: str,
    user_id: str
) -> List[Subgoal]:
    """Декомпозиция с учетом эмоционального состояния"""

    # Получить эмоциональное влияние
    influence = await emotional_layer.get_current_influence(user_id)

    # Если high arousal → ограничить глубину декомпозиции
    if influence.complexity_penalty > 0.3:
        max_depth = 1  # Только один уровень
    else:
        max_depth = 3  # Обычно

    # Если low focus → более простые подцели
    subgoals = await _generate_subgoals(
        goal_id,
        max_depth=max_depth,
        complexity_threshold=0.7 - influence.complexity_penalty
    )

    return subgoals
```

---

### Phase 5: API Endpoints (0.5 дня)

#### Task 5.1: FastAPI Routes
**File:** `services/core/main.py`

```python
# Emotional Layer endpoints

@app.post("/emotions/infer")
async def infer_emotional_state(
    user_id: str,
    signals: EmotionalSignals
):
    """Инференцировать эмоциональное состояние"""
    inference_result = await emotional_layer.infer(user_id, signals)
    return inference_result


@app.get("/emotions/current")
async def get_current_emotional_state(user_id: str):
    """Получить текущее эмоциональное состояние"""
    state = await emotional_layer.get_current_state(user_id)
    return state


@app.get("/emotions/influence")
async def get_emotional_influence(user_id: str):
    """Получить текущее влияние на решения"""
    influence = await emotional_layer.get_current_influence(user_id)
    return influence


@app.post("/emotions/event")
async def track_emotional_event(
    user_id: str,
    event_type: str,  # goal_created, goal_aborted, etc.
    metadata: Optional[Dict[str, Any]] = None
):
    """Отследить событие для эмоционального inference"""
    await emotional_layer.track_event(user_id, event_type, metadata)
    return {"status": "recorded"}


@app.get("/emotions/history")
async def get_emotional_history(
    user_id: str,
    limit: int = 100
):
    """Получить историю эмоциональных состояний"""
    history = await emotional_layer.get_history(user_id, limit)
    return history
```

---

### Phase 6: Affective Memory (0.5 дня)

#### Task 6.1: Affective Memory Recorder
**File:** `services/core/affective_memory.py` (NEW)

```python
"""
Affective Memory - запись эмоциональных паттернов
"""

class AffectiveMemoryRecorder:
    """Запись эмоциональной памяти"""

    async def record_decision_outcome(
        self,
        user_id: str,
        goal_id: str,
        emotional_state_before: EmotionalState,
        outcome: str,
        outcome_metrics: Dict[str, Any]
    ):
        """Записать результат решения"""

        entry = AffectiveMemoryEntry(
            user_id=user_id,
            goal_id=goal_id,
            emotional_state_before=emotional_state_before.dict(),
            emotional_state_after=await emotional_layer.get_current_state(user_id),
            outcome=outcome,
            outcome_metrics=outcome_metrics
        )

        async with AsyncSessionLocal() as db:
            db.add(entry)
            await db.commit()

    async def detect_negative_patterns(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Найти повторяющиеся негативные паттерны"""

        # TODO: SQL query для поиска паттернов
        # Например: "когда arousal > 0.7, success rate падает"

        return []
```

---

## 📁 File Structure

```
services/core/
├── models.py                           (+ EmotionalState, AffectiveMemoryEntry)
├── schemas.py                          (+ EmotionalState*, EmotionalInfluence, EmotionalSignals)
├── emotional_inference.py              (NEW)
├── emotional_aggregation.py            (NEW)
├── emotional_influence.py              (NEW)
├── affective_memory.py                 (NEW)
├── emotional_layer.py                  (NEW - facade)
├── agent_graph.py                      (MODIFY - integrate influence)
├── goal_decomposer.py                  (MODIFY - respect emotional state)
└── main.py                             (MODIFY - add endpoints)
```

---

## 🧪 Testing Strategy

### Unit Tests
```python
# tests/test_emotional_inference.py

async def test_aborted_goals_increase_arousal():
    signals = EmotionalSignals(
        goal_events=["aborted", "aborted", "aborted"]
    )
    state = await inference_engine.infer_from_signals(user_id, signals)
    assert state.arousal > 0.6
    assert state.confidence < 0.4

async def test_low_focus_complexity_penalty():
    state = EmotionalState(focus=0.3)
    influence = influence_engine.map_to_influence(state)
    assert influence.complexity_penalty > 0.3
```

### Integration Tests
```python
# tests/test_emotional_integration.py

async def test_full_emotional_cycle():
    # 1. User input
    signals = EmotionalSignals(user_text="Я устал, давай попроще")

    # 2. Inference
    state = await emotional_layer.infer(user_id, signals)

    # 3. Influence
    influence = await emotional_layer.get_influence(user_id, signals)

    # 4. Decision
    context = await build_context(user_id, "message")

    assert context["complexity_limit"] < 1.0
    assert context["pace"] == "slow"
```

---

## ✅ Success Criteria

MVP считается успешным, когда:

- [ ] EmotionalState корректно сохраняется в БД
- [ ] Rule-based inference работает для 5 базовых правил
- [ ] Influence engine корректно мапит state → weights
- [ ] Supervisor использует emotional context
- [ ] Goal decomposer уважает complexity_penalty
- [ ] API endpoints работают
- [ ] Unit tests coverage > 80%
- [ ] Интеграционные тесты проходят

---

## 🚀 Quick Start (1 день prototype)

Если нужно быстро проверить концепт:

```bash
# Day 1 morning: Models + Basic inference
# 1. Add EmotionalState to models.py
# 2. Create emotional_inference.py with 3 rules
# 3. Test via curl

# Day 1 afternoon: Influence + API
# 4. Create emotional_influence.py
# 5. Add API endpoints
# 6. Test end-to-end

# Day 2: Integration
# 7. Modify agent_graph.py
# 8. Modify goal_decomposer.py
# 9. Full integration test
```

---

## 🎯 Next Steps After MVP

1. **Dashboard v2 Integration**
   - Визуализация эмоционального состояния
   - Графики arousal/valence/focus/confidence
   - Emotional timeline

2. **Personality Integration**
   - Personality traits → emotion thresholds
   - Value Matrix → emotional reactions

3. **More Rules**
   - Распознавание больше паттернов
   - User-specific adaptation

4. **Emotional Layer v2**
   - LLM-based inference
   - Affective memory patterns
   - Emotional feedback loop

---

**Готов к реализации! 🚀**
