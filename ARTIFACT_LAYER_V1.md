# Artifact Layer v1 - Tangible Results from Atomic Goals

## 🎯 Overview

**Key Principle**: "If I delete logs - the system's work remains"

The Artifact Layer ensures that every atomic goal (L3) produces:
1. **Explicit result** - Not just "execution completed"
2. **Fixed result** - Registered in database
3. **Reusable result** - Can be referenced later
4. **Verifiable result** - Code-based checks (NOT LLM)

**Without artifact → goal does NOT exist as completed**

---

## 1. Core Entity: Artifact

### Database Model (`models.py:Artifact`)

```python
class Artifact(Base):
    id: UUID                    # Primary key
    type: str                   # FILE|KNOWLEDGE|DATASET|REPORT|LINK|EXECUTION_LOG
    goal_id: UUID               # FK to goals (CASCADE DELETE)
    skill_name: str             # Skill that created it
    agent_role: str             # Agent that created it

    content_kind: str           # file|db|vector|external
    content_location: str       # Path, URL, DB ID

    domains: JSON               # ["programming", "research"]
    tags: JSON                  # ["bugfix", "feature"]
    language: str               # For code artifacts

    verification_status: str    # pending|passed|failed|partial
    verification_results: JSON  # [{"name": "...", "passed": true, "details": "..."}]

    reusable: bool              # Can be reused

    created_at: datetime
    updated_at: datetime
```

### Artifact Types (v1 - Minimal Sufficient)

| Type | Description | Examples |
|------|-------------|----------|
| **FILE** | Code, markdown, JSON | `.md`, `.py`, `.json` |
| **KNOWLEDGE** | Vector DB chunk | Knowledge base entry |
| **DATASET** | Data files | CSV, tables |
| **REPORT** | Structured summary | Analysis results |
| **LINK** | External reference | URL, repo |
| **EXECUTION_LOG** | Run result | Limited use |

---

## 2. Artifact Registry

**File**: `artifact_registry.py`

### Core Methods

#### `register()` - Register new artifact
```python
await artifact_registry.register(
    goal_id="uuid",
    artifact_type="FILE",
    content_kind="file",
    content_location="results/research.md",
    skill_name="research_skill",
    agent_role="Researcher",
    domains=["research", "analysis"],
    tags=["literature_review"],
    auto_verify=True
)
```

Returns:
```json
{
  "artifact_id": "uuid",
  "verification_status": "passed",
  "verification_results": [...]
}
```

#### `list_by_goal()` - Get all artifacts for a goal
```python
artifacts = await artifact_registry.list_by_goal(
    goal_id="uuid",
    verification_status="passed"  # optional filter
)
```

#### `check_goal_artifacts()` - Verify goal completion
```python
check = await artifact_registry.check_goal_artifacts(goal_id)

# Returns:
{
    "has_artifacts": true,
    "total_count": 3,
    "passed_count": 2,
    "failed_count": 0,
    "pending_count": 1,
    "goal_complete": true,  # For L3: true only if passed_count > 0
    "is_atomic": true
}
```

---

## 3. Artifact Verifier

**File**: `artifact_verifier.py`

### Key Principle: **Code-based verification, NOT LLM**

### Verification Types v1

#### For FILE artifacts
- `file_exists` - File exists on disk
- `file_not_empty` - File size > 0
- `min_length` - Content length ≥ threshold
- `json_valid` - Valid JSON (for .json files)
- `markdown_not_empty` - Markdown has content (for .md files)

#### For KNOWLEDGE artifacts
- `min_knowledge_length` - ≥ 100 characters

#### For DATASET artifacts
- `csv_readable` - Can parse as CSV
- `dataset_not_empty` - Has at least 1 row

#### For REPORT artifacts
- `report_min_length` - ≥ 200 characters

#### For LINK/EXTERNAL artifacts
- `url_format` - Valid URL format
- `repo_format` - Valid git repo format

#### For DB/VECTOR artifacts
- `db_reference_exists` - Non-empty reference
- `vector_id_exists` - Non-empty vector ID

### Usage

```python
verifier = ArtifactVerifier()

results = verifier.verify({
    "type": "FILE",
    "content_kind": "file",
    "content_location": "results/research.md"
})

# Returns list of VerificationResult:
[
    VerificationResult(name="file_exists", passed=True, details="File exists: ..."),
    VerificationResult(name="file_not_empty", passed=True, details="File size: 1234 bytes"),
    VerificationResult(name="markdown_not_empty", passed=True, details="Markdown has content")
]

overall_status = verifier.get_overall_status(results)
# "passed" | "failed" | "partial"
```

