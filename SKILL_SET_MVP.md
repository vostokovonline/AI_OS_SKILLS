# Skill Set MVP v1 - Complete Documentation

## 🎯 Principle: "Alphabet", Not "Features"

These 5 skills are the **foundation** of the system:
- ✅ Each produces artifacts
- ✅ Each is verifiable
- ✅ Each combines with others
- ✅ None tied to specific domains

**This is the alphabet, not the features.**

---

## 🥇 1. text_to_file - Basic Production (MUST HAVE)

### Purpose
**System cannot be mute without it.**

Any goal must be able to produce a result.

### Manifest
```yaml
skill:
  name: text_to_file
  version: "1.0"
  category: production
  agent_roles: [Writer, Researcher, Coder]

  inputs:
    schema: WriteFileInput
    required: [text, filename]

  outputs:
    artifact_type: FILE
    reusable: true

  produces:
    - type: FILE
      format: markdown
      path: results/{goal_id}/{filename}

  verification:
    - name: file_exists
      rule: file_exists == true
    - name: min_length
      rule: len(content) >= 200
```

### What It Gives
- 📄 Reports
- 📄 Plans
- 📄 Specifications
- 📄 Explanations

### Usage
```python
skill = SkillSetFactory.create("text_to_file")

result = await skill.execute(
    inputs={
        "text": "# My Report\n\nThis is the content...",
        "filename": "report.md"
    },
    goal_id="G-123"
)

# Produces: results/G-123/report.md
```

### Why Mandatory
Without it:
- Goal completes → Nothing saved
- Dashboard shows → "100%" but no files
- User asks → "Where's the result?"

**With it**:
- Every goal can produce a tangible file
- System can always show what was created
- Foundation for all other skills

---

## 🥈 2. structured_generation - Structure Over Chaos

### Purpose
Remove chaos from LLM text. Foundation for planning.

### Manifest
```yaml
skill:
  name: structured_generation
  version: "1.0"
  category: reasoning
  agent_roles: [Planner, Analyst]

  inputs:
    schema: StructuredGenInput
    required: [prompt, output_schema]

  outputs:
    artifact_type: DATASET
    reusable: true

  produces:
    - type: DATASET
      format: json
      path: results/{goal_id}/structured.json

  verification:
    - name: schema_valid
      rule: json_schema_valid == true
```

### What It Gives
- 📋 Plans
- 📋 Task lists
- 📋 Decompositions
- 📋 Configs

### Usage
```python
skill = SkillSetFactory.create("structured_generation")

result = await skill.execute(
    inputs={
        "prompt": "Create a plan for research",
        "output_schema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
    },
    goal_id="G-123"
)

# Produces: results/G-123/structured.json
# {"steps": ["Step 1", "Step 2", ...]}
```

### Why Important
**Without it**: LLM produces chaotic text
**With it**: LLM produces structured data

This is the foundation for:
- Goal decomposition
- Task planning
- Configuration generation
- Data analysis results

---

## 🥉 3. web_research - Minimal Research Skill

### Purpose
Get facts, sources, and knowledge from the web.

### Manifest
```yaml
skill:
  name: web_research
  version: "1.0"
  category: research
  agent_roles: [Researcher]

  inputs:
    schema: SearchQuery
    required: [query]

  outputs:
    artifact_type: REPORT
    reusable: true

  produces:
    - type: FILE
      format: markdown
      path: results/{goal_id}/research.md
    - type: KNOWLEDGE
      store: vector_db

  verification:
    - name: min_sources
      rule: sources_count >= 3
```

### What It Gives
- 🔍 Facts
- 📚 Sources
- 🧠 Knowledge (indexed)

### Usage
```python
skill = SkillSetFactory.create("web_research")

result = await skill.execute(
    inputs={
        "query": "soil nutrition for tomatoes"
    },
    goal_id="G-123"
)

# Produces:
# - results/G-123/research.md (with sources)
# - Knowledge chunk in vector DB
```

