# PHASE 1 COMPLETION PLAN — Stabilized Execution Engine

**Current Status**: V3 working, skill selection working, LLM working
**Target**: Complete execution tracking & skill metrics

---

## 1️⃣ EXECUTION TABLE (Critical)

### Schema
```sql
CREATE TABLE executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    skill_id VARCHAR(255) NOT NULL,
    execution_engine VARCHAR(50),  -- 'v3' or 'legacy'

    -- Timing
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,

    -- Outcome
    success BOOLEAN NOT NULL,
    confidence FLOAT,
    artifacts_count INTEGER DEFAULT 0,

    -- Error tracking
    error_message TEXT,
    error_type VARCHAR(255),

    -- V3 specific
    v3_locked_at TIMESTAMP WITH TIME ZONE,
    v3_lock_acquired BOOLEAN DEFAULT false,

    -- Metadata
    goal_snapshot JSONB,  -- goal state at execution time
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    INDEX idx_executions_goal_id (goal_id),
    INDEX idx_executions_skill_id (skill_id),
    INDEX idx_executions_success (success),
    INDEX idx_executions_timestamp (started_at)
);
```

### Integration Points

**goal_executor_v2.py** (atomic goal execution):
```python
async def execute_goal_with_uow(uow, goal_id, session_id):
    execution_rec = ExecutionRecord(
        goal_id=goal_id,
        skill_id=selected_skill.name,
        execution_engine='v3' if is_v3 else 'legacy',
        started_at=datetime.utcnow()
    )

    try:
        result = await skill.execute(inputs, context)

        execution_rec.completed_at = datetime.utcnow()
        execution_rec.duration_ms = calculate_duration(started_at, completed_at)
        execution_rec.success = result.success
        execution_rec.confidence = result.confidence
        execution_rec.artifacts_count = len(result.artifacts)

    except Exception as e:
        execution_rec.success = False
        execution_rec.error_message = str(e)
        execution_rec.error_type = type(e).__name__
        raise

    finally:
        await uow.executions.add(execution_rec)
```

---

## 2️⃣ SKILL PERFORMANCE METRICS (Critical)

### Schema
```sql
CREATE TABLE skill_stats (
    skill_id VARCHAR(255) PRIMARY KEY,

    -- Execution counts
    total_executions INTEGER DEFAULT 0,
    successful_executions INTEGER DEFAULT 0,
    failed_executions INTEGER DEFAULT 0,

    -- Performance metrics
    avg_latency_ms FLOAT,
    p50_latency_ms FLOAT,
    p95_latency_ms FLOAT,
    p99_latency_ms FLOAT,

    -- Quality metrics
    avg_confidence FLOAT,
    avg_artifacts_count FLOAT,
    success_rate FLOAT,

    -- Last updated
    last_execution_at TIMESTAMP WITH TIME ZONE,
    last_calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Trend data (last 100 executions)
    recent_success_rate FLOAT,
    recent_avg_latency FLOAT
);
```

### Update Strategy

**After each execution**:
```python
async def update_skill_stats(uow, skill_id, execution):
    stats = await uow.skill_stats.get(skill_id)

    if not stats:
        stats = SkillStats(skill_id=skill_id)

    # Update counters
    stats.total_executions += 1
    if execution.success:
        stats.successful_executions += 1
    else:
        stats.failed_executions += 1

    # Update success rate
    stats.success_rate = stats.successful_executions / stats.total_executions

    # Update latency (moving average)
    if execution.duration_ms:
        old_avg = stats.avg_latency_ms or 0
        stats.avg_latency_ms = (old_avg * 0.9) + (execution.duration_ms * 0.1)

    stats.last_execution_at = execution.completed_at
    await uow.skill_stats.update(stats)
```

---

## 3️⃣ ENHANCED SKILL SELECTION

### Current Scoring
```python
score = capability_match + artifact_match - generic_penalty
```

### New Scoring (with stats)
```python
def _select_skill(self, requirements, goal_snapshot):
    """
    Select skill considering historical performance.
    """
    required_capabilities = requirements.get("capabilities", [])

    all_skills = skill_registry.list()
    scored_skills = []

    for skill in all_skills:
        # Get historical stats
        stats = await self._get_skill_stats(skill.name)

        # Base score from capabilities
        capability_score = self._score_capabilities(skill, required_capabilities)

        # Performance multiplier
        if stats and stats.total_executions >= 5:
            # High success rate = bonus
            if stats.success_rate > 0.9:
                performance_multiplier = 1.2
            elif stats.success_rate > 0.8:
                performance_multiplier = 1.0
            elif stats.success_rate > 0.7:
                performance_multiplier = 0.8
            else:
                performance_multiplier = 0.5  # Penalize unreliable skills

            # Latency penalty (slow skills)
            if stats.avg_latency_ms > 5000:
                latency_penalty = -3
            elif stats.avg_latency_ms > 3000:
                latency_penalty = -1
            else:
                latency_penalty = 0
        else:
            # New skills get neutral multiplier
            performance_multiplier = 1.0
            latency_penalty = 0

        # Final score
        final_score = (
            capability_score * performance_multiplier
            + latency_penalty
        )

        scored_skills.append((final_score, skill, stats))

    # Sort and select
    scored_skills.sort(key=lambda x: x[0], reverse=True)
    return scored_skills[0][1]
```

