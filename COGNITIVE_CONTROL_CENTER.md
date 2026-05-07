# AI-OS Cognitive Control Center Architecture
**Version:** 2.0  
**Date:** 2026-03-14  
**Status:** Architectural Redesign

---

## 🎯 Executive Summary

**Current State:** AI-OS has grown beyond a framework into a Cognitive Operating System, but interfaces remain as traditional dashboards.

**Problem:** 3 disconnected dashboards (v1/v2/v3) with:
- Different APIs
- Different data models
- No synchronization
- Missing cognitive layers

**Solution:** Single **Cognitive Control Center** - the operational brain of the AI-OS.

---

## 🏗️ Architecture Redesign

### Current Architecture (Broken)

```
┌─────────────────────────────────────────────────────────────┐
│                    MULTIPLE DASHBOARDS                      │
├─────────────────┬─────────────────┬─────────────────────────┤
│  Dashboard v1   │  Dashboard v2   │   Dashboard v3          │
│  (Streamlit)    │  (React/Vite)   │   (FastAPI)             │
│  Different APIs │  Different APIs │   Different APIs        │
└─────────────────┴─────────────────┴─────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   Core API      │
                    │   (8000)        │
                    └─────────────────┘
```

**Problems:**
- ❌ 3 different UIs
- ❌ No real-time updates
- ❌ No cognitive visibility
- ❌ No learning loop visibility

---

### Target Architecture (Cognitive Control Center)

```
┌─────────────────────────────────────────────────────────────┐
│              COGNITIVE CONTROL CENTER                       │
│              (Single Unified Interface)                     │
├─────────────────────────────────────────────────────────────┤
│  System  │  Brain  │  Skills  │  Learning  │  Memory      │
│  Panel   │  Panel  │  Panel   │  Panel     │  Panel       │
└─────────────────────────────────────────────────────────────┘
                              │
                    WebSocket / Events
                              │
┌─────────────────────────────────────────────────────────────┐
│                    CONTROL API LAYER                        │
├─────────────────────────────────────────────────────────────┤
│  /api/system  │  /api/goals  │  /api/skills  │  /api/traces│
│  /api/memory  │  /api/agents │  /api/metrics │  /ws/events │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    COGNITIVE CORE                           │
├─────────────────────────────────────────────────────────────┤
│  Goal System  │  Planner  │  Execution Engine              │
│  Skill Graph  │  Capability Graph  │  Trace System         │
│  Learning Engine  │  Dev Goal Generator  │  Skill Generator│
└─────────────────────────────────────────────────────────────┘
```

---

## 🧠 Cognitive Control Center Panels

### 1. SYSTEM PANEL

**Purpose:** Infrastructure health monitoring

**API:**
```
GET /api/system/status
GET /api/system/containers
GET /api/system/resources
```

**UI Components:**
```
┌─────────────────────────────────────────┐
│  SYSTEM STATUS                          │
├─────────────────────────────────────────┤
│  CPU: ████████░░ 45%                    │
│  RAM: █████████░ 78%                    │
│  Queue: 23 goals pending                │
│  Workers: 4 active                      │
│  Agents: 2 running                      │
│                                         │
│  Containers:                            │
│  ✅ ns_core      (healthy)              │
│  ✅ ns_memory    (healthy)              │
│  ⚠️  ns_litellm  (unhealthy)            │
│  ✅ ns_postgres  (healthy)              │
└─────────────────────────────────────────┘
```

---

### 2. BRAIN PANEL

**Purpose:** Active goal execution visibility

**API:**
```
GET /api/goals
GET /api/goals/active
GET /api/planner/state
GET /api/execution/queue
```

**UI Components:**
```
┌─────────────────────────────────────────┐
│  ACTIVE GOALS                           │
├─────────────────────────────────────────┤
│  Goal ID    Status    Progress  Plan   │
│  ─────────────────────────────────────  │
│  goal_001   running   75%      [●○○]   │
│  goal_002   pending   0%       [○○○]   │
│  goal_003   running   45%      [●●○]   │
│                                         │
│  EXECUTION QUEUE                        │
│  ─────────────────────────────────────  │
│  1. execute_skill(pdf_parse)            │
│  2. execute_skill(summarize)            │
│  3. validate_artifact(report.md)        │
└─────────────────────────────────────────┘
```

---

### 3. SKILLS PANEL

**Purpose:** Skill registry and lifecycle management

**API:**
```
GET /api/skills
GET /api/skills/registry
GET /api/capabilities/graph
POST /api/skills/{id}/activate
POST /api/skills/{id}/deprecate
```

**UI Components:**
```
┌─────────────────────────────────────────┐
│  SKILL REGISTRY                         │
├─────────────────────────────────────────┤
│  Skill               Capability  Rate   │
│  ─────────────────────────────────────  │
│  pdf_parser_v2       pdf_parse   91% ✅ │
│  pdf_parser_v1       pdf_parse   72% ⚠️ │
│  web_search          search      88% ✅ │
│  code_generate       coding      95% ✅ │
│                                         │
│  ACTIONS: [disable] [promote] [retrain] │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  CAPABILITY GRAPH                       │
├─────────────────────────────────────────┤
│  pdf_parse                              │
│    ├─ pdf_parser_v2 (91%)              │
│    └─ pdf_parser_v1 (72%)              │
│                                         │
│  search                                 │
│    ├─ web_search (88%)                 │
│    └─ deep_search (85%)                │
└─────────────────────────────────────────┘
```