### Why Research Matters
Facts over opinions:
- ❌ "Tomatoes need soil" (unverified)
- ✅ "According to [source], tomatoes need pH 6.0-6.8" (verified)

---

## 🧠 4. summarize_knowledge - Memory & Reuse

### Purpose
Don't lose knowledge. Make it reusable.

### Manifest
```yaml
skill:
  name: summarize_knowledge
  version: "1.0"
  category: memory
  agent_roles: [Analyst]

  inputs:
    schema: SummarizeInput
    required: [source_artifact_id]

  outputs:
    artifact_type: KNOWLEDGE
    reusable: true

  produces:
    - type: KNOWLEDGE
      store: vector_db
      tags: [summary]

  verification:
    - name: non_empty
      rule: len(content) > 150
```

### What It Gives
- 💾 Memory preservation
- 🔄 Knowledge reuse
- 📊 Condensed information

### Usage
```python
skill = SkillSetFactory.create("summarize_knowledge")

result = await skill.execute(
    inputs={
        "source_artifact_id": "artifact_123"
    },
    goal_id="G-123"
)

# Produces: Condensed knowledge chunk in vector DB
# Can be retrieved later: "What did we learn about X?"
```

### Why Memory Matters
**Without it**:
- Research performed → forgotten
- Knowledge lost → must redo research
- No accumulation

**With it**:
- Research → summarized → indexed → reusable
- Knowledge compounds over time
- System gets smarter

---

## 🧪 5. self_check - Verification & Control

### Purpose
Automatic sanity-check. Foundation for evolution.

### Manifest
```yaml
skill:
  name: self_check
  version: "1.0"
  category: evaluation
  agent_roles: [Evaluator]

  inputs:
    schema: SelfCheckInput
    required: [artifact_id]

  outputs:
    artifact_type: EXECUTION_LOG
    reusable: false

  produces:
    - type: EXECUTION_LOG
      format: json
      path: results/{goal_id}/check_result.json

  verification:
    - name: verdict_present
      rule: verdict in ["pass", "fail"]
```

### What It Gives
- ✅ Automatic sanity-check
- ✅ Quality control
- ✅ Verification foundation

### Usage
```python
skill = SkillSetFactory.create("self_check")

result = await skill.execute(
    inputs={
        "artifact_id": "artifact_123"
    },
    goal_id="G-123"
)

# Produces: results/G-123/check_result.json
# {"verdict": "pass", "checks": [...]}
```

### Why Verification Matters
**Without it**:
- Artifacts may be garbage
- No quality control
- Trust issues

**With it**:
- Every artifact can be checked
- Quality enforced automatically
- Trust built through verification

---

## 🧠 How They Combine

### Example Goal: "Research X and Save Findings"

```
Goal: "Research soil nutrition for tomatoes"
Level: L3 (Atomic)
Requires: [FILE, KNOWLEDGE]

Flow:
┌─────────────────────────────────────┐
│ 1. web_research                      │
│    query: "soil nutrition tomatoes"  │
│    ↓                                 │
│    Produces:                         │
│    - research.md (FILE)              │
│    - knowledge chunk (KNOWLEDGE)     │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ 2. summarize_knowledge               │
│    source: knowledge chunk           │
│    ↓                                 │
│    Produces:                         │
│    - condensed_knowledge (KNOWLEDGE) │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ 3. text_to_file                      │
│    text: condensed knowledge         │
│    filename: "final_report.md"      │
│    ↓                                 │
│    Produces:                         │
│    - final_report.md (FILE)          │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ 4. self_check                        │
│    artifact: final_report.md         │
│    ↓                                 │
│    Produces:                         │
│    - check_result.json (EXECUTION_LOG)│
└─────────────────────────────────────┘
```

### Result
```
📦 5 Artifacts Produced:
  ├─ research.md (web_research)
  ├─ knowledge chunk #1 (web_research)
  ├─ condensed_knowledge (summarize_knowledge)
  ├─ final_report.md (text_to_file)
  └─ check_result.json (self_check)

✅ Goal Status: DONE
```

