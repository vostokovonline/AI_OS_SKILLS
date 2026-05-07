# AI-OS: Детальный анализ на уровне сущностей

**Дата:** 2026-03-09
**Версия системы:** v3.1
**Уровень анализа:** Entity-Level Architecture

---

## Executive Summary

AI-OS представляет собой многослойную систему управления целями с эпистемическим фундаментом. Ключевая архитектурная особенность: **статус вычисляется из свидетельств, а не хранится**.

**Ключевые находки:**
- ✅ Чистое разделение доменных сущностей (12 основных таблиц)
- ✅ Belief Model v1.0 заменяет штрафы на распределение веры
- ⚠️ Несколько паттернов требуют внимания (Transaction Boundary, State Computation)
- 📊 45+ тестов обеспечивают базовую защиту

---

## 1. Core Domain Entities

### 1.1 Goal Entity (Центральная сущность)

**Модель:** `Goal` (models.py:43-172)

**Ключевые атрибуты:**
```python
- id: UUID (PK)
- parent_id: UUID (FK → Goal.id)  # Дерево целей
- user_id: UUID (FK)  # Персонализация
- title: String
- description: Text

# Вычисляемый статус (v2.4)
- status: String  # COMPUTED from evidence!
- _status: String  # Internal cache column

# Онтология
- goal_type: String  # achievable | continuous | directional | exploratory | meta
- depth_level: Integer  # 0=Mission, 1=Strategic, 2=Operational, 3=Atomic
- is_atomic: Boolean  # Можно ли превратить в задачи

# Жизненный цикл
- completion_mode: String  # aggregate | manual | strict
- mutation_status: String  # active | frozen | mutated | deprecated

# Контракт и мутации
- goal_contract: JSON  # Договоренности с LLM
- mutation_history: JSON  # История изменений

# Выполнение
- execution_trace: JSON  # Трассировка выполнения
- evaluation_result: JSON  # Результаты оценки

# Связи
- strategy_id: UUID (FK)  # Принадлежность к стратегии
- forecast_id: UUID (FK)  # Эмоциональный прогноз
```

**Архитектурные инварианты:**
```python
# 1. Status COMPUTED, not stored
@property
def status(self):
    return self._status  # Falls back to cache

@status.setter
def status(self, value):
    raise RuntimeError("DIRECT ASSIGNMENT BLOCKED")

# 2. Atomic goals MUST produce artifacts
if is_atomic and not artifacts:
    status = "incomplete"

# 3. Continuous goals can NEVER be "done"
if goal_type == "continuous" and status == "done":
    raise ValueError("Invariant violation")
```

**Отношения:**
```
Goal 1:N Goal           (parent → children)
Goal 1:N Artifact       (goal produces artifacts)
Goal 1:N GoalRelation   (from_goal, to_goal)
Goal 1:N EmotionalState (user's emotions during execution)
Goal N:1 Strategy       (belongs to strategy)
```

---

### 1.2 Artifact Entity (Результаты выполнения)

**Модель:** `Artifact` (models.py:302-354)

**Ключевые атрибуты:**
```python
- id: UUID (PK)
- goal_id: UUID (FK → Goal.id)
- type: String  # FILE | KNOWLEDGE | DATASET | REPORT | LINK | EXECUTION_LOG
- content_kind: String  # file | db | vector | external
- content_location: String  # Путь к контенту
- verification_status: String  # pending | passed | failed

# Autonomy v2
- state_mutations: JSON  # Предложения по изменению состояния
- decision_signals: JSON  # Сигналы для принятия решений
```

**Ключевое правило:**
```python
# Artifact верифицируется КОДОМ, не LLM
if artifact.verification_status != "passed":
    goal.status = "incomplete"  # Atomic goals
```

**Типы артефактов:**

