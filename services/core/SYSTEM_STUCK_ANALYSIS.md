# SYSTEM STUCK ANALYSIS
======================

**Date**: 2026-02-11
**Total Goals**: 172
**Stuck Goals**: 42 (pending/active)
**Stuck Rate**: 24.4%

---

## 📊 СТАТИСТИКА ПО СТАТУСАМ

| Статус | Количество | Средний возраст | Проблема? |
|---------|-------------|------------------|------------|
| **done** | 121 | 3.0 дня | ✅ Быстро завершаются |
| **pending** | 32 | **8.3 дня** | ❌ ЗАСТРЯЛИ! |
| **active** | 10 | **8.6 дня** | ❌ ЗАСТРЯЛИ! |
| idea | 8 | 2.2 дня | ✅ Нормально |
| completed | 1 | 11.3 дня | ⚠️ Странный статус |

**Вывод**: 42 цели (24%) ЗАСТРЯЛИ в pending/active > 8 дней.

---

## 🔍 КЛЮЧЕВЫЕ ПРОБЛЕМЫ

### Проблема #1: Non-atomic goals НЕ ИМЕЮТ ДЕТЕЙ (КРИТИЧНО!)

**Данные**:
```
32 non-atomic goals stuck в pending/active
0 execution_trace у этих целей
Некоторые имеют parent_id, но у НИХ НЕТ детей
```

**Примеры stuck goals**:
```
1. "Еженедельные звонки родителям" (L2) - pending 11.3 дней
   - Parent: "Эмоциональная поддержка близких" (L1)
   - НЕ decomposed!
   - НЕ executed!

2. "Пассивный доход для семьи" (L2) - pending 11.3 дней
   - Parent: "Финансовая надёжность для семьи" (L1)
   - НЕ decomposed!

3. "Утренняя медитация 10 минут" (L0) - pending 11.3 дней
   - Mission level goal!
   - Без parent
   - Без детей
   - НЕ decomposed!
```

**Диагноз**: **СЛОВУШКА L0-L2 GOALS**
- Non-atomic goals создаются
- Они НЕ decompose автоматически
- Они НЕ выполняются
- Они остаются pending навсегда

**Почему так происходит**:
```
Worker выполняет ТОЛЬКО atomic goals (is_atomic=true)
Non-atomic goals требуют:
1. Декомпозицию (decompose)
2. Агрегацию результатов детей
3. Обновление parent progress

ЭТО НЕ РАБОТАЕТ!
```

---

### Проблема #2: Parent progress НЕ обновляется (КРИТИЧНО!)

**Данные**:
```
"Оставить след в истории" (L0)
- Статус: active
- Progress: 0
- Дети: 7 (ВСЕ pending!)
- Возраст: 7.3 дней

"Получать устойчивый доход" (L0)
- Статус: active
- Progress: 0
- Дети: 7 (4 done, 1 pending, 2 active)
- Возраст: 11.5 дней
```

**Диагноз**: **Parent goals НЕ агрегируют прогресс детей**

**Ожидаемое поведение**:
```
Если 4/7 детей done → parent.progress = 4/7 ≈ 57%
Если ВСЕ дети done → parent.status = done
```

**Реальность**:
```
parent.progress = 0 (НЕ обновляется!)
parent.status = active (даже если дети done!)
```

---

### Проблема #3: Continuous/Directional goals marked as "done" (ОНТОЛОГИЧЕСКАЯ ОШИБКА!)

**Данные**:
```
17 continuous goals marked as "done"
3 directional goals marked as "done"
```

**Примеры**:
```
❌ "Интеллектуальное развитие" (continuous) → done
❌ "Личностный рост" (continuous) → done
❌ "Эмоциональное благополучие" (continuous) → done
❌ "Получать удовольствие от жизни" (directional) → done
```

**Почему это ОШИБКА**:
```
Continuous goals (по определению):
- НЕ имеют конечного состояния
- Требуют постоянного улучшения
- НЕ МОГУТ быть "done"

Directional goals (по определению):
- Указывают направление развития
- НЕ имеют конкретного критерия завершения
- НЕ МОГУТ быть "done"
```

**Причина**: Прямое присвоение `status = "done"` (41 место в коде!)

---

### Проблема #4: Execution trace ПОЛНОСТЬЮ ОТСУТСТВУЕТ

**Данные**:
```
42 goals в pending/active
0 execution_trace у этих целей
```

**Диагноз**: **Система НЕ выполняет non-atomic goals**

**Что работает**:
```
101 atomic (is_atomic=true) goals done
Среднее время: 3 дня ✅
```

**Что НЕ работает**:
```
32 non-atomic goals stuck
Worker НЕ подбирает их
Decomposition НЕ запускается
```

---

## 🎯 КОРНЕВАЯ ПРИЧИНА

### Сломанный Workflow Non-Atomic Goals

```
Текущая ситуация:
┌─────────────────────────────────────────────────────┐
│ 1. Goal создан (non-atomic)                  │
│    → status = "pending"                       │
│    → is_atomic = false                        │
│    → НИЧЕГО не происходит! ❌                │
│                                              │
│ 2. Ожидается: декомпозиция                   │
│    → НЕ происходит автоматически ❌              │
│    → Worker НЕ подбирает ❌                   │
│                                              │
│ 3. Результат: goal навсегда pending ❌        │
└─────────────────────────────────────────────────────┘
```

