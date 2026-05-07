# AI-OS Production-Grade Architecture
## Полная интегрированная архитектура

---

## 1. Обзор Архитектуры

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI-OS PRODUCTION ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOMAIN LAYER                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐    │
│  │   models/   │  │   events/   │  │  services/  │  │    policies/    │    │
│  │             │  │             │  │             │  │                 │    │
│  │ trace.py    │  │ event.py    │  │ goal_       │  │ decision_       │    │
│  │ capability  │  │ (Domain     │  │ lifecycle   │  │ policies        │    │
│  │ .py         │  │  Events)    │  │ .py         │  │ .py             │    │
│  │             │  │             │  │ skill_      │  │                 │    │
│  │             │  │             │  │ selection   │  │                 │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │  use_cases/ │  │    ports/   │  │    dto/     │  │    context/     │   │
│  │             │  │             │  │             │  │                 │   │
│  │ execute_    │  │ GoalRepo    │  │ GoalDTO     │  │ context_       │   │
│  │ ready_goals │  │ Port        │  │ SkillDTO    │  │ builder.py     │   │
│  │ .py         │  │ Artifact    │  │ TraceDTO    │  │ (RAG+CodeGraph)│   │
│  │ decompose   │  │ Port        │  │             │  │                 │   │
│  │ _activated  │  │ LLM Port    │  │             │  │                 │   │
│  │ _goals.py   │  │ EventBus    │  │             │  │                 │   │
│  └─────────────┘  │    Port     │  └─────────────┘  └─────────────────┘   │
│                    └─────────────┘                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE LAYER                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │ persistence │  │   messaging │  │    llm/     │  │    logging/     │   │
│  │             │  │             │  │             │  │                 │   │
│  │ uow.py      │  │ event_bus   │  │ litellm     │  │ logging_        │   │
│  │ (SQLAlchemy)│  │ .py         │  │ _adapter    │  │ config.py       │   │
│  │             │  │             │  │ .py         │  │                 │   │
│  │ execution_  │  │             │  │             │  │ error_          │   │
│  │ repos       │  │             │  │             │  │ handler.py     │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             ADAPTERS LAYER                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │    api/     │  │   workers/  │  │  temporal/  │  │   dashboard/    │   │
│  │             │  │             │  │             │  │                 │   │
│  │ main.py     │  │ celery      │  │ workflows   │  │ React v2       │   │
│  │ (FastAPI)   │  │ tasks.py    │  │ (Continuous)│  │ (WebSocket)    │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Что Уже Существует vs Что Добавлено

### Существующие Компоненты (включены в архитектуру):

| Компонент | Файл | Статус |
|-----------|------|--------|
| GoalDomainService | `domain/goal_domain_service.py` | ✅ Интегрирован |
| Event Bus | `application/events/bus.py` | ✅ Интегрирован |
| Trace Store | `trace_store.py` | ✅ Интегрирован |
| Capability System | `capability/capability_graph.py` | ✅ Интегрирован |
| Skill Evolution | `skill_evolution.py` | ✅ Интегрирован |
| Semantic Memory | `semantic_memory.py` | ✅ Интегрирован |
| Belief System | `autonomy/beliefs.py` | ✅ Интегрирован |
| Decision Engine | `autonomy/decision_engine.py` | ✅ Интегрирован |
| UoW | `infrastructure/uow.py` | ✅ Интегрирован |

### Новые Компоненты (добавлены):

| Компонент | Файл | Назначение |
|-----------|------|------------|
| Execution Trace Domain | `domain/models/trace.py` | Формальная модель trace |
| Capability Domain | `domain/models/capability.py` | Формальная модель skill/capability |
| Domain Events | `domain/events/event.py` | Типы событий |
| Goal Lifecycle Machine | `domain/services/goal_lifecycle.py` | State machine для целей |
| Skill Selection Service | `domain/services/skill_selection.py` | Алгоритм выбора навыка |
| Context Builder | `application/context/context_builder.py` | RAG + CodeGraph для LLM |

---

## 3. Domain Layer (Подробно)

### 3.1 Models (`domain/models/`)

```
domain/models/
├── __init__.py          # Экспорт всех моделей
├── trace.py            # ExecutionTrace, TraceEvent, TraceStatistics
└── capability.py        # Capability, SkillManifest, SkillMetrics, Skill, CapabilityGraph
```

