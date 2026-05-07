# AI-OS Development Plan - Temporal.io Integration

## Текущее состояние (28.01.2026)

### ✅ Уже работает:
- **Celery** (ns_core_worker) - Chat, resume, cron задачи
- **LangGraph** (agent_graph.py) - Локальная оркестрация агентов
- **Temporal** - Базовая настройка, worker-ы определены, но НЕ запущены

### 🎯 Цель:
Внедрить Temporal.io там, где это принесет **МАКСИМУМ пользы**, сохраняя существующую систему.

---

## Архитектура: Гибридный подход

```
┌─────────────────────────────────────────────────────────────┐
│                    AI-OS Hybrid Architecture                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  📅 Temporal.io (Долгие workflows)                          │
│  ├─ Continuous Goals (ежедневные/еженедельные задачи)      │
│  ├─ Mission-level goals (дни/недели, с resume)             │
│  ├─ Multi-goal coordination (координация целей)            │
│  └─ Human-in-the-loop (требующие подтверждения)            │
│                                                               │
│  ⚡ LangGraph (Локальная оркестрация)                       │
│  ├─ Supervisor → Worker agents (секунды/минуты)            │
│  ├─ Tool execution                                          │
│  └─ Atomic goals (быстрая обработка)                       │
│                                                               │
│  🔄 Celery (Quick async tasks)                              │
│  ├─ Chat sessions                                            │
│  ├─ Resume tasks                                             │
│  └─ Simple cron jobs                                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Приоритеты внедрения Temporal

### 🔥 ПРИОРИТЕТ 1: Continuous Goals (Максимальная польза)

**Проблема:** Continuous goals (улучшение показателей, ежедневные задачи) требуют периодического выполнения.

**Решение:** Temporal Cron Workflows

**Примеры:**
- "Улучшать производительность системы каждую неделю"
- "Ежедневно проверять безопасность кода"
- "Постоянно оптимизировать базу данных"

**Выгода:**
- ✅ Гарантированное выполнение (даже при перезагрузках)
- ✅ Автоматический retry при ошибках
- ✅ История выполнения в Temporal UI
- ✅ Визуализация в Dashboard v2

**Файлы:**
- `services/temporal/workflows/continuous_goals.py` (новый)
- `services/temporal/activities/continuous_activities.py` (новый)

---

### 🔥 ПРИОРИТЕТ 2: Mission-level Goals (Высокая польза)

**Проблема:** Mission goals (L0) могут выполняться днями/неделями, требуется отказоустойчивость.

**Решение:** Temporal Long-Running Workflows

**Примеры:**
- "Построить AI-powered систему за 3 месяца"
- "Достичь 1000 активных пользователей"
- "Масштабировать архитектуру до 1M запросов/сек"

**Выгода:**
- ✅ Автоматический resume после сбоев
- ✅ Версионирование workflows
- ✅ SAGA pattern для compensation
- ✅ Детальная история выполнения

**Файлы:**
- `services/temporal/workflows/mission_goals.py` (новый)
- Интеграция с `goal_executor.py`

---

### 🟡 ПРИОРИТЕТ 3: Multi-Goal Coordination (Средняя польза)

**Проблема:** Некоторые цели требуют координации нескольких подцелей параллельно.

**Решение:** Temporal Child Workflows

**Примеры:**
- Параллельное выполнение независимых подцелей
- Кросс-доменные операции (код + инфра + тесты)
- Pipeline целей (последовательное выполнение)

**Выгода:**
- ✅ Параллельное выполнение с оркестрацией
- ✅ Обработка зависимостей
- ✅ Timeout на каждом этапе

**Файлы:**
- Расширение `goal_workflows.py`

---

### 🟡 ПРИОРИТЕТ 4: Dashboard v2 Visualization

**Проблема:** Нужно видеть состояние Temporal workflows в реальном времени.

**Решение:** Интеграция Temporal UI в Dashboard v2

**Что добавить:**
- Статус Temporal workflows
- История выполнения
- Cron schedule visualization
- Retry/compensation events

**Файлы:**
- `services/dashboard_v2/src/components/temporal/` (новый)
- `services/dashboard_v2/src/api/temporal.ts` (новый)

---

### ⚪ НИЗКИЙ ПРИОРИТЕТ (Не трогать):

**❌ Chat/resume задачи** - Celery справляется отлично
**❌ Atomic goals** - LangGraph лучше
**❌ Quick API operations** - Синхронное выполнение достаточно

---

## План реализации

### Phase 1: Continuous Goals (1-2 дня)

1. **Создать Temporal Cron Workflow**
   ```python
   @workflow.defn
   class ContinuousGoalWorkflow:
       @workflow.run
       async def run(self, goal_id: str, cron_schedule: str):
           while True:
               # Execute goal
               result = await workflow.execute_activity(...)
               # Wait for next cron
               await workflow.wait_condition(lambda: time_to_run)
   ```

2. **Добавить activities для continuous goals**
   - `evaluate_continuous_goal()` - Проверка прогресса
   - `generate_next_action()` - Следующее действие
   - `update_trend_metrics()` - Обновление метрик

3. **Интеграция с goal_executor.py**
   - Определять continuous goals и перенаправлять в Temporal

4. **Тестирование**
   - Создать тестовый continuous goal
   - Проверить cron execution
   - Проверить resume после перезагрузки

### Phase 2: Mission-level Goals (2-3 дня)

1. **Создать Mission Goal Workflow**
   ```python
   @workflow.defn
   class MissionGoalWorkflow:
       @workflow.run
       async def run(self, goal_id: str):
           # Decompose into strategic goals
           subgoals = await self.decompose(goal_id)

           # Execute in parallel/sequence
           for subgoal in subgoals:
               await self.execute_subgoal(subgoal)

           # Evaluate mission completion
           await self.evaluate(goal_id)
   ```

2. **Human-in-the-loop activities**
   - `request_human_approval()` - Запрос подтверждения
   - `wait_for_human_input()` - Ожидание ввода
   - `send_notification()` - Уведомления

3. **SAGA pattern для compensation**
   - Компенсация при отмене подцелей
   - Rollback механизмы

### Phase 3: Dashboard v2 Integration (1-2 дня)

1. **Temporal API client**
   ```typescript
   export const temporalClient = {
     getWorkflowStatus: (id: string) => ...
     getWorkflowHistory: (id: string) => ...
     getCronWorkflows: () => ...
   }
   ```

2. **Temporal visualization components**
   - WorkflowTimeline.tsx
   - CronScheduleView.tsx
   - WorkflowHistory.tsx

3. **Интеграция в GraphCanvas**
   - Показывать Temporal workflows на графе

### Phase 4: Documentation & Testing (1 день)

1. **Обновить CLAUDE.md**
   - Добавить секцию про Temporal
   - Описать когда использовать Temporal vs Celery vs LangGraph

2. **Добавить тесты**
   - Unit тесты для activities
   - Integration тесты для workflows

3. **Примеры использования**
   - Continuous goal examples
   - Mission goal examples

---

## Метрики успеха

- ✅ Continuous goals выполняются по расписанию
- ✅ Mission goals resume после сбоев
- ✅ Dashboard v2 показывает Temporal workflows
- ✅ Система работает в гибридном режиме (Celery + Temporal + LangGraph)
- ✅ Производительность не ухудшилась

---

## Риски и митигация

### Риск 1: Temporal server выход из строя
**Митигация:** Docker auto-restart + backup истории

### Риск 2: Слишком сложная архитектура
**Митигация:** Четкое разделение ответственности (Temporal = долгие workflows, LangGraph = агенты, Celery = быстрые задачи)

### Риск 3: Проблемы с производительностью
**Митигация:** Мониторинг + возможность отключить Temporal без ломки системы

---

## Следующие шаги

1. ✅ Создать план (DONE)
2. 🚧 Реализовать Phase 1: Continuous Goals
3. 🚧 Реализовать Phase 2: Mission-level Goals
4. 🚧 Реализовать Phase 3: Dashboard v2 Integration
5. 🚧 Реализовать Phase 4: Documentation & Testing

---

## Критерии завершения

Phase 1 завершен, когда:
- [ ] Temporal Cron workflow работает
- [ ] Continuous goal выполняется по расписанию
- [ ] Resume после перезагрузки работает
- [ ] Есть хотя бы 1 тестовый continuous goal

Phase 2 завершен, когда:
- [ ] Mission goal workflow работает
- [ ] Human-in-the-loop интегрирован
- [ ] SAGA pattern реализован
- [ ] Есть пример mission goal с Decomposition

Phase 3 завершен, когда:
- [ ] Dashboard v2 показывает Temporal workflows
- [ ] Есть компонент для cron schedule visualization
- [ ] История выполнения доступна в UI

Phase 4 завершен, когда:
- [ ] CLAUDE.md обновлен
- [ ] Тесты написаны
- [ ] Примеры использования есть