---

### 4. LEARNING PANEL

**Purpose:** Self-improvement loop visibility

**API:**
```
GET /api/learning/traces
GET /api/learning/gaps
GET /api/learning/dev-goals
GET /api/learning/evolution
```

**UI Components:**
```
┌─────────────────────────────────────────┐
│  CAPABILITY GAPS                        │
├─────────────────────────────────────────┤
│  ⚠️  video_transcript_parse             │
│      Detected: 3 failed executions      │
│      Suggested: Generate new skill      │
│      [Generate Skill] [Ignore]          │
│                                         │
│  DEV GOALS                              │
│  ─────────────────────────────────────  │
│  1. create_skill(video_transcript)      │
│     Status: in_progress                 │
│  2. improve_skill(pdf_parser)           │
│     Status: pending                     │
│                                         │
│  SKILL EVOLUTION                        │
│  ─────────────────────────────────────  │
│  pdf_parser_v1 → v2 (success +19%)      │
└─────────────────────────────────────────┘
```

---

### 5. MEMORY PANEL

**Purpose:** Vector memory and context visibility

**API:**
```
GET /api/memory/vectors
GET /api/memory/artifacts
GET /api/memory/context
GET /api/memory/stats
```

**UI Components:**
```
┌─────────────────────────────────────────┐
│  VECTOR MEMORY                          │
├─────────────────────────────────────────┤
│  Total Vectors: 15,234                  │
│  Collections: 8                         │
│  Last Index: 2 hours ago                │
│                                         │
│  ARTIFACTS                              │
│  ─────────────────────────────────────  │
│  📄 report_2026_03_14.pdf (2.3MB)       │
│  📄 analysis_summary.md (45KB)          │
│  📊 metrics_q1.json (12KB)              │
│                                         │
│  CONTEXT STORE                          │
│  Active Contexts: 4                     │
│  Cache Hit Rate: 78%                    │
└─────────────────────────────────────────┘
```

---

### 6. TELEMETRY PANEL

**Purpose:** System-wide metrics and monitoring

**API:**
```
GET /api/metrics/traces
GET /api/metrics/success-rate
GET /api/metrics/latency
GET /api/metrics/tokens
GET /api/metrics/learning-rate
```

**UI Components:**
```
┌─────────────────────────────────────────┐
│  TELEMETRY                              │
├─────────────────────────────────────────┤
│  Traces (24h): 1,234                    │
│  Goal Success Rate: 87%                 │
│  Skill Success Rate: 91%                │
│  Avg Latency: 2.3s                      │
│  Token Usage: 456K                      │
│                                         │
│  LEARNING RATE                          │
│  ─────────────────────────────────────  │
│  New Skills (7d): 3                     │
│  Improved Skills (7d): 5                │
│  Deprecated Skills (7d): 2              │
│                                         │
│  [Export Metrics] [Set Alerts]          │
└─────────────────────────────────────────┘
```

---

## 🔌 Control API Specification

### System Endpoints

```python
# services/control_api/system_router.py

@router.get("/system/status")
async def get_system_status():
    """Get overall system health."""
    return {
        "status": "running",
        "uptime": "72h 15m",
        "containers": [...],
        "resources": {...}
    }

@router.get("/system/containers")
async def get_containers():
    """Get container status."""
    return [...]

@router.get("/system/resources")
async def get_resources():
    """Get resource usage."""
    return {
        "cpu": 45,
        "ram": 78,
        "disk": 62
    }
```

### Goals Endpoints

```python
# services/control_api/goals_router.py

@router.get("/goals")
async def get_goals(status: str = None):
    """Get all goals."""
    [...]

@router.get("/goals/active")
async def get_active_goals():
    """Get active goals only."""
    [...]

@router.get("/planner/state")
async def get_planner_state():
    """Get current planner state."""
    [...]
```

### Skills Endpoints

```python
# services/control_api/skills_router.py

@router.get("/skills")
async def get_skills():
    """Get skill registry."""
    [...]

@router.get("/capabilities/graph")
async def get_capability_graph():
    """Get capability → skills mapping."""
    [...]

@router.post("/skills/{id}/activate")
async def activate_skill(id: str):
    """Activate a skill."""
    [...]

@router.post("/skills/{id}/deprecate")
async def deprecate_skill(id: str):
    """Deprecate a skill."""
    [...]
```

### WebSocket Events

```python
# services/control_api/events.py

class EventType(Enum):
    GOAL_STARTED = "goal_started"
    GOAL_FINISHED = "goal_finished"
    SKILL_GENERATED = "skill_generated"
    TRACE_RECORDED = "trace_recorded"
    AGENT_ERROR = "agent_error"
    CAPABILITY_GAP = "capability_gap"
    SKILL_ACTIVATED = "skill_activated"
    SKILL_DEPRECATED = "skill_deprecated"

@websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        event = await event_queue.get()
        await websocket.send_json(event.dict())
```