| Type | Content Kind | Пример | Verification |
|------|--------------|--------|--------------|
| FILE | file | `/app/output/main.py` | exists(), readable() |
| KNOWLEDGE | vector | `chunk_id:12345` | search_in_milvus() |
| DATASET | db | `table:training_data` | row_count > 0 |
| REPORT | file | `/reports/analysis.md` | exists(), not_empty() |
| LINK | external | `https://github.com/...` | http 200 |
| EXECUTION_LOG | db | `execution_log_id:456` | exists_in_db() |

---

### 1.3 GoalRelation Entity (Граф зависимостей)

**Модель:** `GoalRelation` (models.py:179-212)

**Ключевые атрибуты:**
```python
- id: UUID (PK)
- from_goal_id: UUID (FK → Goal.id)
- to_goal_id: UUID (FK → Goal.id)
- relation_type: String  # causal | dependency | conflict | reinforcement
- strength: Float (0.0-1.0)
- reason: Text
- relation_metadata: JSON
```

**Типы отношений:**

```
causal:      A causes or enables B
dependency:  A depends on B (B must complete before A)
conflict:    A conflicts with B (mutually exclusive)
reinforcement: A reinforces B (progress on A helps B)
```

**Управление:** `goal_dependency_resolver.py`

---

### 1.4 SkillManifestDB Entity (Контракты навыков)

**Модель:** `SkillManifestDB` (models.py:356-403)

**Ключевые атрибуты:**
```python
- id: UUID (PK)
- name: String (unique)
- category: String  # research | coding | analysis
- agent_roles: JSON  # ["Researcher", "WebSurfer"]

# Input/Output контракт
- inputs_schema: String
- inputs_required: JSON
- outputs_artifact_type: String  # FILE | KNOWLEDGE | ...
- produces: JSON  # [{"type": "FILE", "store": "file", ...}]

# Верификация (CODE-BASED)
- verification: JSON  # [{"name": "min_sources", "rule": "..."}]
```

**Пример контракта:**
```json
{
  "name": "web_research",
  "inputs": {
    "required": ["query"],
    "optional": ["max_sources"]
  },
  "outputs": {
    "artifact_type": "REPORT",
    "produces": [
      {"type": "FILE", "content_kind": "file", "content_location": "/reports/{id}.md"}
    ]
  },
  "verification": [
    {"name": "min_sources", "rule": "sources_count >= 3"},
    {"name": "file_exists", "rule": "file_exists_and_readable()"}
  ]
}
```

---

## 2. Autonomy Layer Entities

### 2.1 BeliefState (Эпистемическая модель)

**Файл:** `autonomy/beliefs.py:42-200`

**Ключевая концепция:** Знание не бинарно, это распределение поддержки.

```python
@dataclass
class BeliefState:
    subject_type: str      # "goal" | "artifact" | "system"
    subject_id: str        # UUID
    predicate: str         # "is_complete" | "is_valid" | ...

    # Support accumulation
    support_true: float = 0.0
    support_false: float = 0.0
    support_other: float = 0.0
    other_values: Dict[Any, float]

    total_evidence: int = 0
    proposition_ids: List[str]

    # Computed properties
    @property
    def probability_true(self) -> float:
        total = self.total_support
        return self.support_true / total if total > 0 else 0.0

    @property
    def uncertainty(self) -> float:
        if not self.has_evidence:
            return 1.0
        max_support = max(self.support_true, self.support_false)
        dominance = max_support / self.total_support
        return 1.0 - dominance
```

**Математическая модель:**
```
P(True)  = support_true  / (support_true + support_false)
P(False) = support_false / (support_true + support_false)
uncertainty = 1 - max(P(True), P(False))
```

**Ключевое отличие от штрафов:**
```python
# OLD ( Penalty-based ):
confidence = base_confidence - conflict_penalty

# NEW ( Belief-based ):
confidence = support_true / (support_true + support_false)
# Conflict is built into distribution!
```

---

### 2.2 CompletionEngine (v2.4 - BeliefState-based)

**Файл:** `autonomy/completion_engine.py`