---

## 4. New Atomic Goal Rule (L3)

### ❌ Before
```
atomic = sufficiently small
```

### ✅ After
```
L3_atomic_goal:
  MUST:
    - produces >= 1 Artifact
    - artifact.type ∈ allowed_types
    - artifact.verification.status == passed

  If NO passed artifacts →
    status = "incomplete"
    (even if execution "succeeded")
```

### Updated Goal Execution Flow

**File**: `goal_executor.py:execute_goal()`

```
execute
  → skill produces artifact
    → register artifact
      → verify artifact (CODE-BASED)
        → check: L3 goal has passed artifacts?
          → YES: status = "done"
          → NO: status = "incomplete" + notification
```

### New Goal Status

Added `incomplete` status:
- Goal was executed
- But NO passed artifacts (for atomic goals)
- Progress = 0.9 (90% done, but no artifact)

---

## 5. Skill Integration

### Old Way (❌)
```python
def execute_skill(...):
    # ... do work ...
    return "Task completed"  # Just string
```

### New Way (✅)
```python
from artifact_registry import artifact_registry

async def execute_skill(goal_id, ...):
    # ... do work ...
    # Save result to file
    output_path = "results/research.md"
    with open(output_path, 'w') as f:
        f.write(result)

    # Register artifact
    await artifact_registry.register(
        goal_id=goal_id,
        artifact_type="FILE",
        content_kind="file",
        content_location=output_path,
        skill_name="research_skill",
        agent_role="Researcher",
        domains=["research"],
        auto_verify=True
    )

    return "Task completed, artifact registered"
```

---

## 6. API Endpoints

### Register Artifact
```http
POST /artifacts/register
Content-Type: application/json

{
  "goal_id": "uuid",
  "type": "FILE",
  "content_kind": "file",
  "content_location": "results/research.md",
  "skill_name": "research_skill",
  "agent_role": "Researcher",
  "domains": ["research"],
  "tags": ["literature_review"],
  "reusable": true,
  "auto_verify": true
}
```

### Get Goal Artifacts
```http
GET /goals/{goal_id}/artifacts?verification_status=passed
```

### Get Artifact Details
```http
GET /artifacts/{artifact_id}
```

### Verify Artifact
```http
POST /artifacts/{artifact_id}/verify
```

### Check Goal Artifacts
```http
GET /goals/{goal_id}/artifacts/check
```

### List All Artifacts
```http
GET /artifacts?goal_id=uuid&artifact_type=FILE&verification_status=passed&limit=50
```

---

## 7. Dashboard Integration

**File**: `app.py:show_goal_details()`

### Artifact Display in Goal Details

```
📋 Детали: [Goal Name]

├─ 📦 Артефакты (3)
│  ├─ Всего: 3
│  ├─ ✅ Прошли: 2
│  ├─ ⏳ В ожидании: 1
│  └─ ❌ Ошибки: 0
│
├─ ✅ 📄 FILE - `results/research.md`
│  ├─ Тип: FILE
│  ├─ Хранение: file
│  ├─ Статус: passed
│  ├─ 🔍 Результаты верификации:
│  │  ├─ ✅ file_exists: File exists
│  │  ├─ ✅ file_not_empty: File size: 1234 bytes
│  │  └─ ✅ markdown_not_empty: Markdown has content
│  ├─ 🏷️ Домены: ["research"]
│  └─ 🕒 Создан: 2026-01-08 12:34:56
│
└─ ⏳ 🧠 KNOWLEDGE - `vector_id_123`
   └─ ... (details)
```

### Warnings for Atomic Goals

If atomic goal has NO passed artifacts:
```
⚠️ Атомарная цель без подтвержденных артефактов!
L3 goals MUST produce artifacts.
```

---

## 8. Verification Examples

### FILE Artifact (Markdown)
```python
artifact = {
    "type": "FILE",
    "content_kind": "file",
    "content_location": "results/research.md"
}

# Checks performed:
✅ file_exists: File exists at /tmp/artifacts/results/research.md
✅ file_not_empty: File size: 2345 bytes
✅ markdown_not_empty: Markdown has content

# Overall status: passed
```

### FILE Artifact (JSON)
```python
artifact = {
    "type": "FILE",
    "content_kind": "file",
    "content_location": "results/data.json"
}

# Checks performed:
✅ file_exists: File exists
✅ file_not_empty: File size: 1234 bytes
✅ json_valid: JSON is valid

# Overall status: passed
```

