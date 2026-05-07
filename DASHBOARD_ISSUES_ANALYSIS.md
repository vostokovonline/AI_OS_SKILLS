# Dashboard Issues Analysis & Fix Plan

## Date: 2026-04-09

## Problems Identified

### Problem 1: Automatic Goal Decomposition Not Working

**Root Cause Analysis:**

There are **TWO** decomposition systems competing, and neither is working correctly:

#### System A: APScheduler-based (scheduler.py)
`scheduler.py` line 450-457 schedules `decompose_non_atomic_goals()` every 10 minutes.
This calls the **use-case** `DecomposeActivatedGoalsUseCase` which:
- Only decomposes **active** non-atomic goals (not pending)
- Only processes up to `max_goals=5` per run
- Uses `decomposer.decompose_snapshot()` (READ phase) then applies changes (WRITE phase)

#### System B: Celery-based (periodic_tasks.py)
`periodic_tasks.py` defines `auto_decompose_stuck_goals()` Celery task scheduled **hourly**.
This calls `auto_decomposer.scan_and_decompose_stuck_goals()` which:
- Finds **pending** non-atomic goals older than 1 hour
- Decomposes them via `goal_decomposer.decompose_goal()`
- If confidence < 0.7, creates `DecompositionQuestion` records

**WHY IT DOESN'T WORK:**

1. **Celery is not running** - The `periodic_tasks.py` requires a Celery worker + Celery Beat scheduler. There's no evidence these are running in the docker-compose setup. The APScheduler in `scheduler.py` is running, but the Celery-based auto-decomposer is NOT.

2. **APScheduler decompose job only handles ACTIVE goals** - The scheduler job `decompose_non_atomic_goals()` calls the use-case which filters for `status == "active"`. But newly created goals start as `"pending"`, so they never get decomposed by the APScheduler job.

3. **No bridge between the two systems** - The APScheduler job and the Celery task operate on different goal statuses (active vs pending) with different logic.

4. **Confidence threshold too high** - `DECOMPOSITION_CONFIDENCE_THRESHOLD = 0.7` combined with the simplistic confidence calculation in `auto_decomposer.py`:
   ```python
   confidence = 0.5  # base
   + 0.2 if 3-7 subgoals
   - 0.1 if <3 or >10
   - 0.05 per generic term
   - 0.1 if description > 100 chars
   ```
   Most decompositions will score below 0.7, triggering question creation instead.

---

### Problem 2: Questions Module Not Showing in Dashboard

**Root Cause Analysis:**

When decomposition confidence is low, `create_decomposition_questions()` in `auto_decomposer.py` creates:
1. A `DecompositionSession` record in PostgreSQL
2. `DecompositionQuestion` records in PostgreSQL

**BUT** the Questions page in the dashboard (`QuestionsView.tsx`) fetches from a **completely different system**:
- Dashboard calls: `GET /questions/pending` → reads from **Redis** (`pending_question:*` keys)
- Auto-decomposer writes to: **PostgreSQL** (`DecompositionSession`, `DecompositionQuestion` tables)

**These are two completely separate question systems!**

The `/questions/pending` endpoint (main.py line 2512) reads from Redis keys like `pending_question:{goal_id}:{artifact_id}`.
The `create_decomposition_questions()` function writes to PostgreSQL `DecompositionSession` and `DecompositionQuestion` tables.

**There is NO code that syncs PostgreSQL decomposition questions to Redis.**

Additionally, there's a **DecompositionScreen** component (`DecompositionScreen.tsx`) that DOES query the PostgreSQL decomposition sessions via API calls like `getDecompositionSession()`, but this screen is separate from the Questions view.

---

### Problem 3: OCCP v1.0 Sections Are Empty/Meaningless

#### Skills Section
- **Status**: Real implementation
- **Data source**: PostgreSQL `SkillManifestDB` table
- **Issue**: Probably no skills registered in the database. This is expected if no skills have been "deployed" via the OCCP protocol.
- **Fix**: Register existing skills in the `SkillManifestDB` table.

#### Deployments Section
- **Status**: UI is built, backend endpoint likely missing/empty
- **API called**: `GET /skills/lifecycle/history`
- **Issue**: This endpoint is not defined in `services/core/api/endpoints/skills.py`. It may exist in `services/control_api/skill_lifecycle.py` but it's unclear if it's mounted.
- **Fix**: Either implement the endpoint or remove the section.

#### Metrics Section (OCCP Observability)
- **Status**: UI is built, backend endpoint likely missing/empty
- **API called**: `GET /skills/lifecycle/status`
- **Issue**: Same as Deployments - endpoint not clearly mounted.
- **Fix**: Wire up to real metrics from `/api/metrics/*` endpoints or remove section.