---

## 🔄 Self-Improvement Loop

### Current Flow (Broken)

```
Goal → Skill Selection → Execution → Trace → ❌
```

**Missing:**
- ❌ Capability gap detection
- ❌ Dev goal generation
- ❌ Skill generation
- ❌ Capability graph update

### Target Flow (Self-Improving)

```
┌─────────────────────────────────────────────────────────────┐
│  GOAL                                                       │
│    ↓                                                        │
│  PLANNER (capability decomposition)                         │
│    ↓                                                        │
│  CAPABILITY GRAPH (skill selection with weights)            │
│    ↓                                                        │
│  EXECUTION ENGINE                                           │
│    ↓                                                        │
│  TRACE SYSTEM                                               │
│    ↓                                                        │
│  LEARNING ENGINE (trace mining)                             │
│    ↓                                                        │
│  CAPABILITY GAP DETECTION                                   │
│    ↓                                                        │
│  DEV GOAL GENERATOR                                         │
│    ↓                                                        │
│  SKILL GENERATOR                                            │
│    ↓                                                        │
│  SKILL LIFECYCLE MANAGER                                    │
│    ↓                                                        │
│  CAPABILITY GRAPH UPDATE ←──────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Critical Fixes Required

### 1. Fix Fallback Mechanism

**Current (Broken):**
```python
def execute_skill(skill, goal):
    try:
        return skill.execute(goal)
    except:
        return {"result": "echo", "success": True}  # ❌ WRONG
```

**Fixed:**
```python
def execute_skill(skill, goal):
    try:
        return skill.execute(goal)
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "confidence": 0.0  # ❌ Must signal failure
        }
```

### 2. Integrate CapabilityGraph in Skill Selection

**Current (Broken):**
```python
skills = skill_registry.list()  # ❌ No capability awareness
selected = skills[0]  # ❌ Random selection
```

**Fixed:**
```python
capabilities = planner.decompose(goal)  # ✅ Get required capabilities
skills = capability_graph.find_skills(capabilities)  # ✅ Find matching
selected = select_best_skill(skills)  # ✅ Weighted selection
```

### 3. Add Performance Weights to CapabilityGraph

**Current:**
```python
capability → [skill1, skill2]
```

**Fixed:**
```python
capability → [
    {skill: skill1, success_rate: 0.72, latency: 1.2s},
    {skill: skill2, success_rate: 0.91, latency: 0.7s}
]
```

### 4. Create SkillLifecycleManager

```python
class SkillLifecycleManager:
    def activate_skill(self, skill_id: str):
        """Activate skill and update capability graph."""
        [...]
    
    def validate_skill(self, skill_id: str) -> bool:
        """Validate skill before activation."""
        [...]
    
    def deprecate_skill(self, skill_id: str):
        """Deprecate skill and find replacement."""
        [...]
    
    def rollback_skill(self, skill_id: str):
        """Rollback to previous version."""
        [...]
```

### 5. Planner → Capability Decomposition

**Current:**
```python
def plan(goal):
    return select_skill(goal)  # ❌ Direct skill selection
```

**Fixed:**
```python
def plan(goal):
    # ✅ Decompose into tasks
    tasks = decompose_goal(goal)
    
    # ✅ Extract capabilities
    capabilities = []
    for task in tasks:
        caps = extract_capabilities(task)
        capabilities.extend(caps)
    
    # ✅ Return capability requirements
    return {
        "tasks": tasks,
        "capabilities": capabilities
    }
```

---

## 📊 Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

- [ ] Create `services/control_api/`
- [ ] Implement all API endpoints
- [ ] Add WebSocket event stream
- [ ] Fix fallback mechanism
- [ ] Integrate CapabilityGraph

### Phase 2: UI Consolidation (Week 3-4)

- [ ] Remove Dashboard v1 (Streamlit)
- [ ] Remove Dashboard v2 (React/Vite)
- [ ] Build Cognitive Control Center UI
- [ ] Connect to Control API
- [ ] Add real-time updates

### Phase 3: Self-Improvement (Week 5-6)

- [ ] Implement SkillLifecycleManager
- [ ] Add performance weights to graph
- [ ] Implement capability gap detection
- [ ] Add DevGoalGenerator
- [ ] Close learning loop

---

## 🎯 Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Dashboards | 3 | 1 |
| API Endpoints | Fragmented | Unified |
| Real-time Updates | No | Yes (WebSocket) |
| Capability Awareness | 0% | 100% |
| Skill Selection Accuracy | ~50% | >90% |
| Learning Loop | Broken | Closed |
| Self-Improvement | No | Yes |

---

**Next Steps:**
1. Review and approve architecture
2. Start Phase 1 implementation
3. Migrate existing functionality
4. Deploy Cognitive Control Center

---

**Document Version:** 1.0  
**Created:** 2026-03-14  
**Status:** Ready for Implementation