**trace.py** - Модель для трассировки выполнения:
- `TraceEventType` - типы событий (GOAL_CREATED, SKILL_STARTED, etc.)
- `TraceEvent` - атомарное событие
- `ExecutionTrace` - полный trace цели
- `TraceStatistics` - агрегированная статистика

**capability.py** - Модель для capability graph:
- `Capability` - абстрактная способность
- `SkillManifest` - контракт навыка
- `SkillMetrics` - метрики навыка (success_rate, latency, quality)
- `CapabilityGraph` - граф capabilities

### 3.2 Events (`domain/events/`)

```
domain/events/
├── __init__.py
└── event.py            # DomainEvent, GoalCreatedEvent, SkillCompletedEvent, etc.
```

Типы событий:
- Goal lifecycle: `GOAL_CREATED`, `GOAL_COMPLETED`, `GOAL_FAILED`, etc.
- Skill lifecycle: `SKILL_SELECTED`, `SKILL_INVOKED`, `SKILL_COMPLETED`
- Decision: `POLICY_SELECTED`, `REGRET_ANALYZED`
- Memory: `PATTERN_STORED`, `BELIEF_UPDATED`

### 3.3 Services (`domain/services/`)

```
domain/services/
├── __init__.py
├── goal_lifecycle.py   # GoalLifecycleMachine (state machine)
└── skill_selection.py  # SkillSelectionService (алгоритм выбора)
```

**GoalLifecycleMachine** - Формальная state machine:
```python
class GoalLifecycleState(Enum):
    CREATED → READY → PLANNING → EXECUTING → EVALUATING → COMPLETED
                                      ↓
                                   FAILED / BLOCKED / RETRY
```

**SkillSelectionService** - Алгоритм выбора навыка:
```python
score = (success_rate * 0.4) + (quality * 0.3) + (speed * 0.2) + (cost * 0.1)
```

---

## 4. Application Layer (Подробно)

### 4.1 Use Cases (`application/use_cases/`)

```
application/use_cases/
├── execute_ready_goals.py       # Выполнение готовых целей
├── decompose_activated_goals.py # Декомпозиция активированных целей
└── resume_pending_goals.py     # Возобновление ожидающих целей
```

### 4.2 Context OS (`application/context/`)

```
application/context/
└── context_builder.py   # LLM Context Builder (RAG + CodeGraph)
```

**ContextBuilder** - Построение контекста для LLM:
1. Goal context (из БД)
2. RAG search (semantic memory)
3. Code graph expansion (для кода)
4. Execution history (похожие цели)
5. Skill registry (доступные инструменты)
6. Patterns (удачные паттерны)
7. Truncate to token limit

### 4.3 Events (`application/events/`)

```
application/events/
├── __init__.py
├── bus.py              # EventBus (уже существует)
├── goal_events.py     # Goal-specific events
├── execution_events.py
└── decision_events.py
```

---

## 5. Интеграция Существующих Систем

### 5.1 Как связать новое с существующим:

| Существующее | Интеграция через |
|--------------|------------------|
| `trace_store.py` | Domain model `ExecutionTrace` + Event publishing |
| `capability_graph.py` | Domain `CapabilityGraph` + SkillSelectionService |
| `skill_evolution.py` | SkillMetrics в domain + evolution events |
| `semantic_memory.py` | ContextBuilder RAG + Event publishing |
| `autonomy/beliefs.py` | ContextBuilder patterns + Domain Events |
| `goal_transition_service.py` | GoalLifecycleMachine |

### 5.2 Event Flow (пример):

```
User creates goal
    │
    ▼
CreateGoalUseCase
    │
    ├─→ Creates Goal in DB
    │
    └─→ EventBus.publish(GoalCreatedEvent)
              │
              ├─→ trace_store.record()     (ExecutionTrace)
              ├─→ semantic_memory.index() (RAG)
              ├─→ analytics.notify()      (metrics)
              └─→ dashboard.update()       (WebSocket)
```

---

## 6. Migration Plan