**Что ДОЛЖНО быть**:
```
Исправленный workflow:
┌─────────────────────────────────────────────────────┐
│ 1. Goal создан (non-atomic)                  │
│    → status = "pending"                       │
│                                              │
│ 2. Автоматически запускается decompose        │
│    → Создаёт children goals                   │
│    → parent.progress обновляется               │
│                                              │
│ 3. Children выполняются (atomic)              │
│    → Worker подбирает atomic goals            │
│    → Children done → parent progress = 50%      │
│                                              │
│ 4. Все дети done → parent done              │
│    → Агрегация результатов                   │
│    → parent.status = "done"                   │
└─────────────────────────────────────────────────────┘
```

---

## 📋 КОНКРЕТНЫЕ НЕИСПРАВНОСТИ

### 1. Декомпозиция не запускается автоматически

**Где искать**:
```
services/core/goal_decomposer.py
services/core/main.py (POST /goals/{id}/decompose)
```

**Проблема**:
```python
# endpoint существует, но НЕ вызывается автоматически
@app.post("/goals/{goal_id}/decompose")
async def decompose_goal(goal_id: str, max_depth: int = 1):
    # Этот endpoint требует MANUAL вызова
    # Нет автоматической триггер-системы
```

**Что нужно**:
```python
# Автоматический trigger
@staticmethod
async def auto_decompose_if_needed(goal: Goal):
    if goal.is_atomic == false and goal.status == "pending":
        await goal_decomposer.decompose(goal.id)
```

---

### 2. Parent progress не агрегируется

**Где искать**:
```
services/core/goal_executor.py
services/core/tasks.py (Celery tasks)
```

**Проблема**:
```python
# Когда child goal done, parent progress НЕ обновляется
await mark_goal_done(child_goal_id)
# → parent.goal.progress = 0 (BUG!)
```

**Что нужно**:
```python
# Агрегация прогресса
async def update_parent_progress(child_goal_id: str):
    child = await get_goal(child_goal_id)
    parent = await get_goal(child.parent_id)

    if parent:
        children = await get_children(parent.id)
        done_children = [c for c in children if c.status == "done"]

        parent.progress = len(done_children) / len(children)

        if len(done_children) == len(children):
            parent.status = "done"  # Все дети done

        await db.commit()
```

---

### 3. Прямые присвоения статуса

**Где искать**:
```
41 место в коде: goal.status = "done"
```

**Что нужно**:
```python
# Заменить ВСЕ прямые присвоения
# С:
goal.status = "done"

# На:
from goal_transition_service import goal_transition_service
await goal_transition_service.transition_goal(
    goal_id=goal.id,
    to_state="done",
    reason="Children completed",
    actor="system"
)
```

---

### 4. Continuous/directional ontology violation

**Где исправлять**:
```sql
-- Вернуть continuous goals в "ongoing"
UPDATE goals
SET status = 'ongoing',
    completed_at = NULL
WHERE goal_type = 'continuous' AND status = 'done';

-- Вернуть directional goals в "active"
UPDATE goals
SET status = 'active',
    completed_at = NULL
WHERE goal_type = 'directional' AND status = 'done';
```

---

## 🎯 ПЛАН ИСПРАВЛЕНИЯ

### Phase 1: Emergency Fixes (НЕМЕДЛЕННО)

1. **Разблокировать 32 stuck goals**
   - Запустить decompose для всех non-atomic pending goals
   - Создать children goals автоматически

2. **Исправить parent progress aggregation**
   - Добавить trigger на child completion
   - Обновить parent progress автоматически

3. **Исправить ontology violations**
   - Вернуть 17 continuous goals в "ongoing"
   - Вернуть 3 directional goals в "active"

---

### Phase 2: Systematic Fixes (1 неделя)

1. **Автоматическая декомпозиция**
   - Trigger decompose при создании non-atomic goal
   - Background job для stuck pending goals

2. **Progress aggregation**
   - Celery task для обновления parent progress
   - Trigger на child status change

3. **Убрать прямые присвоения**
   - Заменить на transition_goal()
   - Добавить CI guard (CHECK_NO_DIRECT_STATUS.sh)

---

### Phase 3: Prevention (2 недели)

1. **Invariant checking**
   - Hard invariants (уже готово)
   - Phase 1 deploy

2. **Acceleration layer**
   - Velocity monitoring (уже готово)
   - Drift detection (уже готово)
   - Early warning system

---

## 📊 ПРИОРИТЕТЫ

| Приоритет | Проблема | Влияние | Сложность |
|-----------|-----------|-----------|-----------|
| **P0** | Non-atomic goals не decompose | 32 goals stuck | Средняя |
| **P0** | Parent progress не обновляется | Родители broken | Средняя |
| **P1** | Continuous/directional ontology | 20 violations | Низкая |
| **P1** | Прямые присвоения статуса | Потенциальные bugs | Высокая |
| **P2** | Execution trace отсутствует | Нет аудит-трейла | Низкая |

---

## ✅ ЧТО УЖЕ ГОТОВО

1. ✅ **Goal Velocity Engine** — измеряет stuck goals
2. ✅ **Strategic Drift Detector** — найдёт recurrent failures
3. ✅ **AI Intervention Layer** — 10-day rule violations
4. ✅ **Transition Service** — единая точка переходов
5. ✅ **Hard Invariants** — предотвратит ontology violations

---

## 🚀 СЛЕДУЮЩИЕ ШАГИ

**Вариант A: Emergency Unblocking**
```bash
# 1. Разблокировать 32 stuck goals через force decompose
# 2. Исправить parent progress aggregation
# 3. Deploy Phase 1 (invariants)
```

**Вариант B: Systematic Refactor**
```bash
# 1. Исправить decomposition workflow
# 2. Исправить progress aggregation
# 3. Убрать прямые присвоения
# 4. Deploy Phase 1 + 2
```

---

**Ожидание решения**: Какой вариант выбираем?
