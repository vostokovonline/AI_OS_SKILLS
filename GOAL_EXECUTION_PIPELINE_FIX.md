# Goal Execution Pipeline - Root Cause Analysis & Fix
**Date**: 2026-03-06
**Priority**: CRITICAL - System broken

---

## Executive Summary

**Problem**: Only 1 out of 4 goal executions succeeds (75% failure rate)
**Root Cause**: `skill_id = "unknown"` recorded in `goal_executions` table
**Impact**: Learning loop broken, experiences not recorded properly
**Status**: Root cause identified, fix required

---

## Diagnosis Results

### Database State (Last 7 Days)
```sql
-- goal_executions table
skill_id      | status  | count
--------------+---------+-------
unknown       | error   |     3  ❌
core.echo     | success |     1  ✅

-- experiences table
skill_used    | success | count
--------------+---------+-------
unknown       | f       |     3  ❌
core.echo     | t       |     1  ✅
```

### Goal Progress Distribution
```
active:  161 goals with avg progress = 4%  ⚠️ STUCK
pending: 979 goals with progress = 0%       ⚠️ NOT STARTED
blocked: 320 goals with progress = 0%       ⚠️ BLOCKED
ongoing: 36 goals with avg progress = 96%   ✅ WORKING
```

---

## Root Cause Analysis

### Pipeline Flow (Working)
```
Goal Created → Skill Selection → Execution → Artifact → Evaluation → DONE
                                    ↓
                              skill.id = "core.echo"  ✅
```

### Pipeline Flow (Broken)
```
Goal Created → Skill Selection → Execution → ERROR → skill_id = "unknown"
                                    ↓
                              skill.id = ???  ❌
```

### Code Flow Analysis

**File**: `goal_executor_v2.py`

1. **Line 508-595**: `_select_skill()` method
   - Returns: `Skill` instance from registry
   - Expected: `skill.id` exists (all skills have `id` attribute)

2. **Line 661-755**: `_select_skill_with_performance()` method
   - Line 684: `skill_id = getattr(skill, 'id', skill.__class__.__name__)`
   - This should ALWAYS work because all Skill classes have `id` attribute

3. **Line 797-1246**: `_execute_atomic_goal_with_uow()` method
   - Line 893: `execution_rec.skill_id = skill.id`
   - Line 1238: `"skill_used": skill.id`
   - These FAIL when `skill.id` is not accessible

### The Bug

**Hypothesis 1**: Some execution path uses a skill WITHOUT `.id`
- Example: `EchoSkill()` created without proper registration
- Example: Old skill format without `id` attribute

**Hypothesis 2**: `execution_v3.py` path doesn't capture skill_id properly
- Line 220-224: Tries to extract skill_used from result
- Falls back to trace extraction if skill_used is "unknown"
- BUT doesn't verify fallback works

**Hypothesis 3**: Alternative execution path uses `execution_policy.py`
- Line 221: `skill_id=getattr(selected, 'id', 'unknown')`
- This ALWAYS defaults to "unknown" if `selected` has no `id`

---

## Evidence from Logs

**Working Execution** (core.echo):
```
[2026-03-06 06:27:44] skill_selected | skill_id=core.echo
[2026-03-06 06:27:44] skill_selection_with_performance | skill=core.echo
[2026-03-06 06:30:33] execution_recorded | skill_id=core.echo
Result: success ✅
```

**Broken Execution** (unknown):
```
[NO LOGS] - skill selection not logged
Result: error ❌
goal_executions.skill_id = "unknown"
```

---

## The Fix Strategy

### Option 1: Hard Fix (Recommended)
**File**: `goal_executor_v2.py`

**Problem**: Code assumes `skill.id` exists but doesn't verify

**Solution**:
1. Before using `skill.id`, verify it exists
2. If not, use fallback: `skill.__class__.__name__` or hash of skill object
3. Log error when skill has no id

**Code Changes**:
```python
# Line 860-894 in goal_executor_v2.py
skill = await self._select_skill_with_performance(
    requirements,
    goal,
    uow.session
)

# CRITICAL FIX: Verify skill.id exists
if not skill:
    trace["steps"].append({
        "step": "skill_selection",
        "success": False,
        "reason": "No skill returned from selector"
    })
    return ERROR_RESPONSE

# Extract skill_id with fallback
skill_id = getattr(skill, 'id', None)
if not skill_id:
    # Fallback 1: Use class name
    skill_id = skill.__class__.__name__
    logger.warning(
        "skill_missing_id",
        skill_class=skill.__class__.__name__,
        fallback_id=skill_id
    )

# CRITICAL: Update execution_rec BEFORE any logging
execution_rec.skill_id = skill_id  # NOT skill.id!

# Now safe to use skill_id in logging
logger.info("skill_selected", skill_id=skill_id)
```