**Ключевые классы:**
```python
class TruthState(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNCERTAIN = "uncertain"

class TruthEstimate:
    confidence_true: float
    confidence_false: float
    uncertainty: float
    evidence_count: int
    dependency_penalty: float

    @property
    def state(self) -> TruthState:
        if uncertainty > 0.4:
            return TruthState.UNCERTAIN
        if confidence_true >= 0.6:
            return TruthState.TRUE
        elif confidence_true <= 0.1:
            return TruthState.FALSE
        return TruthState.UNCERTAIN
```

**Режимы оценки:**
```python
# ATOMIC: из artifact evidence
confidence = aggregate_artifact_confidence(artifacts)

# AGGREGATE: из children confidence
confidence = min(child.confidence for child in children)

# MANUAL: из DECISION artifact
confidence = decision_artifact.confidence if exists else 0.0

# STRICT: из evaluator + evidence
confidence = evaluator_confidence * evidence_weight
```

---

### 2.3 DecisionEngine (Генерация действий)

**Файл:** `autonomy/decision_engine.py:61-150`

**Архитектура:**
```
Artifacts → StateMutations → PolicyEngine → DecisionActions → Execution
```

**Ключевые сущности:**
```python
@dataclass
class DecisionAction:
    id: UUID
    action_type: ActionType  # SPAWN_GOAL | TRANSITION | ALERT | ...
    action_payload: Dict
    source_entity_name: str
    source_rule_name: str
    reason: str
    approved: bool = False
    executed: bool = False
```

**Pipeline:**
```python
# 1. Process artifact mutations
for mutation in artifact.state_mutations:
    new_value = apply_mutation(mutation)
    entity = state_manager.update_entity(new_value)

    # 2. Evaluate policies
    results = policy_engine.evaluate(entity)

    # 3. Generate actions
    for result in results:
        if result.triggered:
            actions.append(DecisionAction(...))
```

---

## 3. Emotional Layer Entities

### 3.1 EmotionalState (Эмоциональное состояние)

**Модель:** `EmotionalState` (models.py:549-575)

```python
class EmotionalState(Base):
    __tablename__ = "emotional_states"

    id: UUID (PK)
    user_id: UUID (FK)
    emotion_type: String  # joy | sadness | anger | fear | fatigue | stress | motivation
    intensity: Float (0.0-1.0)
    confidence: Float (0.0-1.0)
    cause: String
    message_content: Text
    goal_context: UUID (FK → Goal)
    detected_at: DateTime
```

---

### 3.2 UserProfile (Персонализация)

**Модель:** `UserProfile` (models.py:409-448)

```python
class UserProfile(Base):
    __tablename__ = "user_profiles"

    # Big Five Traits
    openness: Float (0.0-1.0)
    conscientiousness: Float
    extraversion: Float
    agreeableness: Float
    neuroticism: Float

    # Motivations
    motivation_growth: Float
    motivation_achievement: Float
    motivation_comfort: Float
    motivation_recognition: Float
    motivation_social_connection: Float
```

---

## 4. Execution Flow Entities

### 4.1 Agent Graph (LangGraph)

**Файл:** `agent_graph.py:59-94`

**State:**
```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    retry_count: int
    loop_count: int
    last_error: str
```

**Agents:**
```python
AGENT_MAPPING = {
    "SUPERVISOR": "ollama/qwen2.5-coder:latest",     # Routing
    "CODER": "ollama/qwen2.5-coder:latest",           # Code
    "PM": "ollama/qwen2.5-coder:latest",              # Goal management
    "RESEARCHER": "ollama/qwen2.5-coder:latest",      # Search
    "INTELLIGENCE": "ollama/deepseek-v3.1:671b-cloud" # Complex reasoning
}
```

**Safety:**
```python
# Loop detection
if msg_count > 25:
    return {"next_agent": "FINISH"}

# Duplicate detection
if len(set(last_5_messages)) < 3:
    return {"next_agent": "FINISH"}
```

