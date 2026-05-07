# Emotional Layer MVP — Quick Start

**Длительность:** 5-7 дней
**Статус:** Design Spec Approved

---

## 🎯 Что получим

**Система:**
- Перестанет перегружать пользователя
- Будет снижать сложность автоматически
- Начнёт менять тон и темп
- Станет предсказуемо "человечной"

**Технически:**
- Полностью детерминирована
- Тестируема
- Расширяема

---

## 📊 4 измерения (80% кейсов)

```
arousal  (0..1)  → Напряжение/возбуждение
valence  (-1..1) → Негатив ↔ Позитив
focus    (0..1)  → Расфокус ↔ Поток
confidence (0..1) → Уверенность
```

---

## 🔄 Полный цикл

```python
# 1. User Input
signals = {
    "user_text": "Я устал, давай попроще",
    "goal_events": ["aborted", "delayed"],
    "system_metrics": {"avg_goal_complexity": 0.8}
}

# 2. Inference (Rule-based)
state = {
    "arousal": 0.8,    # Высокий (усталость + aborted)
    "valence": -0.2,   # Слегка негатив
    "focus": 0.3,      # Низкий
    "confidence": 0.4  # Средний
}

# 3. Influence Mapping
influence = {
    "complexity_penalty": +0.4,  # Снижать сложность
    "pace_modifier": -0.2,       # Замедлить темп
    "explanation_depth": +0.5,   # Больше объяснений
    "exploration_bias": -0.3     # Меньше эксплорации
}

# 4. Decision Context
context = {
    "max_subgoals": 2,           # Вместо 5
    "decomposition_depth": 1,    # Вместо 3
    "tone": "supportive",        # Вместо "neutral"
    "explanation": "detailed"    # Вместо "brief"
}
```

---

## 📁 Файлы (что создаём)

### Новые файлы (5)
```
services/core/
├── emotional_inference.py      # Rule-based inference
├── emotional_aggregation.py    # EMA smoothing
├── emotional_influence.py      # State → Influence mapping
├── affective_memory.py         # Emotional patterns
└── emotional_layer.py          # Facade API
```

### Модификации (3)
```
services/core/
├── models.py                   # + EmotionalState, AffectiveMemoryEntry
├── schemas.py                  # + EmotionalState*, EmotionalInfluence
├── agent_graph.py              # + emotional context
├── goal_decomposer.py          # + respect complexity_penalty
└── main.py                     # + API endpoints
```

---

## 🚀 3-Day Quick Start

### Day 1: Core (4 часа)
```bash
# Morning
1. models.py → add EmotionalState
2. schemas.py → add Pydantic models
3. emotional_inference.py → 3 basic rules

# Afternoon
4. Test inference via Python shell
5. emotional_aggregation.py → EMA
6. emotional_influence.py → mapping
```

### Day 2: API (3 часа)
```bash
# Morning
7. main.py → add 5 endpoints
8. Test via curl

# Afternoon
9. emotional_layer.py → facade
10. Integration tests
```

### Day 3: Integration (4 часа)
```bash
# Morning
11. agent_graph.py → Supervisor context
12. goal_decomposer.py → complexity limit

# Afternoon
13. Full E2E test
14. Dashboard visualization (optional)
```

---

## 💡 Rule Examples (MVP)

```python
# Rule 1: Aborted goals → high arousal
if aborted_goals_last_24h >= 3:
    arousal += 0.2
    confidence -= 0.2

# Rule 2: "устал" → low valence, low focus
if "устал" in user_text.lower():
    valence -= 0.3
    focus -= 0.2

# Rule 3: "проще" → lower arousal
if "проще" in user_text.lower():
    arousal -= 0.1
    focus += 0.1

# Rule 4: High complexity → low focus
if avg_goal_complexity > 0.7:
    focus -= 0.15

# Rule 5: Success rate > 70% → positive
if positive_artifacts_ratio > 0.7:
    valence += 0.2
    confidence += 0.1
```

---

## 🔌 Integration Points

### 1. Supervisor Agent
```python
# Before
context = {"user_message": message}

# After
signals = collect_signals(user_id, message)
influence = emotional_layer.get_influence(user_id, signals)
context = {
    "user_message": message,
    "complexity_limit": 1.0 - influence.complexity_penalty,
    "explanation_detail": "high" if influence.explanation_depth > 0.5 else "normal"
}
```

### 2. Goal Decomposer
```python
# Before
subgoals = await decompose(goal_id, max_depth=3)

# After
influence = emotional_layer.get_current_influence(user_id)
if influence.complexity_penalty > 0.3:
    max_depth = 1
subgoals = await decompose(goal_id, max_depth=max_depth)
```

### 3. Agent Prompts
```python
# Before
prompt = "You are helpful assistant"

# After
if influence.pace_modifier < -0.3:
    prompt = "You are helpful assistant. Be patient and supportive."
```

---

## 🧪 Testing

### Manual Test
```bash
# 1. Create emotional state
curl -X POST http://localhost:8000/emotions/infer \
  -H "Content-Type: application/json" \
  -d '{
    "user_text": "Я устал, давай попроще",
    "goal_events": ["aborted"]
  }'

# Response:
{
  "arousal": 0.7,
  "valence": -0.3,
  "focus": 0.4,
  "confidence": 0.5
}

# 2. Get influence
curl http://localhost:8000/emotions/influence?user_id=xxx

# Response:
{
  "complexity_penalty": 0.4,
  "pace_modifier": -0.2,
  "explanation_depth": 0.3,
  "exploration_bias": -0.2
}

# 3. Create goal and check complexity
curl -X POST http://localhost:8000/goals/create \
  -d '{"title": "Сложная цель", ...}'

# Check: только 1-2 подцели (вместо 5)
```

---

## ✅ Success Criteria

- [ ] 5 правил работают корректно
- [ ] EMA сглаживание работает
- [ ] Influence mapping корректен
- [ ] Supervisor использует контекст
- [ ] Goal decomposer уважает complexity
- [ ] API endpoints работают
- [ ] Tests pass

---

## 🎯 After MVP

### Week 2: Dashboard
- Emotional state visualization
- Arousal/Valence график
- Influence indicators

### Week 3: Personality Integration
- Personality traits → emotion thresholds
- Values → emotional reactions

### Week 4: More Rules
- 15+ rules вместо 5
- User-specific adaptation

---

## 📚 Documentation

- `EMOTIONAL_LAYER_MVP_PLAN.md` - Full implementation plan
- `EMOTIONAL_LAYER_QUICKSTART.md` - This file

---

**Готов начать! 🚀**
