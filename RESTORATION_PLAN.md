# AI_OS Dashboard Restoration Plan

## Current Status (2026-03-13)

| Component | Status | Port | Issues |
|-----------|--------|------|--------|
| **Core API** | ⚠️ Partial | 8000 | Missing /api/status endpoint |
| **Dashboard v1 (Streamlit)** | ⚠️ Unknown | 8501 | Need verification |
| **Dashboard v2 (React)** | ✅ Working | 3000 | ControlCenter fixed |
| **Dashboard v3 (FastAPI)** | ✅ Working | 8081 | CogOS integration works |
| **CogOS** | ✅ Running | - | Status: running |

---

## Critical Fixes Required

### 1. Core API - Add Missing Endpoints

**File:** `services/core/main.py`

**Missing endpoints:**
- `GET /api/status` - System status
- `GET /api/goals` - Goals list
- `GET /api/agents` - Agents status
- `GET /api/artifacts` - Artifacts list

**Fix:** Add compatibility layer for dashboard APIs

### 2. Dashboard v1 (Streamlit) - Verify & Fix

**File:** `services/dashboard/app.py`

**Actions:**
- Check all pages load correctly
- Verify API connections
- Fix broken imports

### 3. Dashboard v2 (React) - Complete Fixes

**Files:**
- `services/dashboard_v2/src/pages/ControlCenter.tsx` ✅ Fixed
- `services/dashboard_v2/src/pages/SystemHealth.tsx` - Check API calls
- `services/dashboard_v2/src/api/client.ts` - Verify base URL

**Actions:**
- Rebuild after fixes
- Test all pages

### 4. Dashboard v3 (FastAPI) - Enhance

**Files:**
- `ai_os/dashboard/` - Already working

**Actions:**
- Add more panels
- Improve real-time updates
- Add authentication

---

## Implementation Order

1. **Core API endpoints** (30 min)
2. **Dashboard v1 verification** (30 min)
3. **Dashboard v2 rebuild** (15 min)
4. **Integration testing** (30 min)

---

## Expected Final State

```
┌─────────────────────────────────────────────────────┐
│  AI_OS Dashboard Ecosystem                          │
├─────────────────────────────────────────────────────┤
│  v1 (Streamlit)  → http://localhost:8501/  ✅      │
│  v2 (React)      → http://localhost:3000/  ✅      │
│  v3 (FastAPI)    → http://localhost:8081/  ✅      │
│                                                       │
│  Core API        → http://localhost:8000/  ✅      │
│  CogOS           → Running                   ✅      │
└─────────────────────────────────────────────────────┘
```

---

## Test Checklist

- [ ] All dashboards accessible
- [ ] All API endpoints return 200
- [ ] CogOS status shows "running"
- [ ] Goals can be created/viewed
- [ ] Agents can be spawned
- [ ] Artifacts display correctly
- [ ] Command Center buttons work
- [ ] WebSocket connections work
- [ ] No console errors in browsers