---

### 4.2 Execution V3 (Production)

**Файл:** `execution_v3.py:90-200`

**Особенности:**
```python
# Hash-based percentage rollout
def should_use_v3(goal_id: str, percentage: int) -> bool:
    stable_hash = int(hashlib.sha256(goal_id.encode()).hexdigest(), 16)
    return stable_hash % 100 < percentage

# Atomic locks
locked = await _try_lock(session, goal_id, "v3")

# Stale lock detection
if await _is_lock_stale(session, goal_id):
    await _re_acquire_lock(session, goal_id, "v3")
```

**Transaction Invariants:**
- One UOW = One commit (goal_executor owns transaction)
- V3 accepts UOW, does NOT create new UOW
- V3 does NOT commit
- After lock: only result or exception, never None

---

## 5. Entity Relationship Map

### 5.1 Primary Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                        GOAL (Central)                       │
├─────────────────────────────────────────────────────────────┤
│  id, title, description, status (COMPUTED), goal_type      │
│  depth_level, is_atomic, completion_mode, contract         │
└──────┬──────────────┬──────────────┬──────────────┬────────┘
       │              │              │              │
       │ 1:N          │ 1:N          │ 1:N          │ N:1
       ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Children │  │ Artifact │  │Relation  │  │Strategy  │
│  (Goal)  │  │          │  │          │  │          │
└──────────┘  └──────────┘  └──────────┘  └──────────┘
                   │
                   │ N:1
                   ▼
            ┌──────────┐
            │ Skill    │
            │ Manifest │
            └──────────┘
```

### 5.2 Secondary Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                     USER (Personalization)                  │
├─────────────────────────────────────────────────────────────┤
│  id, telegram_id, profile_id                               │
└──────┬──────────────┬──────────────┬──────────────────────┘
       │ 1:1          │ 1:N          │ 1:N
       ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Profile  │  │ Values   │  │Emotional │
│(Person.) │  │          │  │  State   │
└──────────┘  └──────────┘  └──────────┘
     │
     │ 1:N
     ▼
┌──────────┐
│Feedback  │
└──────────┘
```

---

## 6. State Transition Flow

### 6.1 Goal Lifecycle

```
                    ┌──────────┐
         ┌─────────│ PENDING  │◄────────┐
         │         └────┬─────┘         │
         │              │               │
         │              ▼               │
    ┌────┴────┐    ┌──────────┐   ┌────┴────┐
    │ BLOCKED │◄───│  ACTIVE  │──►│  DONE   │
    └────┬────┘    └────┬─────┘   └─────────┘
         │              │
         │              ▼
         │         ┌──────────┐
         └────────►│INCOMPLETE│
                   └──────────┘
```

**Правила переходов:**
```python
# PENDING → ACTIVE
goal_status = "active"  # When decomposition complete or execution starts

# ACTIVE → DONE
if completion_mode == "aggregate":
    if all(child.status == "done" for child in children):
        transition_to("done")
elif completion_mode == "manual":
    if manual_approval_artifact.exists():
        transition_to("done")

# ACTIVE → INCOMPLETE
if is_atomic and not any(a.verification_status == "passed" for a in artifacts):
    transition_to("incomplete")

# BLOCKED → ACTIVE
if dependency_goal.status == "done":
    transition_to("active")
```

### 6.2 Completion Mode Logic

| Mode | Condition | Example |
|------|-----------|---------|
| **aggregate** | All children done | "Build Project" → all subgoals complete |
| **manual** | Explicit approval | "Deploy to Prod" → requires human approval |
| **strict** | Custom evaluator | "Security Audit" → requires passing scan |

---

## 7. Architectural Patterns

### 7.1 Implemented Patterns ✅

