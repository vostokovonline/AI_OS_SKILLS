# MCP Skill Autogeneration - Complete Architecture

## Production-Ready System with Dependency Management, Rate Limiting, and Pruning

---

## Full Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GOAL EXECUTOR                                  │
│                                                                         │
│  1. Receives goal with requirements                                    │
│  2. Checks existing skills via skill_registry                          │
│  3. No match? → Triggers MCP Manager                                   │
└────────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         MCP MANAGER                                     │
│                                                                         │
│  find_or_generate_skill(capabilities, requirements, goal_context)       │
│                                                                         │
│  ├─→ Check if plugin exists in _registry                               │
│  │   └─→ Yes: Return plugin_id                                         │
│  │                                                                       │
│  └─→ No: Trigger background generation (async)                         │
│      └─→ Return "fallback_echo" for immediate use                       │
└────────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼ (async background)
┌─────────────────────────────────────────────────────────────────────────┐
│                   MCP SKILL GENERATOR                                  │
│                                                                         │
│  generate_skill(missing_capabilities, requirements, goal_context)      │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ STEP 0: Rate Limiting Check                                     │   │
│  │                                                                 │   │
│  │  ✓ Max concurrent generations: 3                              │   │
│  │  ✓ Cooldown between generations: 60s                          │   │
│  │  ✓ Auto-prune old skills before hitting cap                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ STEP 1: Check cap (MAX_PLUGINS=50)                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ STEP 2: Build prompt with goal context                          │   │
│  │  - Capabilities list                                            │   │
│  │  - Input/Output types                                           │   │
│  │  - Goal title and description                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ STEP 3: Generate code via LLM (local-coder)                    │   │
│  │  - Model: ollama/qwen2.5-coder:latest                         │   │
│  │  - Temperature: 0.2 (deterministic)                            │   │
│  │  - Response time: ~30-50s                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ STEP 4: Extract skill class                                     │   │
│  │  - Remove markdown code blocks                                  │   │
│  │  - Extract plugin_id from class definition                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ STEP 5: Save to file                                            │   │
│  │  /app/mcp_plugins/{plugin_id}.py                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ STEP 5.5: Install Dependencies ⭐ NEW                          │   │
│  │                                                                 │   │
│  │  MCPDependencyManager:                                          │   │
│  │  1. Extract imports from code                                   │   │
│  │  2. Filter stdlib (os, sys, json, etc.)                         │   │
│  │  3. Map imports → pip packages                                   │   │
│  │  4. Auto-install missing packages                               │   │
│  │     - pip install {package} -q                                  │   │
│  │     - Cache installed packages                                  │   │
│  │     - Log failures (non-blocking)                               │   │
│  │                                                                 │   │
│  │  Example:                                                       │   │
│  │    yfinance → pip install yfinance                              │   │
│  │    requests → pip install requests                              │   │
│  │    bs4 → pip install beautifulsoup4                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ STEP 6: Sandbox Validation                                      │   │
│  │                                                                 │   │
│  │  Check 1: Syntax validity (import test)                         │   │
│  │  Check 2: Required attributes (id, execute)                     │   │
│  │          - Skip base Skill class                               │   │
│  │  Check 3: Safety (dangerous patterns)                           │   │
│  │  Check 4: Mock execution (smoke test)                           │   │
│  │                                                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ STEP 7: Create plugin object                                    │   │
│  │  MCPSkillPlugin:                                                 │   │
│  │    - plugin_id, skill_code                                      │   │
│  │    - capabilities, version                                      │   │
│  │    - status (experimental/failed)                                │   │
│  │    - generation_status (generating/completed/failed) ⭐         │   │
│  │    - generation_started_at, generation_completed_at ⭐         │   │
│  │    - execution_count, success_count                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ STEP 8: Register in _registry                                   │   │
│  │ STEP 9: Save to database (autogenerated_skills table)           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Status Tracking: ⭐                                                   │
│  ├── generation_status: "completed" or "failed"                        │
│  ├── generation_duration: logged to metrics                          │
│  └── error: captured if validation failed                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Safeguards Against Skill Explosion

### 1. Rate Limiting
```
MAX_CONCURRENT_GENERATIONS = 3
GENERATION_COOLDOWN_SECONDS = 60
```

**Behavior:**
- Max 3 simultaneous generations
- 60s cooldown between generations
- Prevents LLM spam / resource exhaustion

### 2. Skill Pruning
```python
PRUNING_THRESHOLD_DAYS = 30
MIN_SUCCESS_RATE_FOR_RETENTION = 0.3  # 30%
MIN_EXECUTIONS_BEFORE_PRUNING = 5
```

**Pruning Logic:**
```
IF skill_age > 30 days AND
   (execution_count < 5 OR success_rate < 30%):
    DELETE skill file
    MARK as "deprecated" in database
    REMOVE from _registry
```

### 3. Hard Cap
```python
MAX_PLUGINS = 50
```

When cap is reached:
- Auto-prune triggers first
- If still at cap → reject new generation

