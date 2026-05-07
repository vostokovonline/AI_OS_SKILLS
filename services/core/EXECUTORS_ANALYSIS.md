# АНАЛИЗ ТРЕХ EXECUTOR-ОВ GOAL SYSTEM

## 📋 Executive Summary

В системе AI-OS существуют **три разных executor-а** для выполнения целей, создающих архитектурный хаос через циклические зависимости и дублирование логики.

---

## 🔍 Детальный анализ каждого executor

### 1. GoalExecutor (V1) — `goal_executor.py`

**Назначение:** Базовый executor для complex/non-atomic goals

**Ключевые характеристики:**
- ✅ Создает цели через `create_goal()`
- ✅ Работает с агентами (LangGraph)
- ✅ Делегирует atomic goals → V2 (строка 163-166)
- ⚠️ 7 прямых присвоений status (нарушают защиту)
- ✅ Использует Goal Contract v3.0
- ✅ Интеграция с Personality Engine

**Flow выполнения:**
```
execute_goal()
├── Проверка Goal Contract
├── Если atomic → делегирует в V2
└── Если complex → выполняет через agent_graph
    └── Работает до завершения или ошибки
```

**Используется в:**
- `api/endpoints/goals.py:63` — для non-atomic целей
- `main.py:289` — fallback execution
- Celery tasks

---

### 2. GoalExecutorV2 — `goal_executor_v2.py`

**Назначение:** Executor для atomic goals с Skills

**Ключевые характеристики:**
- ✅ Работает с Canonical Skills (SkillResult, Artifacts)
- ✅ Execution tracing
- ✅ Skill registry integration
- ⚠️ 6 прямых присвоений status
- ✅ Использует transition_goal() в большинстве мест
- ⚠️ Делегирует non-atomic → V1 (строка 102, 550)

**Flow выполнения:**
```
execute_goal()
├── Если atomic → _execute_atomic_goal()
│   ├── Parse requirements
│   ├── Select skill
│   ├── Execute skill
│   ├── Register artifacts
│   └── Check completion
└── Если complex → _delegate_to_original() → V1
```

**Используется в:**
- `api/endpoints/goals.py:61` — для atomic целей
- `main.py:286` — primary execution
- `goal_executor.py:166` — делегирование от V1

---

### 3. EnhancedGoalExecutor — `enhanced_goal_executor.py`

**Назначение:** "Улучшенный" executor (не используется в production)

**Ключевые характеристики:**
- ❌ **НЕ ИСПОЛЬЗУЕТСЯ** в API endpoints
- ✅ MVP Skills integration
- ✅ Deterministic Planner
- ✅ Artifact Registry
- ⚠️ 4 прямых присвоения status
- ⚠️ Делегирует complex → V1 (строка 248)

**Flow выполнения:**
```
execute_goal()
├── Если atomic → _execute_atomic_goal()
│   ├── Parse requirements
│   ├── Deterministic Planner
│   ├── Execute MVP Skill
│   ├── Verify artifacts
│   └── Check completion
└── Если complex → _execute_complex_goal() → V1
```

**Используется:**
- Только создан экземпляр `enhanced_goal_executor` (строка 391)
- **Нигде не вызывается в production коде!**

---

## 🔄 Циклические зависимости

### Диаграмма зависимостей:

```
┌─────────────────────────────────────────────────────────┐
│                    ЦИКЛИЧЕСКИЙ АД                       │
└─────────────────────────────────────────────────────────┘

    goal_executor.py (V1)
           │
           ├── is_atomic ──> goal_executor_v2.execute_goal()
           │
           └─ (complex) ───────────────────────────────┐
                                                      │
    goal_executor_v2.py (V2)                          │
           │                                          │
           ├── is_atomic ──> _execute_atomic_goal()   │
           │                                          │
           └─ (complex) ──> _delegate_to_original() ──┘
                                   │
                                   └─> GoalExecutor.execute_goal()


    enhanced_goal_executor.py
           │
           ├── is_atomic ──> _execute_atomic_goal()
           │
           └─ (complex) ──> _execute_complex_goal()
                                   │
                                   └─> GoalExecutor.execute_goal()
```

### Проблемы циклов:

1. **V1 → V2 → V1:** При определенных условиях можно попасть в бесконечный цикл
2. **Состояние теряется:** Каждый executor имеет свою сессию БД
3. **Статус рассинхронизируется:** V1 обновляет, V2 не видит изменений
4. **Race conditions:** Оба могут писать в одну цель одновременно