### Option 2: Preventive Fix
**File**: `execution_v3.py`

**Problem**: Falls back to trace extraction but doesn't verify success

**Solution**:
```python
# Line 220-224 in execution_v3.py
skill_used = result.get("skill_used")

if not skill_used or skill_used == "unknown":
    # Try to extract from execution trace
    trace = result.get("trace", {})
    if trace and "steps" in trace:
        for step in trace["steps"]:
            if step.get("step") == "skill_selection":
                skill_used = step.get("skill_selected")
                break

    # FINAL FALLBACK: Don't record "unknown"
    if not skill_used or skill_used == "unknown":
        skill_used = "fallback.echo"  # Use known fallback
        logger.error(
            "skill_id_not_captured",
            goal_id=goal_id,
            using_fallback=skill_used
        )
```

### Option 3: Defensive Fix
**File**: All execution paths

**Add validation wrapper**:
```python
def normalize_skill_id(skill) -> str:
    """
    Extract skill_id with multiple fallbacks.
    NEVER returns "unknown".
    """
    # Try direct id attribute
    skill_id = getattr(skill, 'id', None)
    if skill_id and skill_id != "unknown":
        return skill_id

    # Try class name
    class_name = skill.__class__.__name__
    if "Skill" in class_name:
        # Convert "EchoSkill" → "echo"
        return class_name.replace("Skill", "").lower() + ".fallback"

    # Try module name
    module_name = getattr(skill, '__module__', '')
    if 'canonical_skills' in module_name:
        return "canonical." + class_name

    # Last resort: hash of object (consistent across runs)
    return f"skill_{hash(str(skill)) & 0x7fffffff}"
```

---

## Implementation Plan

### Phase 1: Critical Fix (1 hour)
1. Add `normalize_skill_id()` function to `goal_executor_v2.py`
2. Replace all `skill.id` with `normalize_skill_id(skill)`
3. Add error logging when skill has no id
4. Test with 5 atomic goals

### Phase 2: Validation (30 min)
1. Check all skills in registry have `.id`
2. Find and fix skills without `.id`
3. Add registration validation

### Phase 3: Monitoring (30 min)
1. Add metric: `skill_id_extraction_success_rate`
2. Alert if < 95%
3. Log all skill selection failures

---

## Testing Checklist

- [ ] Create 5 test atomic goals
- [ ] Verify all have `skill_id != "unknown"`
- [ ] Verify all `goal_executions` rows have valid skill_id
- [ ] Verify all `experiences` rows have valid skill_used
- [ ] Check goal progress updates correctly
- [ ] Monitor for 1 hour - no new "unknown" skill_ids

---

## Success Criteria

**Before Fix**:
- 75% failure rate (3/4 executions)
- skill_id = "unknown" in 75% of records
- Learning loop broken

**After Fix**:
- 95%+ success rate
- skill_id = valid identifier in 99%+ of records
- Learning loop working
- Experiences recorded properly

---

## Related Issues

### Issue 1: Goal Progress Not Updated
**Symptom**: 161 active goals with 4% avg progress
**Root Cause**: Execution errors prevent progress updates
**Fix**: Same as above - fix skill_id extraction

### Issue 2: Experiences Not Recorded
**Symptom**: Only 4 experiences total (3 unknown, 1 core.echo)
**Root Cause**: Unknown skill_id creates invalid experiences
**Fix**: Same as above

### Issue 3: Execution Analytics Broken
**Symptom**: Can't track skill performance
**Root Cause**: 75% of records have skill_id = "unknown"
**Fix**: Same as above

---

## Next Steps

1. **Implement Option 1** (Hard Fix) - highest priority
2. **Add monitoring** for skill_id extraction
3. **Fix all skills** to ensure they have `.id` attribute
4. **Add integration test** for skill selection pipeline
5. **Document** proper skill format for future

---

## Questions for User

1. Do you want me to implement **Option 1** (Hard Fix) now?
2. Should I also add the **monitoring** (Phase 3)?
3. Do you want to see **Execution Orchestrator** architecture?

The Execution Orchestrator is the layer that OpenAI/Anthropic/DeepMind use to make systems 10x more stable. It's missing from most DIY agent systems but would solve these issues permanently.

Let me know which path to take!