### KNOWLEDGE Artifact
```python
artifact = {
    "type": "KNOWLEDGE",
    "content_kind": "vector",
    "content_location": "vector_id_12345"
}

# Checks performed:
✅ vector_id_exists: Vector ID: vector_id_12345

# Overall status: passed
```

### LINK Artifact
```python
artifact = {
    "type": "LINK",
    "content_kind": "external",
    "content_location": "https://github.com/user/repo"
}

# Checks performed:
✅ url_format: Valid URL format

# Overall status: passed
```

---

## 9. Success Criterion

### Question:
**"If I delete logs - does the system's work remain?"**

### v1 Answer:
✅ **YES** - If artifacts exist

**Evidence**:
- Files created and saved
- Knowledge chunks in vector DB
- Datasets stored
- Reports generated
- All registered in `artifacts` table

**Without artifacts**:
- Only logs remain
- Execution "succeeded" but no tangible result
- Goal marked as `incomplete`

---

## 10. What NOT to Do in v1

### ❌ Do NOT Add:
- Artifact versioning (v2+)
- Dependency graphs between artifacts (v2+)
- Provenance chains (v2+)
- Auto-merging of knowledge (v2+)
- Artifact marketplace (v2+)

**v1 is about fixation, not perfection**

---

## 11. Next Steps After v1

Once Artifact Layer v1 is stable:

1. **Skill Manifest** - Clear contract for skills:
   ```
   Input: {...}
   Output: Artifact
   Guarantees: [...]
   ```

2. **Memory ≠ Logs** - Use artifacts:
   - Extract knowledge from artifacts
   - Reference artifacts in memory
   - "I wrote this code → here's the artifact"

3. **Goal Mutation** - Based on real results:
   - Strengthen: "Previous artifact was too simple"
   - Weaken: "Previous artifact requirements too strict"

4. **Human-in-the-Loop** - Review artifacts:
   - Human approves/rejects artifacts
   - Feedback improves verification

5. **Artifact Search** - Find reusable artifacts:
   - Search by domain, type, tags
   - "Has similar goal been achieved before?"

---

## 12. Files Created/Modified

### New Files
- `models.py:Artifact` - Database model
- `artifact_verifier.py` - Code-based verification
- `artifact_registry.py` - CRUD operations
- `migrations/add_artifact_layer.sql` - Database migration

### Modified Files
- `goal_executor.py` - Added artifact check for atomic goals
- `main.py` - Added artifact API endpoints
- `app.py` - Added artifact display in dashboard

---

## 13. Database Schema

```sql
CREATE TABLE artifacts (
    id UUID PRIMARY KEY,
    type VARCHAR(50) NOT NULL,              -- FILE|KNOWLEDGE|DATASET|REPORT|LINK|EXECUTION_LOG
    goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    skill_name VARCHAR(255),
    agent_role VARCHAR(100),

    content_kind VARCHAR(50) NOT NULL,       -- file|db|vector|external
    content_location TEXT NOT NULL,

    domains JSONB,
    tags JSONB,
    language VARCHAR(50),

    verification_status VARCHAR(50) DEFAULT 'pending',
    verification_results JSONB,

    reusable BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_artifacts_goal_id ON artifacts(goal_id);
CREATE INDEX idx_artifacts_type ON artifacts(type);
CREATE INDEX idx_artifacts_verification_status ON artifacts(verification_status);
CREATE INDEX idx_artifacts_created_at ON artifacts(created_at DESC);
```

---

## 14. Testing the Implementation

### Test 1: Register FILE artifact
```bash
curl -X POST http://ns_core:8000/artifacts/register \
  -H "Content-Type: application/json" \
  -d '{
    "goal_id": "uuid",
    "type": "FILE",
    "content_kind": "file",
    "content_location": "test.md",
    "domains": ["test"]
  }'
```

### Test 2: Check goal artifacts
```bash
curl http://ns_core:8000/goals/{goal_id}/artifacts/check
```

### Test 3: Verify atomic goal enforcement
```bash
# Create atomic goal without artifacts
# → Should be marked as "incomplete"
```

---

## Conclusion

**Artifact Layer v1 is complete and operational**

✅ Database schema created
✅ Verification system implemented (code-based, not LLM)
✅ Registry for artifact management
✅ Goal execution updated to require artifacts for L3
✅ API endpoints exposed
✅ Dashboard shows artifacts
✅ Atomic goals MUST produce passed artifacts

**Key Achievement**: System now produces tangible, verifiable, reusable results that persist even after logs are deleted.
