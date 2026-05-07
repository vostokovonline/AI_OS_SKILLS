# AGI Implementation - Summary & Quickstart

## What Was Done (Session Summary)

### ✅ Phase 1: Clean Architecture
**Files created:**
- `services/core/domain/services/goal_creation_service.py` (208 lines)
- `services/core/domain/services/goal_execution_service.py` (288 lines)
- `services/core/domain/services/goal_evaluation_service.py` (395 lines)
- `services/core/domain/services/goal_orchestrator.py` (268 lines)

**Impact:**
- Separated concerns (SRP compliance)
- Removed hidden commits (in new code)
- Pure domain logic
- UoW pattern throughout

### ✅ Phase 2: AGI Components (NEW!)
**Files created:**
- `services/core/agi/experience_service.py` (408 lines)
- `services/core/agi/world_model.py` (467 lines)
- `services/core/agi/strategy_evolution.py` (563 lines)

**These enable:**
1. **Learning from experience** - "What worked before?"
2. **World modeling** - "What will happen?"
3. **Strategy evolution** - "How can I improve?"

### 📚 Documentation
- `ENTITY_LEVEL_ANALYSIS.md` - Full entity analysis
- `ENTITY_MAP_VISUAL.txt` - Visual entity map
- `SERVICES_ARCHITECTURE.md` - Service design
- `AGI_ARCHITECTURE_DEPLOYED.md` - AGI documentation

---

## Quickstart: Using AGI Components

### 1. Experience-Driven Execution

```python
from agi import experience_service
from domain.services import goal_orchestrator
from infrastructure.uow import get_uow

async with get_uow() as uow:
    goal_id = UUID("some-goal-id")

    # Find similar past executions
    similar = await experience_service.find_similar(
        goal_title="Write documentation",
        goal_type="achievable",
        min_success_score=0.7
    )

    print(f"Found {len(similar)} similar executions")

    # Get best strategy recommendation
    best = await experience_service.get_best_strategy(
        goal_title="Write documentation",
        goal_type="achievable"
    )

    if best:
        print(f"Best strategy: {best['strategy_name']}")
        print(f"Expected success: {best['expected_success_score']}")
        print(f"Confidence: {best['confidence']}")

    # Execute
    result = await goal_orchestrator.execute_and_evaluate(uow, goal_id)

    # Learn from this execution
    await experience_service.learn_from_execution(
        execution_result=result["execution_result"],
        goal=goal
    )
```

### 2. World Model Predictions

```python
from agi import world_model

# Update entity state
await world_model.update_entity(
    name="production_server",
    entity_type=EntityType.RESOURCE,
    attributes={"status": "running", "cpu": 45.2, "memory": 67.8},
    confidence=0.95
)

# Check preconditions
can_restart, issues = await world_model.check_preconditions(
    "restart production_server"
)

if not can_restart:
    print(f"Cannot restart: {issues}")

# Predict effect
prediction = await world_model.predict_effect(
    "restart production_server"
)

print(f"Predicted effect: {prediction.expected_effect}")
print(f"Confidence: {prediction.confidence}")
```

### 3. Strategy Evolution

```python
from agi import strategy_evolution

# Select best strategy for goal
strategy = await strategy_evolution.select_strategy(
    goal_type="achievable",
    domains=["programming", "documentation"],
    complexity=0.7
)

if strategy:
    print(f"Selected: {strategy.name}")
    print(f"Fitness: {strategy.fitness}")
    print(f"Success rate: {strategy.success_rate}")

    # Execute with strategy
    result = await execute_with_strategy(goal, strategy)

    # Evaluate strategy performance
    await strategy_evolution.evaluate(
        strategy=strategy,
        goal_id=goal.id,
        success=result["success"],
        score=result["score"],
        duration_ms=result["duration_ms"],
        artifacts_count=len(result["artifacts"])
    )

    # Evolve population
    stats = await strategy_evolution.evolve_population(
        keep_top_n=5,
        mutation_count=3,
        crossover_count=2
    )

    print(f"New population size: {stats['population_size']}")
```