#### Artifacts Section
- **Status**: Real implementation
- **Data source**: PostgreSQL `Artifact` table + filesystem
- **Issue**: "Артефакты отсутствуют на диске" - No artifacts have been created by goal execution. Artifacts are created by skills during goal execution, not standalone.
- **Fix**: Artifacts will appear once skills execute goals and produce outputs. No immediate fix needed - this is working as designed.

#### Autonomy Section
- **Status**: **PLACEHOLDER/MOCK** - all data is hardcoded
- **Issue**: Component fetches from `apiClient.get('/alerts/summary')` but then **ignores the result** and sets mock data (line 67-90 of Autonomy.tsx):
  ```typescript
  setState({
    current_mode: 'autonomous',
    active_policies: ['ethical_bounds', 'budget_limits', 'safety_first'],
    safety_constraints: { ethics: ['no_harm', 'privacy_first', 'transparency'], budget: 10000, ... },
    recent_decisions: [{ id: '1', node_id: 'goal-123', action: 'decompose', ... }],
  });
  ```
- **Fix**: Wire up to real `/autonomy/state`, `/autonomy/policies`, `/autonomy/process` backend endpoints.

#### Admin Section
- **Status**: Partial implementation
- **Pending Approvals tab**: Works (fetches goals with `completion_mode === 'manual'`)
- **Reflections tab**: **HARDCODED EMPTY** - `setReflections([])` on line 93
- **System Observer tab**: **PLACEHOLDER** - shows "--" for all metrics
- **Fix**: Wire up reflections from goal `lessons_learned` data and connect system observer to real metrics.

---

## Fix Plan

### Priority 1: Fix Automatic Goal Decomposition

**Option A (Recommended): Unify the two systems**
1. Modify the APScheduler job in `scheduler.py` to ALSO decompose **pending** goals (not just active)
2. Remove the Celery-based `periodic_tasks.py` auto-decomposer (Celery is not running)
3. Have the APScheduler job call `auto_decomposer.scan_and_decompose_stuck_goals()` instead of the use-case

**Option B: Start Celery worker + beat**
1. Add Celery worker to docker-compose
2. Add Celery Beat scheduler
3. Ensure Redis broker is accessible

**Recommendation: Option A** - Simpler, no additional infrastructure needed.

### Priority 2: Fix Questions Module

**Option A (Recommended): Sync PostgreSQL questions to Redis**
1. In `create_decomposition_questions()` (auto_decomposer.py), after creating PostgreSQL records, also write to Redis:
   ```python
   redis_client.set(
       f"pending_question:{goal_id}:{session_id}",
       json.dumps({
           "artifact_id": str(session_id),
           "goal_id": str(goal_id),
           "question": question_text,
           "priority": "high",
           "asked_at": datetime.utcnow().isoformat(),
           "timeout_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
           "timeout_action": "wait_longer",
           "default_answer": "",
           "status": "pending"
       })
   )
   ```

**Option B: Update dashboard to read from PostgreSQL**
1. Create a new endpoint `GET /decomposition/questions/pending` that reads from PostgreSQL
2. Update `questionsStore.ts` to call this endpoint instead

**Recommendation: Option A** - Quick fix, no dashboard changes needed.

### Priority 3: Fix OCCP Sections

#### Deployments & Metrics
1. Check if `GET /skills/lifecycle/history` and `GET /skills/lifecycle/status` endpoints exist
2. If not, either:
   a. Implement them in `services/core/api/endpoints/skills.py`
   b. Or update `occpApi.ts` to call existing endpoints
   c. Or mark sections as "Coming Soon" in the UI

#### Autonomy
1. Update `Autonomy.tsx` to call real API endpoints:
   ```typescript
   const response = await apiClient.get('/autonomy/state');
   setState(response.data);
   ```
2. Remove all hardcoded mock data

#### Admin
1. Reflections: Fetch from goal `lessons_learned` field
2. System Observer: Connect to real Prometheus/metrics data or remove the tab

#### Artifacts
- **No fix needed**. Artifacts are created during goal execution. Once goals run and produce outputs, artifacts will appear.

---

## Implementation Order

1. **Fix decomposition** (Option A) - ~2 hours
2. **Fix questions sync** (Option A) - ~1 hour
3. **Fix Autonomy page** - ~1 hour
4. **Fix Deployments/Metrics** - ~2 hours
5. **Fix Admin reflections** - ~30 min
6. **Test end-to-end** - ~1 hour

**Total estimated effort: ~7 hours**
