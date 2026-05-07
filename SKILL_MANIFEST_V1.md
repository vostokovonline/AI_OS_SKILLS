# Skill Manifest v1 - Clear Contracts for Skills

## 🎯 Purpose: 5 Problems Solved

**Without manifest**: skill = black box
**With manifest**: skill = contract

Skill Manifest solves:

1. ✅ **Planner** knows what skill can actually do
2. ✅ **Goal System** knows what will be produced
3. ✅ **Artifact Layer** knows what to register
4. ✅ **Evaluation** knows what to check
5. ✅ **Dashboard** shows results, not chatter

---

## 1. Manifest Structure (v1)

### Format: YAML (or Python dict)

```yaml
skill:
  name: web_research
  version: "1.0"

  description: >
    Performs web search and produces a structured research artifact
    with sources and summary.

  category: research
  agent_roles: [Researcher, WebSurfer]

  inputs:
    schema: SearchQuery
    required: [query]
    optional: [max_sources, time_range]

  outputs:
    artifact_type: REPORT
    schema: ResearchReport
    reusable: true

  produces:
    - type: KNOWLEDGE
      store: vector_db
      tags: [research, web]
    - type: FILE
      format: markdown
      path_template: results/{goal_id}/research.md
      tags: [research, web, sources]

  constraints:
    max_tokens: 4000
    max_sources: 7
    timeout_sec: 60
    requires_api: [search]

  verification:
    - name: min_sources
      rule: sources_count >= 3
      description: Must have at least 3 sources
    - name: citations_present
      rule: has_citations == true
      description: Must include citations
    - name: non_empty_summary
      rule: len(summary) > 300
      description: Summary must be > 300 characters

  failure_modes:
    - no_sources
    - timeout
    - empty_result
```

---

## 2. Mandatory Fields (P0)

Without these, skill cannot be registered:

| Field | Description | Example |
|-------|-------------|---------|
| `name` | Unique identifier | `web_research` |
| `inputs.schema` | Input schema name | `SearchQuery` |
| `inputs.required` | Required fields | `["query"]` |
| `outputs.artifact_type` | What artifact is produced | `REPORT` |
| `produces` | List of artifacts produced | See below |
| `verification` | List of verification rules | See below |

---

## 3. How Planner Uses Manifest

### ❌ Before
```
"Take any skill, hope it works"
```

### ✅ After
Planner selects by:

- **category** - research, coding, analysis
- **agent_roles** - which agents can execute
- **outputs.artifact_type** - what artifact is produced
- **produces[].type** - specific artifact types

### Example

Goal requires:
```yaml
goal:
  level: L3
  requires:
    artifacts:
      - type: FILE
      - type: KNOWLEDGE
```

Planner finds skills:
```
✅ web_research - Produces FILE + KNOWLEDGE
❌ chat_completion - Produces no artifacts (not selected)
```

---

## 4. Connection to Goal Atomicity (L3)

### Atomic Goal Requirements

```yaml
goal:
  level: L3
  is_atomic: true
  requires:
    artifacts:
      - type: FILE
      - type: KNOWLEDGE
```

### Planner Constraint

Planner CANNOT select a skill that doesn't cover `requires.artifacts`:

```python
# Find skills that cover ALL requirements
skills = registry.find_for_goal_requirements([
    ArtifactType.FILE,
    ArtifactType.KNOWLEDGE
])

# Only skills that produce BOTH types are returned
```

---

## 5. Execution Contract

### Every Skill MUST Return

```python
class SkillResult:
    artifacts: list[Artifact]  # Produced artifacts
    status: str               # success | failed
    error: str | None         # Error message if failed
    metadata: dict | None     # Additional info
```

### Old Way (❌)
```python
def execute_skill(...):
    # ... do work ...
    return "Task completed"  # Just text
```

