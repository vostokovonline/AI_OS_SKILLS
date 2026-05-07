# AI_OS Goal System v3.0 - Summary

## Overview
Implemented advanced meta-evaluation features based on v3.0 specification:
- **Goal Contracts** - Formalized LLM behavior constraints
- **Evaluation/Reflection Split** - Strict evaluator vs causal reflector
- **Goal Mutation** - Strengthen/weaken/change_type/freeze operations
- **Semantic Memory** - Decision pattern extraction (Memory ≠ Logs)

## 1. Goal Contracts (Контракты целей)

### Purpose
Formalized constraints on LLM behavior for goal execution to prevent:
- Infinite loops
- Excessive decomposition
- Unauthorized actions
- Resource waste

### Implementation
**File**: `goal_contract_validator.py`

**Fields in Goal Model**:
```python
goal_contract = Column(JSON, nullable=True)
# {
#   "allowed_actions": ["decompose", "spawn_subgoal", "execute"],
#   "forbidden": ["spawn_meta_goal", "external_execution"],
#   "max_depth": 3,
#   "max_subgoals": 7,
#   "evaluation_mode": "binary|scalar|trend",
#   "timeout_seconds": 300,
#   "resource_limits": {"max_tokens": 100000, "max_api_calls": 50}
# }
```

**Default Contracts by Goal Type**:
- **achievable**: Can decompose, execute, evaluate; max_depth=3, max_subgoals=7
- **continuous**: Only execute + evaluate; max_depth=0 (no decomposition)
- **directional**: Only spawn_subgoal; max_depth=1; no execution/evaluation
- **exploratory**: Can decompose, execute, evaluate; max_depth=2, max_subgoals=5
- **meta**: Can decompose, mutate, evaluate; NO external execution

**Key Methods**:
- `can_execute_action(goal, action)` - Check if action is allowed
- `check_depth_limit(goal, current_depth)` - Prevent infinite decomposition
- `check_subgoals_limit(goal, count)` - Prevent exponential growth
- `get_evaluation_mode(goal)` - Return binary/scalar/trend

**Integration**:
- `goal_decomposer.py` - Checks contract before decomposition
- `goal_executor.py` - Checks contract before execution
- Auto-applied to all new goals and subgoals

## 2. Strict Evaluator (Строгий оценщик)

### Purpose
Checks ONLY the fact of goal completion, without reasoning

**File**: `goal_strict_evaluator.py`

**Evaluation Modes**:

#### Binary Mode
For achievable goals with clear success criteria
```json
{
  "passed": true/false,
  "confidence": 0.0-1.0,
  "evidence": ["Fact 1", "Fact 2"]
}
```

#### Scalar Mode
For meta, directional goals
```json
{
  "score": 0.0-1.0,
  "evidence": ["Fact 1"],
  "gaps": ["Missing"]
}
```

#### Trend Mode
For continuous goals
```json
{
  "trend": "improving|stable|degrading",
  "score": 0.0-1.0,
  "evidence": ["Fact 1"]
}
```

**Key Methods**:
- `evaluate_goal(goal_id)` - Main entry point
- `_evaluate_binary(goal)` - Binary completion check
- `_evaluate_scalar(goal)` - Degree of completion
- `_evaluate_trend(goal)` - Trend analysis for continuous goals

## 3. Goal Reflector (Рефлектор)

### Purpose
Analyzes WHY and WHAT NEXT - causal reasoning and next goal generation

**File**: `goal_reflector.py`

**Reflection Types**:

#### On Success
Extracts success factors and patterns:
```json
{
  "why": "Why it succeeded",
  "success_factors": ["Factor 1"],
  "lessons_learned": ["Lesson 1"],
  "patterns": ["Pattern 1"],
  "next_goals": [{...}],
  "action": "complete"
}
```

#### On Failure
Analyzes root causes and generates improvement goals:
```json
{
  "why": "Why it failed",
  "root_causes": ["Cause 1"],
  "mistakes": ["Mistake 1"],
  "missing_resources": ["Resource 1"],
  "improvement_goals": [{...}],
  "action": "continue|adjust"
}
```

#### On Degradation
For continuous goals with degrading trend:
```json
{
  "why": "Goal degraded",
  "action": "mutate",
  "mutation_suggestion": {
    "type": "weaken",
    "reason": "Simplify to restore trend"
  }
}
```

**Key Methods**:
- `reflect_on_goal(goal_id, strict_evaluation)` - Main entry
- `_reflect_on_success(goal, score)` - Success analysis
- `_reflect_on_failure(goal, score)` - Failure analysis
- `_generate_next_goal(completed_goal, reflection)` - Next Goal Generator

