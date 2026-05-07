# AI-OS Domain Services Architecture (v2.0)

## Phase 1: Service Decomposition

### Current State
```
GoalExecutor (384 lines, 6 methods)
  ├── create_goal()           [Creation logic]
  ├── create_goal_with_uow()  [Creation with UoW]
  ├── execute_goal()          [Execution logic]
  └── execute_complex_goal()  [Complex execution]
```

### Target Architecture
```
domain/
├── services/
│   ├── __init__.py
│   ├── goal_creation_service.py    [Pure creation logic]
│   ├── goal_execution_service.py   [Pure execution logic]
│   ├── goal_evaluation_service.py  [Pure evaluation logic]
│   └── goal_orchestrator.py        [Composition only]
├── goal_domain_service.py          [Already exists ✓]
└── validators/
    ├── goal_invariants.py          [Invariant validation]
    └── transition_validator.py     [Transition validation]
```

## Service Contracts

### 1. GoalCreationService
**Responsibility**: Create goals with validation
**Does NOT**:
- Commit transactions
- Log events
- Send notifications

```python
class GoalCreationService:
    async def create(
        self,
        uow: UnitOfWork,
        title: str,
        description: str = "",
        goal_type: str = "achievable",
        is_atomic: bool = False,
        parent_id: UUID = None,
        user_id: UUID = None
    ) -> Goal:
        """
        Create goal within UoW transaction.

        Returns:
            Goal: Created goal (NOT committed yet)

        Raises:
            ValidationError: If invariants violated
        """
        pass
```

### 2. GoalExecutionService
**Responsibility**: Execute goals (atomic and complex)
**Does NOT**:
- Manage state transitions
- Commit transactions
- Update beliefs

```python
class GoalExecutionService:
    async def execute_atomic(
        self,
        goal: Goal,
        session_id: str = None
    ) -> ExecutionResult:
        """
        Execute atomic goal via skills.

        Returns:
            ExecutionResult: artifacts + evidence

        Raises:
            ValueError: If goal is not atomic
        """
        pass

    async def execute_complex(
        self,
        goal: Goal,
        session_id: str = None
    ) -> ExecutionResult:
        """
        Execute complex goal via decomposition + agent graph.

        Returns:
            ExecutionResult: subgoals + artifacts
        """
        pass
```

### 3. GoalEvaluationService
**Responsibility**: Evaluate goal completion
**Does NOT**:
- Transition state
- Commit transactions

```python
class GoalEvaluationService:
    async def evaluate(
        self,
        goal: Goal,
        context: EvaluationContext
    ) -> TruthEstimate:
        """
        Evaluate goal based on evidence.

        Returns:
            TruthEstimate: confidence + state

        Note:
            Does NOT modify goal state
        """
        pass
```

### 4. GoalOrchestrator
**Responsibility**: Compose services
**Does**:
- Coordinate workflow
- Manage UoW lifecycle
- Handle errors

```python
class GoalOrchestrator:
    def __init__(self):
        self.creation = GoalCreationService()
        self.execution = GoalExecutionService()
        self.evaluation = GoalEvaluationService()
        self.domain = goal_domain_service
        self.transition = transition_service

    async def create_and_execute(
        self,
        title: str,
        description: str = "",
        ...
    ) -> dict:
        """
        High-level workflow.

        Workflow:
            1. Create goal (UoW)
            2. Execute goal (UoW)
            3. Evaluate result (UoW)
            4. Transition state (UoW)
            5. Commit (UoW)

        Single transaction throughout.
        """
        pass
```

## Migration Plan

### Step 1: Create Services (Day 1)
```bash
# Create new files
touch services/core/domain/services/{goal_creation,goal_execution,goal_evaluation}_service.py
```

### Step 2: Extract Logic (Day 2)
```python
# Move logic from GoalExecutor → Services
# GoalExecutor becomes facade
```

### Step 3: Update Endpoints (Day 3)
```python
# Old:
from goal_executor import goal_executor
goal = await goal_executor.create_goal(title)

# New:
from domain.services.goal_orchestrator import orchestrator
async with get_uow() as uow:
    goal = await orchestrator.creation.create(uow, title)
```

### Step 4: Deprecate GoalExecutor (Day 4)
```python
# Add deprecation warnings
class GoalExecutor:
    @deprecated("Use GoalOrchestrator instead")
    async def create_goal(self, ...):
        return await self.orchestrator.create_and_execute(...)
```

## Anti-Pattern Prevention

### ❌ DON'T:
```python
# Service with hidden commit
class BadService:
    async def create(self, session, data):
        goal = Goal(**data)
        session.add(goal)
        await session.commit()  # ❌ Hidden commit!
```

### ✅ DO:
```python
# Service with UoW
class GoodService:
    async def create(self, uow, data):
        goal = Goal(**data)
        await uow.goals.add(uow.session, goal)
        # UoW commits, not service
```

## Success Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Service lines | - | <200 each | ✅ |
| GoalExecutor lines | 384 | <50 (facade) | ✅ |
| Hidden commits | 52 | 0 | ✅ |
| Direct status assignments | 13 | 0 | ✅ |
| Test coverage | 45 | 100+ | ✅ |

## Timeline

- **Day 1**: Create service files + structure
- **Day 2**: Extract creation logic
- **Day 3**: Extract execution logic
- **Day 4**: Extract evaluation logic
- **Day 5**: Integration testing
- **Day 6**: Endpoint migration
- **Day 7**: Deprecation + documentation