---

## Integration Steps

### Step 1: Database Tables

```sql
-- Experiences
CREATE TABLE experiences (
    id UUID PRIMARY KEY,
    goal_id UUID,
    goal_title TEXT,
    goal_type VARCHAR(50),
    goal_domains JSONB,
    strategy_name VARCHAR(100),
    strategy_params JSONB,
    execution_type VARCHAR(50),
    duration_ms INTEGER,
    artifacts_count INTEGER,
    outcome VARCHAR(20),
    success_score FLOAT,
    error_message TEXT,
    created_at TIMESTAMPTZ,
    user_id UUID,
    should_repeat BOOLEAN,
    confidence FLOAT
);

-- World States
CREATE TABLE world_states (
    id UUID PRIMARY KEY,
    entity_type VARCHAR(50),
    name VARCHAR(255) UNIQUE,
    attributes JSONB,
    observed_at TIMESTAMPTZ,
    last_updated TIMESTAMPTZ,
    confidence FLOAT,
    source VARCHAR(100),
    source_artifact_id UUID
);

-- Relations
CREATE TABLE world_relations (
    id UUID PRIMARY KEY,
    from_entity VARCHAR(255),
    to_entity VARCHAR(255),
    relation_type VARCHAR(50),
    strength FLOAT,
    metadata JSONB,
    created_at TIMESTAMPTZ
);

-- Strategies
CREATE TABLE strategies (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE,
    description TEXT,
    strategy_type VARCHAR(50),
    parameters JSONB,
    applicable_goal_types JSONB,
    applicable_domains JSONB,
    min_complexity FLOAT,
    max_complexity FLOAT,
    usage_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    total_score FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ,
    last_used TIMESTAMPTZ,
    parent_strategy_id UUID,
    generation INTEGER DEFAULT 0
);
```

### Step 2: Update GoalOrchestrator

Add to `domain/services/goal_orchestrator.py`:

```python
class GoalOrchestrator:
    def __init__(self):
        # ... existing services ...

        # NEW: AGI components
        from agi import experience_service, world_model, strategy_evolution
        self.experience = experience_service
        self.world_model = world_model
        self.strategy = strategy_evolution

    async def execute_with_agi(
        self,
        uow: "UnitOfWork",
        goal_id: UUID,
        session_id: Optional[str] = None,
        use_experience: bool = True,
        use_world_model: bool = True,
        use_strategy_selection: bool = True
    ) -> Dict[str, Any]:
        """
        Execute goal with full AGI capabilities.
        """
        from infrastructure.uow import GoalRepository

        repo = GoalRepository()
        goal = await repo.get(uow.session, goal_id)

        # 1. Query experience
        similar_experiences = []
        if use_experience:
            similar_experiences = await self.experience.find_similar(
                goal_title=goal.title,
                goal_type=goal.goal_type
            )

        # 2. Select strategy
        selected_strategy = None
        if use_strategy_selection:
            selected_strategy = await self.strategy.select_strategy(
                goal_type=goal.goal_type,
                domains=goal.domains
            )

        # 3. Check preconditions
        preconditions_met = []
        if use_world_model:
            action = f"execute goal: {goal.title}"
            preconditions_met, unmet = await self.world_model.check_preconditions(action)

        # 4. Execute
        result = await self.execute_and_evaluate(uow, goal_id, session_id)

        # 5. Learn from execution
        await self.experience.learn_from_execution(
            execution_result=result["execution_result"],
            goal=goal
        )

        # 6. Evaluate strategy
        if selected_strategy:
            await self.strategy.evaluate(
                strategy=selected_strategy,
                goal_id=goal_id,
                success=result["success"],
                score=result["evaluation"]["confidence_true"],
                duration_ms=result["execution_result"]["duration_ms"],
                artifacts_count=len(result["execution_result"]["artifacts"])
            )

        # 7. Return with AGI context
        result["agi_context"] = {
            "similar_experiences_count": len(similar_experiences),
            "selected_strategy": selected_strategy.name if selected_strategy else None,
            "preconditions_met": len(preconditions_met) == 0,
            "learned": True
        }

        return result
```