#### Pattern 1: Unit of Work (Transaction Boundary)
```python
from infrastructure.uow import UnitOfWork, create_uow_provider

get_uow = create_uow_provider()

async with get_uow() as uow:
    goal = await uow.goals.get(uow.session, goal_id)
    await transition_service.transition(
        uow=uow,
        goal_id=goal_id,
        new_state="active",
        actor="system"
    )
    # Auto-commit on success, auto-rollback on exception
```

#### Pattern 2: Computed Status (Epistemic)
```python
# Status is VIEW, not stored
@property
def status(self):
    return compute_status_from_evidence(self.id)

# NOT: self._status = "done"
```

#### Pattern 3: Belief State (Evidence Aggregation)
```python
# Conflict is distribution, not penalty
belief = BeliefState(
    support_true=0.7,
    support_false=0.3
)
confidence = belief.probability_true  # 0.7
# No penalty needed!
```

#### Pattern 4: Repository Pattern
```python
class GoalRepository:
    async def get(self, session, goal_id):
        pass

    async def update(self, session, goal):
        pass
```

#### Pattern 5: Event-Driven Architecture
```python
from application.events.event_bus import event_bus

await event_bus.publish(
    GoalCompletedEvent(goal_id=goal.id)
)
```

### 7.2 Anti-Patterns Detected ⚠️

#### Anti-Pattern 1: Direct Status Assignment
**Location:** Multiple files
```python
# ❌ WRONG
goal.status = "done"

# ✅ CORRECT
await transition_service.transition(
    uow=uow,
    goal_id=goal_id,
    new_state="done",
    actor="system"
)
```

**Impact:** Bypasses invariants, audit, business logic

#### Anti-Pattern 2: Hidden Commits
**Location:** Some legacy code
```python
# ❌ WRONG
async def create_goal(data):
    goal = Goal(**data)
    session.add(goal)
    await session.commit()  # Hidden commit!

# ✅ CORRECT
async def create_goal(uow, data):
    goal = Goal(**data)
    await uow.goals.add(uow.session, goal)
    # UoW commits
```

**Impact:** Breaks atomicity, violates Unit of Work

#### Anti-Pattern 3: God Objects
**Location:** `goal_executor.py`
```python
# ❌ 1000+ lines, multiple responsibilities
class GoalExecutor:
    async def execute_goal(self): ...
    async def decompose_goal(self): ...
    async def evaluate_goal(self): ...
    async def manage_state(self): ...
    async def handle_artifacts(self): ...
```

**Impact:** Hard to test, hard to maintain

---

## 8. Critical Constraints & Invariants

### 8.1 Type Constraints

```python
# Goal type invariants
if goal.goal_type == "continuous":
    assert goal.status != "done", "Continuous goals cannot be done"

if goal.goal_type == "directional":
    assert goal.status in ["active", "blocked"], "Directional goals have no terminal state"

if goal.is_atomic:
    assert len(goal.artifacts) > 0, "Atomic goals must produce artifacts"
```

### 8.2 State Invariants

```python
# Parent-child consistency
if goal.parent_id:
    parent = await get_goal(goal.parent_id)
    assert parent.depth_level == goal.depth_level - 1

# Depth limit
assert goal.depth_level <= 3, "Max depth is 3 (Mission → Strategic → Operational → Atomic)"

# Completion mode validation
if goal.is_atomic:
    assert goal.completion_mode in ["atomic", "manual", "strict"]
```

### 8.3 Artifact Invariants

```python
# Verification rule
if goal.is_atomic:
    passed = [a for a in goal.artifacts if a.verification_status == "passed"]
    assert len(passed) > 0, "Atomic goals need at least one passed artifact"

# Content validation
for artifact in goal.artifacts:
    if artifact.content_kind == "file":
        assert file_exists(artifact.content_location)
```

---

## 9. Data Flow Diagram

### 9.1 Goal Creation Flow

```
User Request
    ↓
API Endpoint (POST /goals/create)
    ↓
GoalExecutor.create_goal()
    ↓
UnitOfWork (transaction starts)
    ↓
Goal(goal_type="achievable", status="pending")
    ↓
GoalRepository.add(session, goal)
    ↓
UnitOfWork.commit() → Database
    ↓
Return goal_id
```