## 4. Goal Mutation (Мутация целей)

### Purpose
Modify goals in runtime to adapt to changing conditions

**File**: `goal_mutator.py`

**Mutation Types**:

#### Strengthen (🔺)
Raise success criteria:
- Add more domains
- Tighten completion_criteria
- Add constraints
- Example: scalar 0.7 → 0.9

#### Weaken (🔻)
Simplify criteria:
- Remove domains
- Relax completion_criteria
- Remove constraints
- Example: unreachable → achievable

#### Change Type (🔄)
Change goal_type:
- directional → continuous
- achievable → exploratory
- Auto-updates goal_contract

#### Freeze (❄️)
Temporarily pause goal:
- Sets mutation_status = "frozen"
- Blocks all actions
- Status: active → pending

#### Thaw (🔥)
Resume frozen goal:
- Sets mutation_status = "active"
- Restores previous status

**Key Methods**:
- `mutate_goal(goal_id, mutation_type, reason, **params)`
- `_strengthen_goal(goal, reason)`
- `_weaken_goal(goal, reason)`
- `_change_goal_type(goal, reason, new_type)`
- `_freeze_goal(goal, reason)`
- `_thaw_goal(goal, reason)`

**Mutation History**:
```python
mutation_history = [
  {"type": "strengthen", "reason": "...", "timestamp": "..."},
  {"type": "change_type", "from_type": "achievable", "to_type": "continuous"}
]
mutation_status = "active|frozen|mutated|deprecated"
```

## 5. Semantic Memory (Семантическая память)

### Purpose
Extract and store decision patterns (Memory ≠ Logs)

**File**: `semantic_memory.py`

**Pattern Types**:

#### Success Patterns
What worked:
```json
{
  "pattern_type": "success",
  "goal_type": "achievable",
  "domains": ["programming", "infrastructure"],
  "success_factors": ["Factor 1"],
  "lessons_learned": ["Lesson 1"],
  "patterns": ["Pattern 1"]
}
```

#### Failure Patterns
What didn't work and why:
```json
{
  "pattern_type": "failure",
  "goal_type": "achievable",
  "root_causes": ["Cause 1"],
  "mistakes": ["Mistake 1"],
  "missing_resources": ["Resource 1"]
}
```

#### Decomposition Patterns
Which decomposition patterns worked:
```json
{
  "pattern_type": "decomposition",
  "parent_goal_type": "achievable",
  "subgoals_count": 5,
  "subgoals_types": ["achievable", "achievable", ...],
  "subgoals_domains": ["domain1", "domain2"],
  "depth_distribution": [1, 2, 2, 2, 3]
}
```

#### Agent Effectiveness
Which agent + model combos work:
```json
{
  "pattern_type": "agent_effectiveness",
  "agent_role": "Coder",
  "model_name": "gpt-4",
  "task_type": "refactoring",
  "success": true,
  "duration_ms": 1500,
  "context": {"domains": ["programming"], "goal_type": "achievable"}
}
```

**Key Methods**:
- `store_pattern(pattern_type, content, source_goal_id, confidence)`
- `extract_success_pattern(goal_id, reflection)`
- `extract_failure_pattern(goal_id, reflection)`
- `extract_decomposition_pattern(parent_goal, subgoals)`
- `track_agent_effectiveness(agent_role, model_name, task_type, success, duration_ms, context)`
- `retrieve_similar_patterns(pattern_type, goal_type, domains, limit)`
- `get_recommendations(goal, task_type)` - Returns actionable insights

**Storage**: Uses existing `Thought` model with `category="pattern"`

## 6. Database Migration

**File**: `migrations/add_goal_contracts.sql`

Applied successfully:
```sql
ALTER TABLE goals ADD COLUMN goal_contract JSONB;
ALTER TABLE goals ADD COLUMN mutation_history JSONB;
ALTER TABLE goals ADD COLUMN mutation_status VARCHAR(50) DEFAULT 'active';
CREATE INDEX idx_goals_mutation_status ON goals(mutation_status);
```

## 7. API Endpoints

### Existing (v2.0)
- `POST /goals/create` - Create goal with auto-classification
- `POST /goals/classify` - Classify goal
- `POST /goals/{goal_id}/decompose` - Decompose goal
- `POST /goals/{goal_id}/evaluate` - Full evaluation (legacy)
- `GET /goals/{goal_id}/tree` - Get goal tree
- `GET /goals/stats` - Get statistics