---

## 📊 Сравнительная таблица

| Характеристика | V1 | V2 | Enhanced |
|----------------|-----|-----|----------|
| **Статус** | Production | Production | **Dead code** |
| **Atomic goals** | Делегирует в V2 | ✅ Собственная логика | ✅ Собственная логика |
| **Complex goals** | ✅ Собственная логика | Делегирует в V1 | Делегирует в V1 |
| **Skills** | Нет | Canonical Skills | MVP Skills |
| **Artifacts** | Нет | ✅ SkillResult | ✅ Artifact Registry |
| **Execution trace** | Нет | ✅ Полный trace | Нет |
| **Transition service** | Частично | ✅ Большинство | Нет |
| **Status violations** | 7 | 6 | 4 |
| **Используется в API** | ✅ Да | ✅ Да | ❌ Нет |

---

## 🎯 Выводы и решения

### Что происходит сейчас:

```python
# API endpoint (api/endpoints/goals.py:60-63)
if goal.is_atomic:
    result = await goal_executor_v2.execute_goal(goal_id, session_id)  # → V2
else:
    result = await goal_executor.execute_goal(goal_id, session_id)      # → V1

# V1 при atomic (goal_executor.py:163-166)
if goal.is_atomic:
    return await goal_executor_v2.execute_goal(goal_id, session_id)      # → V2

# V2 при complex (goal_executor_v2.py:102)
else:
    return await self._delegate_to_original(goal, session_id)           # → V1
```

### Решение: Унифицированный GoalExecutor

**Стратегия:** Оставить V1 как единственный entry point, встроить в него логику V2

**План рефакторинга:**

#### Фаза 1: Подготовка (15 мин)
1. Выпилить `enhanced_goal_executor.py` (dead code)
2. Слить логику V2 в V1
3. Убрать циклическое делегирование

#### Фаза 2: Унификация (30 мин)
```python
# Новая структура goal_executor.py

class GoalExecutor:
    def __init__(self):
        self.skill_registry = SkillRegistry()  # From V2
        
    async def execute_goal(self, goal_id, session_id):
        goal = await self._get_goal(goal_id)
        
        # Единая точка входа
        if goal.is_atomic:
            return await self._execute_atomic(goal, session_id)  # Бывшая V2
        else:
            return await self._execute_complex(goal, session_id)  # Бывшая V1
    
    async def _execute_atomic(self, goal, session_id):
        # Логика из V2: skills, artifacts, verification
        pass
    
    async def _execute_complex(self, goal, session_id):
        # Логика из V1: agent graph, decomposition
        pass
```

#### Фаза 3: Фикс статусов (1 час)
1. Заменить 7 violations в V1 на transition_goal()
2. Заменить 6 violations в V2 (которая теперь часть V1)
3. Проверить интеграцию

---

## ⚡ Немедленные действия

### Рекомендация: Вариант А (упрощение)

**Шаг 1:** Удалить `enhanced_goal_executor.py` (dead code)
**Шаг 2:** Оставить V1 + V2, но убрать циклическое делегирование
**Шаг 3:** API всегда вызывает V1, V1 решает atomic/complex

**Изменения в API:**
```python
# Было:
if goal.is_atomic:
    result = await goal_executor_v2.execute_goal(goal_id, session_id)
else:
    result = await goal_executor.execute_goal(goal_id, session_id)

# Станет:
result = await goal_executor.execute_goal(goal_id, session_id)  # V1 решает
```

**Изменения в V1:**
```python
# goal_executor.py:163-166
# УБРАТЬ эту логику - V1 всегда обрабатывает сам
# if goal.is_atomic:
#     return await goal_executor_v2.execute_goal(goal_id, session_id)
```

**Изменения в V2:**
```python
# goal_executor_v2.py:100-102
# УБРАТЬ делегирование в V1
# else:
#     return await self._delegate_to_original(goal, session_id)
# 
# V2 становится чистым atomic executor-ом, никогда не видит complex
```

---

## 📈 Результат

**До:** 3 executors, циклические зависимости, 17+ violations
**После:** 2 executors (V1-main, V2-atomic), четкое разделение, 0 циклов

**Следующий шаг:** После разделения фиксим status violations в каждом отдельно.