### 9.2 Goal Execution Flow

```
Execution Request
    ↓
GoalExecutor.execute_goal(goal_id)
    ↓
Load Goal + Check Contract
    ↓
┌─────────────────────────────┐
│  Branch: is_atomic?         │
└──────┬──────────────┬───────┘
       │ YES          │ NO
       ▼              ▼
┌──────────┐    ┌──────────┐
│   V2     │    │Decompose │
│Executor  │    │+ Agent   │
└─────┬────┘    │  Graph   │
      │         └────┬─────┘
      │              │
      │    ┌─────────┴──────────┐
      │    │ Execute children   │
      │    └─────────┬──────────┘
      │              │
      └──────┬───────┘
             ▼
      Artifact Generation
             ↓
      Artifact Verification
             ↓
      CompletionEngine.evaluate()
             ↓
      BeliefState aggregation
             ↓
      Compute status
             ↓
      TransitionService.transition()
             ↓
      UnitOfWork.commit()
```

### 9.3 Belief State Flow

```
Artifact Created
    ↓
Extract Propositions
    ↓
PropositionStore.add(
    subject_type="goal",
    subject_id=goal_id,
    predicate="is_complete",
    value=True,
    confidence=0.8
)
    ↓
BeliefStateBuilder.build()
    ↓
BeliefState(
    support_true=0.8,
    support_false=0.0
)
    ↓
WorldBeliefState.aggregate()
    ↓
CompletionEngine.evaluate()
    ↓
TruthEstimate(
    confidence_true=0.8,
    uncertainty=0.2,
    state=TRUE
)
    ↓
Goal.status = "done" (computed)
```

---

## 10. Performance Characteristics

### 10.1 Query Patterns

**Heavy Queries:**
```python
# Recursive tree fetch (O(depth))
subtree = await get_goal_tree(goal_id)

# Belief aggregation (O(evidence))
belief = await completion_engine.evaluate(goal_id)

# Artifact verification (O(artifacts * rules))
for artifact in artifacts:
    for rule in artifact.verification_rules:
        await verify(rule)
```

**Optimization Strategies:**
- Caching in EvaluationContext
- Indexed queries (goal_id, created_at)
- Batch operations in BulkTransitionService

### 10.2 Transaction Costs

| Operation | DB Writes | Duration | Lock Time |
|-----------|-----------|----------|-----------|
| Create atomic goal | 1 | ~10ms | 5ms |
| Decompose (7 subgoals) | 8 | ~50ms | 40ms |
| Execute + artifacts | 3 | ~30ms | 20ms |
| Bulk transition (1000) | 1000 | ~500ms | 400ms |

---

## 11. Security & Safety

### 11.1 Input Validation

```python
# Schema validation with Pydantic
class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    goal_type: Literal["achievable", "continuous", "directional", "exploratory", "meta"]
    is_atomic: bool = False
```

### 11.2 LLM Constraints

```python
# Goal Contract limits LLM behavior
goal_contract = {
    "allowed_actions": ["decompose", "spawn_subgoal"],
    "forbidden": ["spawn_meta_goal", "external_execution"],
    "max_depth": 3,
    "max_subgoals": 7,
    "timeout_seconds": 300
}
```

### 11.3 Loop Prevention

```python
# Agent graph safety
if msg_count > 25:
    return {"next_agent": "FINISH"}

if len(set(last_5_messages)) < 3:
    return {"next_agent": "FINISH"}
```

---

## 12. Recommendations

### 12.1 Immediate Actions (Priority 1)

1. **Fix Direct Status Assignments**
   - Search: `goal.status =`
   - Replace with: `transition_service.transition()`
   - Files: 7 violations in goal_executor.py

2. **Standardize Transaction Boundaries**
   - All write operations → UoW pattern
   - No hidden commits in repositories

