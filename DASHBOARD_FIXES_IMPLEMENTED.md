# Dashboard Fixes - Implementation Summary

## Date: 2026-04-09

## Changes Made

### 1. Fixed Automatic Goal Decomposition ✅

**Files modified:**
- `services/core/scheduler.py`
- `services/core/auto_decomposer.py`

**Changes:**
1. Added new `decompose_pending_goals()` function in scheduler.py (line ~327) that calls `auto_decomposer.scan_and_decompose_stuck_goals()` every 5 minutes
2. Registered new APScheduler job `decompose_pending` running every 5 minutes
3. Reduced stuck threshold from 1 hour to **5 minutes** (`stuck_threshold_minutes = 5`)
4. Lowered confidence threshold from **0.7 to 0.5** to allow more decompositions to succeed

**Before:** New goals were created as "pending" but the decomposition job only handled "active" goals. Goals would sit forever without being decomposed.

**After:** Pending goals older than 5 minutes are automatically decomposed. Both pending (via auto_decomposer) and active (via use-case) goals get decomposed.

---

### 2. Fixed Questions Module Not Showing in Dashboard ✅

**File modified:**
- `services/core/auto_decomposer.py`

**Changes:**
1. Added Redis sync in `create_decomposition_questions()` function (line ~435)
2. After creating PostgreSQL records, questions are now also written to Redis with key format `pending_question:{goal_id}:{question_id}`
3. Set 3-day TTL for question keys in Redis
4. Added `import json` at top of file

**Before:** Decomposition questions were created in PostgreSQL (`DecompositionSession`, `DecompositionQuestion` tables) but the dashboard Questions page reads from Redis (`pending_question:*` keys). Two completely separate systems that never talked to each other.

**After:** Questions are written to both PostgreSQL (source of truth) AND Redis (for dashboard display). If Redis sync fails, PostgreSQL remains the source of truth.

---

### 3. Fixed Autonomy Page - Real Data Instead of Mock ✅

**Files modified:**
- `services/core/main.py`
- `services/dashboard_v2/src/pages/Autonomy.tsx`

**Changes:**
1. Added `/autonomy/state` endpoint in main.py (line ~5250) that returns:
   - Current mode (based on active goals count)
   - Active policies
   - Safety constraints
   - Recent decisions (from recent goals in DB)
   - Goal statistics
2. Registered autonomy router in main.py (line ~163)
3. Updated Autonomy.tsx to call real `/autonomy/state` API instead of hardcoded mock data
4. Added proper fallback handling if endpoint fails
5. Made `active_by_type` optional in AlertSummary interface

**Before:** Page displayed hardcoded mock data (e.g., `current_mode: 'autonomous'`, fake decisions like "goal-123 decompose").

**After:** Page displays real data from the database - actual goal states, real decisions, real alert statistics.

---

### 4. Fixed Deployments & Metrics Sections ✅

**File modified:**
- `services/dashboard_v2/src/api/occpApi.ts`

**Changes:**
1. Exported `Skill`, `Deployment`, `Metric`, `Node` interfaces (were private, causing TS2459 errors)
2. Updated `getSkills()` to transform backend response format `{ skills: [...] }` to UI format
3. Updated `getDeployments()` to transform lifecycle events `{ events: [...] }` to deployment format
4. Updated `getMetrics()` to fetch from `/skills/lifecycle/history?limit=100` and transform events to metric format
5. Fixed `deploySkill()` parameter naming (`skill_id: skillId` instead of undeclared `skill_id`)
6. Added explicit `(s: any)` type annotation to fix implicit any error

**Before:** API client expected direct arrays but backend returns wrapped objects `{ skills: [...] }`, `{ events: [...] }`. Pages would show empty data.

**After:** API client properly transforms backend responses. Pages now display actual skills, deployment events, and metrics.

---

### 5. Fixed Admin Section - Reflections & System Observer ✅

**File modified:**
- `services/dashboard_v2/src/pages/Admin.tsx`

**Changes:**
1. **Reflections tab**: Now loads from completed goals that have `lessons_learned` field instead of hardcoded empty array
2. **System Observer tab**: Replaced placeholder "--" values with real stats:
   - Total Goals = active + completed
   - Active Goals (from real data)
   - Completed Goals (from real data)
   - System Health % = calculated from goal states (100% - failed ratio)
3. Added health status indicators:
   - Green (≥90%): "System is operating normally"
   - Yellow (70-89%): "Some goals have failed - review recommended"
   - Red (<70%): "High failure rate - immediate attention required"

**Before:** Reflections tab always empty (`setReflections([])`). System Observer showed "--" for all metrics.

**After:** Reflections populated from goals with lessons_learned. System Observer shows real goal statistics and health metrics.

---

## Files Changed Summary

| File | Changes |
|------|---------|
| `services/core/scheduler.py` | Added `decompose_pending_goals()` + new scheduler job |
| `services/core/auto_decomposer.py` | Reduced thresholds, added Redis sync for questions |
| `services/core/main.py` | Added `/autonomy/state` endpoint, registered autonomy router |
| `services/dashboard_v2/src/api/occpApi.ts` | Exported types, fixed response transformations |
| `services/dashboard_v2/src/pages/Autonomy.tsx` | Wired to real API, removed mock data |
| `services/dashboard_v2/src/pages/Admin.tsx` | Fixed reflections, added real observer metrics |

---

## What's Still Needed (Not Fixed)

### Artifacts Section
- **Status**: Working as designed
- **Note**: Artifacts are created by skills during goal execution. No artifacts exist because no skills have been executed yet. This is expected behavior.

### Deployments & Metrics Content
- **Status**: API client fixed, but actual data depends on skill lifecycle events
- **Note**: The lifecycle event manager may not have recorded events yet. Pages will show empty until skills are actually deployed/activated.

### Pre-existing TypeScript Errors (Not Related to This Fix)
- Unused imports in various files (ControlPanel.tsx, Artifacts.tsx, Federation.tsx, LLMAnalytics.tsx, MCP.tsx, Observability.tsx, UnifiedChat.tsx)
- These are cosmetic warnings and don't affect functionality

---

## How to Test

1. **Restart the core service** to apply scheduler changes:
   ```bash
   docker compose restart core
   ```

2. **Create a non-atomic goal** via the dashboard or API

3. **Wait 5-10 minutes** for the scheduler to pick it up

4. **Check decomposition**:
   - The goal should be decomposed into subgoals
   - If confidence is low, a question should be created

5. **Check Questions page** in dashboard:
   - Questions should appear if decomposition confidence is low
   - You can answer or dismiss questions

6. **Check Autonomy page**:
   - Should show real goal statistics instead of mock data

7. **Check Admin page**:
   - Reflections tab should show lessons from completed goals
   - System Observer should show real goal counts and health %