---

## 4️⃣ RETRY STRATEGY

### Skill Fallback Chain
```python
SKILL_FALLBACKS = {
    'core.web_research': [
        'core.llm_research',
        'core.echo'
    ],
    'core.write_file': [
        'core.llm_generate',
        'core.echo'
    ],
    'core.llm_research': [
        'core.echo'
    ]
}

async def execute_with_retry(uow, goal, primary_skill):
    """
    Execute skill with automatic fallback on failure.
    """
    skill_chain = [primary_skill] + SKILL_FALLBACKS.get(primary_skill.name, [])

    last_error = None

    for attempt, skill in enumerate(skill_chain, 1):
        execution_rec = ExecutionRecord(
            goal_id=goal.id,
            skill_id=skill.name,
            started_at=datetime.utcnow()
        )

        try:
            result = await skill.execute(inputs, context)

            execution_rec.success = True
            execution_rec.completed_at = datetime.utcnow()

            await uow.executions.add(execution_rec)
            await update_skill_stats(uow, skill.name, execution_rec)

            logger.info(
                "skill_execution_success",
                skill=skill.name,
                attempt=attempt,
                duration_ms=execution_rec.duration_ms
            )

            return result

        except Exception as e:
            last_error = e
            execution_rec.success = False
            execution_rec.error_message = str(e)
            execution_rec.error_type = type(e).__name__

            await uow.executions.add(execution_rec)
            await update_skill_stats(uow, skill.name, execution_rec)

            logger.warning(
                "skill_execution_failed_trying_next",
                skill=skill.name,
                attempt=attempt,
                next_skill=skill_chain[attempt].name if attempt < len(skill_chain) else None,
                error=str(e)
            )

    # All skills failed
    raise Exception(f"All skills failed. Last error: {last_error}")
```

---

## 5️⃣ ANALYTICS ENDPOINTS

### New API Routes
```python
@router.get "/analytics/execution-metrics"
async def get_execution_metrics(
    hours: int = 24,
    skill_id: Optional[str] = None
):
    """
    Get execution metrics for analytics.

    Returns:
    - Total executions
    - Success rate
    - Avg latency
    - P50/P95/P99
    - Skill breakdown
    """
    pass

@router.get "/analytics/skill-performance"
async def get_skill_performance():
    """
    Get all skill performance stats.

    Returns:
    - Skill rankings
    - Success rates
    - Latency percentiles
    - Trend data
    """
    pass

@router.get "/analytics/v3-vs-legacy"
async def compare_engines():
    """
    Compare V3 vs legacy performance.
    """
    pass
```

---

## 📊 IMPLEMENTATION ORDER

### Step 1: Database Schema (30 min)
1. Create migration for `executions` table
2. Create migration for `skill_stats` table
3. Add indexes
4. Run migration

### Step 2: Execution Tracking (1 hour)
1. Add `ExecutionRecord` model
2. Integrate into `goal_executor_v2.py`
3. Add to UnitOfWork
4. Test with synthetic goals

### Step 3: Skill Stats Update (1 hour)
1. Add `SkillStats` model
2. Add update logic after execution
3. Add background calculation job
4. Verify stats accuracy

### Step 4: Enhanced Selection (2 hours)
1. Fetch stats in selection
2. Add performance multiplier
3. Add latency penalty
4. Test scoring variance

### Step 5: Retry Strategy (1.5 hours)
1. Define fallback chains
2. Implement retry loop
3. Add tracking per attempt
4. Test failure scenarios

### Step 6: Analytics API (1 hour)
1. Add metrics endpoints
2. Add skill performance endpoint
3. Add V3 vs legacy comparison
4. Test dashboard integration

**Total Time**: ~7 hours of focused work

---

## ✅ SUCCESS CRITERIA FOR PHASE 1

- [ ] Every execution tracked in `executions` table
- [ ] Skill stats updated after each execution
- [ ] Selection considers historical performance
- [ ] Failed skills automatically retry with fallback
- [ ] Analytics endpoints return real metrics
- [ ] Dashboard shows execution trends
- [ ] V3 vs legacy comparison available

---

## 🚀 NEXT PHASE (Phase 2)

After Phase 1 is complete:
1. Build Experience Layer (experiences table)
2. Pattern extraction from executions
3. Similarity search for goal→skill matching

**PHASE 1 IS THE FOUNDATION. WITHOUT IT, PHASE 2+ WILL FAIL.**
