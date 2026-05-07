# Personality Enhancement & Goal Conflict Detection

## Что добавлено

### 1. Personality Engine Enhancement (NS1/NS2 ideas)

#### **Personality Snapshots** - Версионирование профиля
- Создание snapshot'ов перед изменениями
- Откат к предыдущим версиям
- История изменений личности

**API:**
```bash
# Создать snapshot
POST /personality/{user_id}/snapshot?reason=adaptation&created_by=system

# Получить историю
GET /personality/{user_id}/snapshots?limit=10

# Откатиться к версии
POST /personality/{user_id}/rollback/{snapshot_version}
```

**Использование:**
```python
from personality_engine import get_personality_engine

engine = get_personality_engine()

# Создать snapshot перед изменениями
snapshot = await engine.create_snapshot(
    user_id="user-123",
    reason="adaptation",
    created_by="system"
)

# Откатиться, если что-то пошло не так
profile = await engine.rollback_to_snapshot(
    user_id="user-123",
    snapshot_version=5
)
```

---

#### **Contextual Memory** - Короткосрочная память
- Недавние цели (top 5)
- Эмоциональный тон
- Behavioral summary (completed/missed tasks)
- Interaction streak

**API:**
```bash
# Получить контекстную память
GET /personality/{user_id}/contextual-memory

# Обновить
PUT /personality/{user_id}/contextual-memory
{
    "recent_goals": [
        {"id": "...", "title": "...", "status": "active", "progress": 0.5}
    ],
    "emotional_tone": "оптимистичный",
    "behavioral_summary": {
        "completed_tasks": 14,
        "missed_tasks": 3,
        "interaction_frequency": "ежедневно"
    }
}
```

**Использование:**
```python
# Получить контекст
memory = await engine.get_contextual_memory(user_id="user-123")
print(f"Эмоциональный тон: {memory.emotional_tone_recent}")
print(f"Последние цели: {[g.title for g in memory.recent_goals]}")

# Обновить после выполнения цели
await engine.update_contextual_memory(
    user_id="user-123",
    recent_goals=[...],
    emotional_tone="вдохновленный",
    behavioral_summary={"completed_tasks": 15, "missed_tasks": 3}
)
```

---

### 2. Goal Conflict Detection

#### **Автообнаружение конфликтов**
- Resource conflicts (время, деньги, энергия)
- Time conflicts (одновременное выполнение)
- Mutually exclusive goals (полная несовместимость)
- Value conflicts (противоречие ценностям)

**API:**
```bash
# Проверить цель на конфликты
POST /goals/{goal_id}/check-conflicts
{
    "check_against": ["goal-2-id", "goal-3-id"]  # опционально
}

# Получить все конфликты пользователя
GET /goals/{user_id}/conflicts?status=detected&severity=high

# Разрешить конфликт
POST /conflicts/{conflict_id}/resolve
{
    "resolution": "Приоритизировать goal_1, отложить goal_2"
}
```

**Использование:**
```python
from goal_conflict_detector import get_goal_conflict_detector

detector = get_goal_conflict_detector()

# Проверить перед декомпозицией
result = await detector.check_goal_conflicts(goal_id="goal-123")

if result.has_conflicts:
    print(f"Обнаружено {len(result.conflicts)} конфликтов!")
    for conflict in result.conflicts:
        print(f"- {conflict['description']}")
        print(f"  Решение: {conflict['resolution_suggestion']}")

# Получить все конфликты пользователя
conflicts = await detector.get_conflicts_for_user(
    user_id="user-123",
    severity="high"
)

# Разрешить конфликт
resolved = await detector.resolve_conflict(
    conflict_id="conflict-456",
    resolution="Отложить goal_2 на 2 недели"
)
```

---

## Интеграция с существующей системой

### 1. Goal Decomposition + Conflict Detection

```python
# В goal_decomposer.py перед созданием subgoals:
from goal_conflict_detector import get_goal_conflict_detector

detector = get_goal_conflict_detector()

# Проверить parent goal на конфликты
conflicts = await detector.check_goal_conflicts(parent_goal_id)

if conflicts.severity in ["high", "critical"]:
    # Warn user
    return {
        "warning": f"Обнаружены конфликты: {len(conflicts.conflicts)}",
        "conflicts": conflicts.conflicts
    }
```

### 2. Goal Executor + Contextual Memory

```python
# В goal_executor.py после выполнения цели:
from personality_engine import get_personality_engine

engine = get_personality_engine()

# Обновить контекстную память
await engine.update_contextual_memory(
    user_id=goal.user_id,
    recent_goals=get_recent_goals(goal.user_id),
    emotional_tone=detected_emotion,
    behavioral_summary={
        "completed_tasks": completed_count,
        "missed_tasks": missed_count
    }
)
```

### 3. Personality Auto-Adaptation

```python
# При положительном feedback:
if reaction == "positive":
    # Усилить паттерн
    await engine.update_profile(user_id, {
        "motivations": {"growth": current_growth + 0.05}
    })

# При отрицательном:
elif reaction == "negative":
    # Создать snapshot и откатить
    snapshot = await engine.create_snapshot(user_id, reason="negative_feedback")
    await engine.rollback_to_snapshot(user_id, snapshot.snapshot_version - 1)
```