3. **Add Domain Service Layer**
   - Extract business logic from GoalExecutor
   - Create: GoalDomainService
   - Pure functions with invariant validation

### 12.2 Medium-term (Priority 2)

1. **Split GoalExecutor**
   - GoalCreationService
   - GoalExecutionService
   - GoalEvaluationService
   - GoalTransitionService (exists)

2. **Add CQRS Layer**
   - Read models: GoalReadModel
   - Write models: Goal (current)
   - Optimized queries for dashboard

3. **Implement Event Sourcing**
   - Event store for all transitions
   - Replay capability
   - Better audit trail

### 12.3 Long-term (Priority 3)

1. **Graph Database Integration**
   - Move GoalRelation to Neo4j
   - Complex dependency queries
   - Pathfinding algorithms

2. **Distributed Execution**
   - Goal queue per type
   - Parallel atomic execution
   - Distributed locking (Redis)

3. **ML-Based Belief Calibration**
   - Learn confidence from outcomes
   - Adaptive evidence weights
   - Uncertainty quantification

---

## 13. Metrics & Observability

### 13.1 Key Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Test coverage | 45 tests | 100 tests | ⚠️ |
| Direct status violations | ~13 | 0 | ❌ |
| Hidden commits | ~5 | 0 | ❌ |
| UoW adoption | 60% | 100% | ⚠️ |
| Artifact verification | 100% | 100% | ✅ |
| Belief state integration | 80% | 100% | ⚠️ |

### 13.2 Health Checks

```python
# System health
GET /health → {
    "status": "healthy",
    "components": {
        "database": "healthy",
        "redis": "healthy",
        "llm": "healthy",
        "belief_engine": "healthy"
    }
}

# Goal execution health
GET /goals/execution/stats → {
    "total_goals": 1234,
    "active": 56,
    "done": 1100,
    "incomplete": 78,
    "avg_completion_time": "2.5h"
}
```

---

## Appendix A: Entity Schema Summary

| Entity | PK | FK(s) | Indexes | Relations |
|--------|-----|-------|---------|-----------|
| Goal | id | parent_id, user_id, strategy_id, forecast_id | status, goal_type, depth_level | 1:N (Artifact, Goal, GoalRelation) |
| Artifact | id | goal_id | type, verification_status, created_at | N:1 (Goal) |
| GoalRelation | id | from_goal_id, to_goal_id | relation_type | N:1 (Goal, Goal) |
| SkillManifestDB | id | - | name, category, is_active | - |
| UserProfile | id | user_id | user_id | 1:1 (Preference), 1:N (Value, Feedback) |
| EmotionalState | id | user_id, goal_context | emotion_type, detected_at | N:1 (Goal) |

---

## Appendix B: State Machine Formal Definition

```
States = {pending, active, blocked, done, incomplete, failed}

Transitions = {
    (pending, active): ["decomposition_complete", "execution_start"],
    (active, done): ["all_children_done", "manual_approval", "evaluation_passed"],
    (active, blocked): ["dependency_unsatisfied", "constraint_violation"],
    (active, incomplete): ["no_passed_artifacts"],
    (blocked, active): ["dependency_satisfied", "constraint_resolved"],
    (pending, failed): ["creation_failed"],
    (active, failed): ["execution_failed"]
}

Guards = {
    "all_children_done": lambda g: all(c.status == "done" for c in g.children),
    "manual_approval": lambda g: g.completion_mode == "manual" and has_approval(g),
    "no_passed_artifacts": lambda g: g.is_atomic and not any(a.verification_status == "passed" for a in g.artifacts)
}

Invariant(g):
    if g.goal_type == "continuous":
        assert g.status != "done"
    if g.is_atomic:
        assert g.status != "done" or has_passed_artifacts(g)
    if g.depth_level > 0:
        assert g.parent_id is not None
```

---

**Document Version:** 1.0
**Last Updated:** 2026-03-09
**Author:** AI-OS Architecture Analysis