---

## 📊 Skill Matrix

| Skill | Input | Output | Artifact Type | Reusable | Purpose |
|-------|-------|--------|---------------|----------|---------|
| **text_to_file** | text + filename | file | FILE | ✅ | Basic production |
| **structured_generation** | prompt + schema | file | DATASET | ✅ | Planning & structure |
| **web_research** | query | file + vector | FILE + KNOWLEDGE | ✅ | Facts & sources |
| **summarize_knowledge** | artifact_id | vector | KNOWLEDGE | ✅ | Memory & reuse |
| **self_check** | artifact_id | file | EXECUTION_LOG | ❌ | Verification |

---

## 🎯 Minimal but Sufficient

### Question: Why Only 5 Skills?

**Answer**: 5 skills = system starts working

| Need | Skill |
|------|-------|
| Write result | text_to_file |
| Plan tasks | structured_generation |
| Get facts | web_research |
| Remember | summarize_knowledge |
| Verify | self_check |

**All essential needs covered.**

### What's NOT Included (And Why)

| Skill | Why Not MVP |
|-------|-------------|
| code_execution | Can be built on text_to_file |
| email | Can be added later |
| database_query | Domain-specific |
| api_call | Domain-specific |
| file_analyze | Can use structured_generation + text_to_file |

**Focus: Foundation, not features.**

---

## 🔧 Usage Examples

### Example 1: Simple Research Goal

```python
from skills.mvp_skills import SkillSetFactory, SkillComposer

composer = SkillComposer()

# Goal: "Research X and save"
results = composer.execute_chain(
    skill_names=["web_research", "text_to_file"],
    goal_id="G-123",
    initial_inputs={"query": "topic X", "filename": "research_X.md"}
)

# Result: 3 artifacts (FILE + KNOWLEDGE + FILE)
```

### Example 2: Research with Summary

```python
# Goal: "Research X, condense, save"
results = composer.execute_chain(
    skill_names=[
        "web_research",           # Get facts
        "summarize_knowledge",    # Condense
        "text_to_file",           # Save
        "self_check"              # Verify
    ],
    goal_id="G-123",
    initial_inputs={"query": "topic X", "filename": "summary_X.md"}
)

# Result: 5 artifacts, verified
```

### Example 3: Structured Planning

```python
# Goal: "Create plan for X"
results = composer.execute_chain(
    skill_names=[
        "structured_generation",  # Generate plan
        "text_to_file",           # Save plan
        "self_check"              # Verify plan
    ],
    goal_id="G-123",
    initial_inputs={
        "prompt": "Create a plan to achieve X",
        "output_schema": plan_schema,
        "filename": "plan_X.json"
    }
)

# Result: 3 artifacts, verified plan
```

---

## 📈 Why This is the "Alphabet"

### Analogy: Language Learning

**First**, you learn the alphabet (ABC):
- Not enough to write novels
- But necessary for ALL writing
- Foundation for everything else

**Then**, you learn words:
- Combines letters
- Has meaning
- Still basic

**Finally**, you write:
- Combine words into sentences
- Sentences into paragraphs
- Paragraphs into stories

### Same with Skills

**Alphabet** (MVP Skills):
1. text_to_file = A (basic production)
2. structured_generation = B (structure)
3. web_research = C (facts)
4. summarize_knowledge = D (memory)
5. self_check = E (verification)

**Words** (Skill Combinations):
- Research + Save = "CA" (basic workflow)
- Plan + Execute = "BAE" (project workflow)
- Facts + Memory + Verify = "CDE" (knowledge workflow)

**Sentences** (Complex Goals):
- Multi-step research
- Project execution
- Knowledge building

---

## 🎯 Success Criteria

### ✅ System Can