### Phase 1: Domain Foundation (1-2 дня)
1. ✅ Создать `domain/models/trace.py`
2. ✅ Создать `domain/models/capability.py`
3. ✅ Создать `domain/events/event.py`
4. ✅ Создать `domain/services/goal_lifecycle.py`
5. ✅ Создать `domain/services/skill_selection.py`

### Phase 2: Application Layer (2-3 дня)
1. ✅ Создать `application/context/context_builder.py`
2. Интегрировать EventBus с domain events
3. Обновить use_cases для использования domain models
4. Обновить API endpoints для использования domain events

### Phase 3: Integration (3-5 дней)
1. Интегрировать trace_store с ExecutionTrace domain model
2. Интегрировать capability_graph с CapabilityGraph domain model
3. Интегрировать skill_evolution с SkillMetrics
4. Интегрировать semantic_memory с ContextBuilder
5. Интегрировать goal_transition_service с GoalLifecycleMachine

### Phase 4: Testing & Polish (2-3 дня)
1. Unit tests для domain services
2. Integration tests для use cases
3. E2E tests для полного flow
4. Performance testing

---

## 7. Критические Инварианты (для сохранения)

### 7.1 Goal Lifecycle:
- ✅ Continuous goals → `ONGOING`, NOT `COMPLETED`
- ✅ Directional goals → `ONGOING` or `FROZEN`, NOT `COMPLETED`
- ✅ Terminal states: `COMPLETED`, `FAILED`, `FROZEN` - нет переходов
- ✅ BLOCKED → READY только при выполненных зависимостях

### 7.2 Skill Selection:
- ✅ Experimental skills могут быть выбраны (для learning)
- ✅ Deprecated skills НЕ выбираются
- ✅ Confidence penalty при sample_count < 10
- ✅ Fallback chain при неудаче

### 7.3 Event System:
- ✅ Все domain events immutable
- ✅ Event handlers не блокируют publishing
- ✅ Failed handlers логируются, не падают

---

## 8. API Integration Points

### 8.1 Current endpoints сохраняются:
```python
# Goals
POST /goals/create
POST /goals/{id}/decompose
POST /goals/{id}/execute
POST /goals/{id}/evaluate

# Skills
POST /skills/invoke
GET /skills/list

# Execution
GET /execution/traces/{goal_id}
GET /execution/status

# Decision
GET /decision/policy/{goal_type}
POST /decision/evaluate
```

### 8.2 Новые endpoints:
```python
# Context
POST /context/build  # Build LLM context

# Events
GET /events/history
GET /events/metrics

# Lifecycle
GET /lifecycle/allowed-transitions/{goal_id}
POST /lifecycle/transition
```

---

## 9. Monitoring & Observability

### 9.1 Метрики:
- Event bus: events_published, events_handled, handlers count
- Goal lifecycle: transitions, failures, retries
- Skill selection: selection_count, success_rate per skill
- Context: token_count, sources_used

### 9.2 Логирование:
- Structured logging через `logging_config.py`
- Все domain events логируются
- Execution traces сохраняются

---

## 10. Summary

Архитектура AI-OS теперь формализована:

```
Domain Layer (чистая бизнес-логика)
    │
    ├─→ Models: Goal, Artifact, Skill, Capability, Trace
    ├─→ Events: GoalCreated, SkillInvoked, etc.
    ├─→ Services: LifecycleMachine, SkillSelector
    └─→ Policies: Decision policies
           │
           ▼
Application Layer (use cases + orchestration)
    │
    ├─→ Use cases: ExecuteGoal, DecomposeGoal, etc.
    ├─→ Context: RAG + CodeGraph builder
    └─→ Ports: Repository interfaces
           │
           ▼
Infrastructure Layer (реализации)
    │
    ├─→ SQLAlchemy repositories
    ├─→ Redis event bus
    ├─→ LiteLLM adapter
    └─→ Structlog logging
           │
           ▼
Adapters (внешние интерфейсы)
    │
    ├─→ FastAPI (REST)
    ├─→ Celery (async tasks)
    ├─→ Temporal (workflows)
    └─→ Dashboard (WebSocket)
```

**Ключевые улучшения:**
1. ✅ Формальная Goal Lifecycle Machine
2. ✅ Capability Graph + Skill Selection
3. ✅ Context OS для LLM
4. ✅ Domain Events для loose coupling
5. ✅ Execution Trace для learning