### New Way (✅)
```python
async def execute_skill(goal_id, ...):
    # ... do work ...

    # Save result to file
    output_path = f"results/{goal_id}/research.md"
    with open(output_path, 'w') as f:
        f.write(result)

    # MUST return SkillResult with artifacts
    return SkillResult(
        artifacts=[
            {
                "artifact_type": "FILE",
                "content_kind": "file",
                "content_location": output_path,
                "domains": ["research"],
                "tags": ["web", "sources"]
            },
            {
                "artifact_type": "KNOWLEDGE",
                "content_kind": "vector_db",
                "content_location": f"vector_{goal_id}",
                "domains": ["research"]
            }
        ],
        status="success",
        metadata={"sources_count": 5}
    )
```

### If No Artifacts → Execution Failed

```python
if not result.artifacts:
    goal.status = "failed"
    error = "Skill produced no artifacts"
```

---

## 6. Verification - Rules, Not LLM

### Manifest Defines Rules

```yaml
verification:
  - name: min_sources
    rule: sources_count >= 3
  - name: citations_present
    rule: has_citations == true
  - name: non_empty_summary
    rule: len(summary) > 300
```

### Execution Checks Rules

```python
# Code-based verification (NOT LLM)
for rule in manifest.verification:
    if not evaluate_rule(artifact, rule):
        artifact.verification_status = "failed"
        artifact.verification_results.append({
            "name": rule.name,
            "passed": False,
            "details": f"Rule failed: {rule.rule}"
        })
```

### LLM Can Suggest, But NOT Confirm

- ❌ LLM: "This artifact looks good" (not acceptable)
- ✅ Code: `sources_count >= 3` (acceptable)

---

## 7. Skill Registry

### Core Methods

```python
from skill_registry import skill_registry

# Load built-in skills
skill_registry.load_builtin()

# Find by output artifact type
skills = skill_registry.find_by_output(ArtifactType.FILE)

# Find by agent role
skills = skill_registry.find_by_role("Researcher")

# Find for goal requirements
skills = skill_registry.find_for_goal_requirements([
    ArtifactType.FILE,
    ArtifactType.KNOWLEDGE
])

# Validate inputs before execution
is_valid, error = skill_registry.validate_inputs(
    "web_research",
    {"query": "..."}
)
```

---

## 8. API Endpoints

### List All Skills
```http
GET /skills?category=research&agent_role=Researcher&artifact_type=FILE
```

Response:
```json
{
  "status": "ok",
  "count": 2,
  "skills": [
    {
      "name": "web_research",
      "category": "research",
      "agent_roles": ["Researcher", "WebSurfer"],
      "inputs": {
        "schema": "SearchQuery",
        "required": ["query"],
        "optional": ["max_sources"]
      },
      "outputs": {
        "artifact_type": "REPORT",
        "reusable": true
      },
      "produces": [
        {
          "type": "KNOWLEDGE",
          "store": "vector_db"
        },
        {
          "type": "FILE",
          "format": "markdown"
        }
      ],
      "verification": [
        {
          "name": "min_sources",
          "rule": "sources_count >= 3"
        }
      ]
    }
  ]
}
```

### Get Skill Manifest
```http
GET /skills/web_research
```

### Find Skills for Goal
```http
POST /skills/find

{
  "required_artifacts": ["FILE", "KNOWLEDGE"],
  "agent_role": "Researcher",
  "category": "research"
}
```

### Validate Inputs
```http
POST /skills/validate_inputs

{
  "skill_name": "web_research",
  "inputs": {"query": "...", "max_sources": 5}
}
```

---

## 9. Dashboard: Skills View

### Skill List with Manifest Info

```
🔧 SKILLS

📊 web_research
Category: research
Agents: Researcher, WebSurfer
Produces:
  🧠 KNOWLEDGE (vector_db)
  📄 FILE (markdown)
Verified by:
  ✓ min_sources (sources_count >= 3)
  ✓ citations_present (has_citations == true)
  ✓ non_empty_summary (len(summary) > 300)
```

### Now Skills = Production Lines
- Not just "buttons"
- Clear input/output contracts
- Predictable artifacts
- Verifiable results

---

## 10. Common Mistake

### ❌ Making Manifest "for Humans"
```yaml
# Bad: Too verbose, human-focused
description: >
  This skill performs a comprehensive search of the web
  using advanced algorithms and returns detailed results
  that have been carefully curated...
```