With these 5 skills, system can:
1. **Produce results** (text_to_file)
2. **Plan actions** (structured_generation)
3. **Get facts** (web_research)
4. **Remember** (summarize_knowledge)
5. **Verify quality** (self_check)

### ✅ Goals Can Be Completed

Any atomic goal (L3) can be completed by combining these skills.

### ✅ Artifacts Are Produced

Every skill execution produces tangible, verifiable artifacts.

---

## 📦 What You Get

### Files Created
- `skills/mvp_skills.py` - All 5 skills implemented
- Complete manifests for each skill
- SkillComposer for chaining skills
- Usage examples

### Skills Included
1. ✅ TextToFileSkill
2. ✅ StructuredGenerationSkill
3. ✅ WebResearchSkill
4. ✅ SummarizeKnowledgeSkill
5. ✅ SelfCheckSkill

### Integration
- Works with Skill Registry
- Works with Artifact Layer
- Works with Deterministic Planner
- Verifiable by Verification Engine

---

## 🚀 Next Steps

### After MVP Skills Work

1. **Domain-Specific Skills**
   - code_execution (for programming)
   - data_analysis (for analytics)
   - email_communication (for contacts)

2. **Advanced Combinations**
   - Skill pipelines
   - Parallel execution
   - Conditional flows

3. **Skill Optimization**
   - Performance tracking
   - Success rate analytics
   - Auto-selection improvement

---

## 🎓 Key Principles

### 1. Skills Produce Artifacts
Every skill MUST return artifacts. No exceptions.

### 2. Skills Are Verifiable
Every skill has verification rules in manifest.

### 3. Skills Combine
Skills can be chained to achieve complex goals.

### 4. Skills Are Domain-Agnostic
Core skills work across domains (research, coding, analysis).

### 5. Skills Are Contracts
Manifest defines what skill does, not what it "might do".

---

## 📊 Comparison: Before vs After

### Before (Without MVP Skills)
```
Goal: "Research X"
→ LLM generates text
→ Status: "done"
→ User: "Where's the result?"
```

### After (With MVP Skills)
```
Goal: "Research X"
→ web_research executes
→ Produces: research.md + knowledge chunk
→ summarize_knowledge executes
→ Produces: condensed knowledge
→ text_to_file executes
→ Produces: final_report.md
→ self_check executes
→ Produces: check_result.json (verified)
→ Status: "done" with 5 artifacts
→ User: Opens research.md and final_report.md
```

---

## 💡 Real Example

### Goal: "Research tomato soil nutrition"

```python
# Execute skill chain
results = composer.execute_chain(
    skill_names=[
        "web_research",           # 1. Research
        "summarize_knowledge",    # 2. Condense
        "text_to_file"            # 3. Save report
    ],
    goal_id="G-tomato-001",
    initial_inputs={
        "query": "tomato soil nutrition pH requirements",
        "filename": "tomato_soil_guide.md"
    }
)

# Check results
for result in results:
    print(f"{result.status}: {len(result.artifacts)} artifacts")

# Output:
# success: 2 artifacts (research.md + knowledge)
# success: 1 artifact (condensed knowledge)
# success: 1 artifact (final report)
```

### Dashboard Shows
```
🎯 Research tomato soil nutrition
Status: ✅ DONE

📦 Artifacts (4):
  📄 research.md (web_research) ✅
    └─ min_sources: 5/3 sources
  🧠 knowledge#abc123 (web_research) ✅
  🧠 knowledge#def456 (summarize_knowledge) ✅
  📄 tomato_soil_guide.md (text_to_file) ✅
    └─ file_exists: File exists
    └─ min_length: 1247/200 chars
```

---

## 🎉 Conclusion

**5 Skills = Complete System**

Not just features - the **alphabet**:
- A = text_to_file (production)
- B = structured_generation (reasoning)
- C = web_research (facts)
- D = summarize_knowledge (memory)
- E = self_check (verification)

**With these 5 skills, AI_OS becomes a production system that creates tangible, verifiable results.**

Everything else is built on this foundation.