### New (v3.0)
- `POST /goals/{goal_id}/mutate` - Mutate goal (strengthen/weaken/change/freeze)
- `POST /goals/{goal_id}/strict_evaluate` - Strict evaluation only
- `POST /goals/{goal_id}/reflect` - Reflect on evaluation result
- `GET /goals/{goal_id}/patterns` - Get recommendations from semantic memory
- `GET /patterns/retrieve` - Retrieve patterns from memory
- `POST /goals/{goal_id}/extract_patterns` - Extract patterns from completed goal

## 8. Workflow Examples

### Complete Goal Execution with v3.0
```python
# 1. Create goal (auto-assigns default contract)
POST /goals/create
{
  "title": "Implement feature X",
  "description": "..."
}
# → goal_contract auto-created based on goal_type

# 2. Decompose (checks contract: allowed_actions, max_depth, max_subgoals)
POST /goals/{id}/decompose

# 3. Execute (checks contract: can_execute_action("execute"))
POST /goals/{id}/execute

# 4. Strict evaluation (checks contract: evaluation_mode)
POST /goals/{id}/strict_evaluate
# → Returns: {passed: true, score: 0.8, evaluation_mode: "scalar"}

# 5. Reflect (analyzes why and what next)
POST /goals/{id}/reflect
{
  "strict_evaluation": {...}
}
# → Returns: {why: "...", lessons_learned: [...], next_goals: [...]}

# 6. Extract patterns to semantic memory
POST /goals/{id}/extract_patterns
{
  "reflection": {...}
}
# → Stores success/failure patterns for future use

# 7. Get recommendations for similar goal
GET /goals/{new_id}/patterns
# → Returns: {success_factors: [...], pitfalls: [...], effective_agents: [...]}
```

### Goal Mutation Example
```python
# Goal is stuck, need to simplify
POST /goals/{id}/mutate
{
  "mutation_type": "weaken",
  "reason": "Goal is too complex, need to simplify",
  "new_title": "Simplified goal"
}
# → LLM generates simplified version
# → Updates: title, completion_criteria, removes constraints
# → Appends to mutation_history
```

### Semantic Memory Example
```python
# Agent executed task, track effectiveness
semantic_memory.track_agent_effectiveness(
  agent_role="Coder",
  model_name="gpt-4",
  task_type="refactoring",
  success=True,
  duration_ms=1500,
  context={"domains": ["programming"], "goal_id": "..."}
)

# Later: Get recommendations for similar task
GET /goals/{goal_id}/patterns
# → Returns:
# {
#   "success_factors": ["Use gpt-4 for refactoring"],
#   "pitfalls": ["Don't use gpt-3.5 for complex code"],
#   "effective_agents": [
#     {"agent": "Coder", "model": "gpt-4", "success_rate": "high"}
#   ]
# }
```

## 9. Files Created/Modified

### New Files (v3.0)
- `goal_contract_validator.py` - Contract validation system
- `goal_strict_evaluator.py` - Strict binary/scalar/trend evaluation
- `goal_reflector.py` - Causal reflection and next goal generation
- `goal_mutator.py` - Goal mutation operations
- `semantic_memory.py` - Decision pattern extraction
- `migrations/add_goal_contracts.sql` - Database migration

### Modified Files
- `models.py` - Added goal_contract, mutation_history, mutation_status fields
- `goal_decomposer.py` - Integrated contract checks, auto-assigns contracts to subgoals
- `goal_executor.py` - Integrated contract checks, auto-assigns contracts to new goals
- `main.py` - Added v3.0 API endpoints

## 10. Next Steps (Optional)

1. **Dashboard Integration** - Add v3.0 controls to dashboard:
   - Mutation buttons (strengthen/weaken/change/freeze)
   - Separate evaluate/reflect actions
   - Pattern viewer
   - Contract editor

2. **Pattern Visualization** - Show learned patterns in dashboard

3. **Auto-Mutation** - System can suggest mutations based on semantic memory

4. **Contract Learning** - System learns optimal contracts from execution history

## Conclusion

AI_OS Goal System v3.0 is now fully implemented with:
- ✅ Goal Contracts - Formalized behavior constraints
- ✅ Strict Evaluator - Fact-based evaluation (binary/scalar/trend)
- ✅ Reflector - Causal analysis and next goal generation
- ✅ Goal Mutation - Runtime goal modification
- ✅ Semantic Memory - Decision pattern extraction (Memory ≠ Logs)

All database migrations applied successfully. System ready for production use.