---

## Dependency Management Flow

```
Generated Skill Code
        │
        ▼
┌──────────────────────────┐
│ Extract Imports          │
│  - import yfinance       │
│  - import requests       │
│  - from bs4 import BS    │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Filter Stdlib            │
│  - Remove: os, sys, json │
│  - Remove: project mods  │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Map to Pip Packages       │
│  yfinance → yfinance     │
│  bs4 → beautifulsoup4    │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Check Cache              │
│  _installed_cache = set()│
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Install Missing          │
│  pip install {pkg} -q    │
└──────────────────────────┘
```

**Supported Packages:**
- yfinance (stock data)
- requests (HTTP)
- beautifulsoup4 (scraping)
- pandas, numpy (data)
- matplotlib (visualization)
- httpx, aiohttp (async HTTP)
- And more...

---

## Background Generation Monitoring

### MCPSkillPlugin Status Fields

```python
class MCPSkillPlugin:
    # Basic info
    plugin_id: str
    status: str  # experimental, stable, deprecated, failed

    # ⭐ Generation tracking
    generation_status: str  # generating, completed, failed
    generation_started_at: datetime
    generation_completed_at: Optional[datetime]
    generation_error: Optional[str]

    # Performance metrics
    execution_count: int
    success_count: int
    success_rate: float
```

### Monitoring Example

```python
plugin = await mcp_manager.get_plugin("stock_fetcher_skill")

print(f"Status: {plugin.generation_status}")
print(f"Duration: {(plugin.generation_completed_at - plugin.generation_started_at).total_seconds()}s")
print(f"Error: {plugin.generation_error}")
```

**Output:**
```
Status: completed
Duration: 52.3s
Error: None
```

---

## Test Results

```
✓ PASS - Dependency Extraction
✓ PASS - Rate Limiting (3 concurrent, 60s cooldown)
✓ PASS - Generation Status Tracking
✓ PASS - Generate with Dependencies (auto-installed requests)
✓ PASS - Pruning Logic (30 days, <30% success rate)
✓ PASS - Concurrent Protection (5/5 hit rate limits)
```

---

## Production Checklist

✅ **Dependency Management**
- Auto-extract imports from generated code
- Filter stdlib modules
- Install pip packages automatically
- Cache installed packages
- Handle install failures gracefully

✅ **Rate Limiting**
- Max 3 concurrent generations
- 60s cooldown between generations
- Clear error messages for limits

✅ **Pruning**
- Auto-remove skills after 30 days
- Keep if >30% success rate and 5+ executions
- Mark as "deprecated" in database
- Delete plugin files

✅ **Background Monitoring**
- Track generation status
- Log generation duration
- Capture errors for debugging
- Non-blocking execution

✅ **Safety**
- Sandbox validation before registration
- Dangerous pattern detection
- Mock execution testing

---

## API Usage

### Generate Skill (Background)
```python
from mcp_manager import mcp_manager

# Non-blocking trigger
plugin_id = await mcp_manager.find_or_generate_skill(
    capabilities=["stock_analysis"],
    requirements={"input_type": "text", "output_type": "report"},
    goal_context={"title": "Analyze AAPL", "description": "Stock analysis"}
)

# Immediately returns fallback or plugin_id
# Generation happens in background
```

### Check Generation Status
```python
from mcp_skill_generator import mcp_skill_generator

plugin = await mcp_skill_generator.get_plugin("stock_analysis_skill")

if plugin.generation_status == "completed":
    print(f"✓ Generated in {plugin.generation_duration}s")
elif plugin.generation_status == "generating":
    print(f"⏳ Still generating...")
elif plugin.generation_status == "failed":
    print(f"✗ Failed: {plugin.generation_error}")
```

### List Plugins
```python
plugins = await mcp_manager.list_plugins(status_filter="experimental")

for p in plugins:
    print(f"{p['plugin_id']}: {p['success_rate']}")
```

---

## Configuration

All settings in `mcp_skill_generator.py`:

```python
# Generation
MAX_PLUGINS = 50
GENERATION_MODEL = "local-coder"  # Ollama qwen2.5-coder

# Rate Limiting
MAX_CONCURRENT_GENERATIONS = 3
GENERATION_COOLDOWN_SECONDS = 60

# Pruning
PRUNING_THRESHOLD_DAYS = 30
MIN_SUCCESS_RATE_FOR_RETENTION = 0.3
MIN_EXECUTIONS_BEFORE_PRUNING = 5
```

---

## Future Enhancements

1. **Skill Improvement Loop**
   - Analyze execution logs
   - Regenerate with better prompts
   - A/B test versions

2. **Experimental → Stable Promotion**
   - Auto-promote after 20 executions
   - Require >90% success rate

3. **Performance Metrics API**
   - Latency tracking
   - Memory usage
   - Error rates

4. **Dependency Version Pinning**
   - Store package versions with skill
   - Reproducible environments

---

🎉 **MCP Skill Autogeneration is production-ready!**