### ✅ Making Manifest "for System"
```yaml
# Good: Contract-focused
inputs:
  required: [query]
outputs:
  artifact_type: REPORT
produces:
  - type: FILE
  - type: KNOWLEDGE
verification:
  - name: min_sources
    rule: sources_count >= 3
```

**Readability secondary. Contract primary.**

---

## 11. Success Criterion

### Question:
**"Can you disable LLM reasoning and system still works using only manifests + planner?"**

### v1 Answer:
✅ **YES** - System becomes predictable

**Evidence**:
- Planner selects skills by manifest contracts
- Skills produce verifiable artifacts
- Execution validated against rules
- No "hope it works" randomness

---

## 12. Built-in Skills v1

| Name | Category | Produces | Agent |
|------|----------|----------|-------|
| `web_research` | research | REPORT, FILE, KNOWLEDGE | Researcher, WebSurfer |
| `code_analysis` | analysis | REPORT, FILE (x2) | Coder, Researcher |
| `file_write` | execution | FILE | Coder |
| `data_analysis` | analysis | REPORT, DATASET, FILE | Researcher, Analyst |

---

## 13. Files Created

### New Files
- `skill_manifest.py` - Manifest model and built-in manifests
- `skill_registry.py` - Registry and executor
- `models.py:SkillManifestDB` - Database model
- `migrations/add_skill_manifests.sql` - Database migration
- `skills/manifests/web_research.yaml` - Sample manifest
- `skills/manifests/code_analysis.yaml` - Sample manifest

### Modified Files
- `main.py` - Added skill API endpoints

---

## 14. Database Schema

```sql
CREATE TABLE skill_manifests (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    version VARCHAR(50) DEFAULT '1.0',
    description TEXT,

    category VARCHAR(50) NOT NULL,
    agent_roles JSONB NOT NULL,

    inputs_schema VARCHAR(255) NOT NULL,
    inputs_required JSONB NOT NULL,
    inputs_optional JSONB,

    outputs_artifact_type VARCHAR(50) NOT NULL,
    outputs_schema VARCHAR(255) NOT NULL,
    outputs_reusable BOOLEAN DEFAULT TRUE,

    produces JSONB NOT NULL,

    constraints JSONB,
    verification JSONB NOT NULL,
    failure_modes JSONB,

    is_builtin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_skill_manifests_name ON skill_manifests(name);
CREATE INDEX idx_skill_manifests_category ON skill_manifests(category);
CREATE INDEX idx_skill_manifests_outputs_artifact_type ON skill_manifests(outputs_artifact_type);
```

---

## 15. Next Steps

After Skill Manifest v1, you can now:

1. **Skill Marketplace** - Share custom skills
2. **Skill Versioning** - Track manifest versions
3. **Skill Dependencies** - Skills that call other skills
4. **Auto-Selection** - Planner auto-picks best skill
5. **Skill Composition** - Combine multiple skills
6. **Skill Analytics** - Track skill success rates

---

## 16. Testing the Implementation

### Test 1: List all skills
```bash
curl http://ns_core:8000/skills
```

### Test 2: Get specific skill
```bash
curl http://ns_core:8000/skills/web_research
```

### Test 3: Find skills for goal
```bash
curl -X POST http://ns_core:8000/skills/find \
  -H "Content-Type: application/json" \
  -d '{
    "required_artifacts": ["FILE", "KNOWLEDGE"],
    "category": "research"
  }'
```

### Test 4: Validate inputs
```bash
curl -X POST http://ns_core:8000/skills/validate_inputs \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "web_research",
    "inputs": {"query": "test"}
  }'
```

---

## Conclusion

**Skill Manifest v1 is complete and operational**

✅ Manifest model and structure defined
✅ Registry for skill management
✅ Database model and migration applied
✅ API endpoints exposed
✅ Sample YAML manifests created
✅ Skill execution contract enforced
✅ Planner integration ready

**Key Achievement**: Skills are now predictable, verifiable components with clear contracts - not black boxes.

The system can now work using **only manifests + planner**, without relying on LLM reasoning for skill selection.