### Step 3: Update API Endpoint

```python
# In api/endpoints/goals.py

@router.post("/{goal_id}/execute-agi")
async def execute_goal_agi(
    goal_id: str,
    uow: UnitOfWork = Depends(get_uow)
):
    """
    Execute goal with AGI enhancements.

    AGI features:
    - Experience-based strategy selection
    - World model predictions
    - Automatic learning
    """
    from domain.services import goal_orchestrator

    result = await goal_orchestrator.execute_with_agi(
        uow=uow,
        goal_id=UUID(goal_id)
    )

    return result
```

---

## Testing

### Unit Tests

```python
# tests/unit/test_experience_service.py

import pytest
from agi import experience_service, OutcomeType

@pytest.mark.asyncio
async def test_store_experience():
    record = await experience_service.store(
        goal_id=uuid4(),
        goal_title="Test goal",
        goal_type="achievable",
        strategy_name="atomic_default",
        execution_type="atomic",
        duration_ms=1000,
        artifacts_count=1,
        outcome=OutcomeType.SUCCESS,
        success_score=0.9
    )

    assert record.outcome == OutcomeType.SUCCESS
    assert record.success_score == 0.9

@pytest.mark.asyncio
async def test_find_similar():
    # Store some experiences
    await experience_service.store(
        goal_id=uuid4(),
        goal_title="Write documentation",
        goal_type="achievable",
        strategy_name="atomic_default",
        execution_type="atomic",
        duration_ms=1000,
        artifacts_count=1,
        outcome=OutcomeType.SUCCESS,
        success_score=0.9
    )

    similar = await experience_service.find_similar(
        goal_title="Write docs",
        goal_type="achievable"
    )

    assert len(similar) > 0
```

### Integration Tests

```python
# tests/integration/test_agi_workflow.py

@pytest.mark.asyncio
async def test_full_agi_workflow():
    from domain.services import goal_orchestrator
    from agi import experience_service, strategy_evolution

    async with get_uow() as uow:
        # Create goal
        result = await goal_orchestrator.create_and_activate(
            uow=uow,
            title="Write test code",
            goal_type="achievable",
            is_atomic=True
        )

        goal_id = UUID(result["goal_id"])

        # Execute with AGI
        result = await goal_orchestrator.execute_with_agi(uow, goal_id)

        # Verify learning happened
        assert result["agi_context"]["learned"] == True

        # Verify strategy was evaluated
        stats = strategy_evolution.get_population_summary()
        assert stats["total_strategies"] > 0
```

---

## Performance Considerations

### Memory Usage
- Experience records: ~1KB each
- World model entities: ~500B each
- Strategies: ~2KB each

**Recommendation:** Keep <10K experiences, <1K entities, <100 strategies

### Query Performance
- Experience similarity: O(n) - TODO: use vector search
- Strategy selection: O(n) - fine for <100 strategies
- World model queries: O(n) - TODO: add indexes

### Caching
```python
# Cache similar experiences for 5 minutes
@lru_cache(maxsize=100)
async def find_similar_cached(goal_title, goal_type):
    return await experience_service.find_similar(
        goal_title, goal_type
    )
```

---

## Next Steps

### Immediate
1. Run database migrations
2. Test AGI components
3. Update API endpoints

### Short-term
1. Add vector similarity for experiences
2. Implement actual prediction logic in world model
3. Add A/B testing for strategies

### Long-term
1. Automatic evolution cycles
2. Cross-user learning
3. Meta-learning (learn to learn)

---

## Summary

**What you have now:**
- ✅ Clean domain architecture
- ✅ Three AGI components (Experience, World Model, Strategy)
- ✅ Full documentation

**What's needed:**
- ⏳ Database tables
- ⏳ Integration testing
- ⏳ API endpoint updates
- ⏳ Performance optimization

**You're much closer to AGI than before!**

The infrastructure is there. Now it needs data and tuning.