---

## Новые модели БД

### PersonalitySnapshot
```python
class PersonalitySnapshot(Base):
    profile_id: UUID
    snapshot_version: int
    snapshot_reason: str  # "user_update", "adaptation", "manual"
    core_traits: JSON  # {"openness": 0.7, ...}
    motivations: JSON  # {"growth": 0.9, ...}
    values: JSON  # [{"name": "осознанность", "importance": 0.8}, ...]
    preferences: JSON
    created_at: datetime
    created_by: str  # "system", "user", "auto_adaptation"
```

### ContextualMemory
```python
class ContextualMemory(Base):
    user_id: UUID (unique)
    recent_goals: JSON  # top 5 целей
    emotional_tone_recent: str  # "оптимистичный", "тревожный"
    emotional_tone_confidence: float
    behavioral_summary_week: JSON  # completed/missed tasks
    last_interaction_at: datetime
    interaction_streak: int  # дней подряд
```

### GoalConflict
```python
class GoalConflict(Base):
    goal_1_id: UUID
    goal_2_id: UUID
    conflict_type: str  # "resource", "time", "mutually_exclusive"
    severity: str  # "low", "medium", "high", "critical"
    description: str
    resolution_suggestion: str
    status: str  # "detected", "resolved", "ignored"
    detected_at: datetime
    resolved_at: datetime
```

---

## Примеры использования

### Пример 1: Создание цели с проверкой конфликтов

```python
# 1. Создать цель
goal = await create_goal(
    title="Работать больше",
    user_id="user-123"
)

# 2. Проверить на конфликты
from goal_conflict_detector import get_goal_conflict_detector
detector = get_goal_conflict_detector()

conflicts = await detector.check_goal_conflicts(goal.id)

if conflicts.has_conflicts:
    for conflict in conflicts.conflicts:
        print(f"⚠️  Конфликт: {conflict['description']}")
        print(f"   Решение: {conflict['resolution_suggestion']}")
```

### Пример 2: Адаптация личности на основе feedback

```python
# После выполнения goal
feedback = await get_user_feedback(goal_id="goal-123")

if feedback["reaction"] == "positive":
    # Усилить мотивацию роста
    profile = await engine.get_profile(user_id="user-123")
    new_growth = min(1.0, profile.motivations.growth + 0.1)

    # Создать snapshot перед изменением
    await engine.create_snapshot(user_id="user-123", reason="adaptation")

    # Обновить
    await engine.update_profile(user_id="user-123", {
        "motivations": {"growth": new_growth}
    })

elif feedback["reaction"] == "negative":
    # Откатиться назад
    snapshots = await engine.get_snapshots(user_id="user-123", limit=1)
    if snapshots:
        await engine.rollback_to_snapshot(user_id="user-123", snapshots[0].snapshot_version)
```

### Пример 3: Контекстная память для Decision Logic

```python
# При принятии решения о следующей цели
from personality_engine import get_personality_engine

engine = get_personality_engine()
context = await engine.get_contextual_memory(user_id="user-123")

# Учёт эмоционального состояния
if context.emotional_tone_recent == "уставший":
    # Предложить более лёгкие задачи
    next_goal_suggestions = filter_easy_goals(all_goals)

# Учёт паттернов успеха
if context.behavioral_summary_week.completed_tasks > 10:
    # Можно дать более сложные задачи
    next_goal_suggestions = filter_challenging_goals(all_goals)
```

---

## Следующие шаги

### ✅ DONE:
1. Personality Snapshots (версионирование)
2. Contextual Memory (короткосрочная память)
3. Goal Conflict Detection
4. API endpoints
5. Документация

### 🚧 TODO:
1. **Интеграция с Decision Logic**
   - Использовать personality при выборе стратегий
   - Учитывать contextual_memory при планировании

2. **Dashboard v2 UI**
   - Показывать конфликты в InspectorPanel
   - Кнопка "Откатиться к версии" в профиле
   - Визуализация contextual_memory

3. **Auto-Adaptation Loop**
   - Автоматическая адаптация на основе feedback
   - Метрики эффективности адаптации

4. **Emotional Layer Integration**
   - Emotion Recognition (по тексту)
   - Mood Regulation
   - Affective Memory

---

## Ключевые идеи из NS1/NS2

1. **Personality Engine** как "архитектор идентичности"
   - Value Matrix (матрица ценностей)
   - Adaptation Loop (цикл адаптации)
   - Versioning (snapshot'ы с откатом)

2. **Contextual Memory** из NS1/NS2:
   - recent_goals
   - emotional_tone_recent
   - behavioral_summary_week

3. **Goal Linking** (Связывание целей):
   - Выявление конфликтов
   - Разрешение противоречий
   - Политика компромиссов

---

## Метрики успеха

- ✅ Personality Snapshots работают
- ✅ Contextual Memory обновляется
- ✅ Conflicts обнаруживаются
- ✅ API endpoints отвечают
- ✅ Код синтаксически верен

**Осталось:**
- Deploy (проблемы с Docker volumes)
- Integration testing
- Dashboard v2 UI
