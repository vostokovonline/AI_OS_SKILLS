# Evolution System Documentation

## Overview

The Evolution System enables AI-OS to learn from past executions and improve future performance through semantic pattern matching.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EVOLUTION SYSTEM                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐ │
│  │   Goal       │────▶│  Execution   │────▶│   Pattern           │ │
│  │   Input      │     │  Pipeline    │     │   Learning          │ │
│  └──────────────┘     └──────────────┘     └──────────────────────┘ │
│                                                    │                 │
│                              ┌─────────────────────┘                  │
│                              ↓                                        │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐ │
│  │   Planner    │◀────│  Semantic    │◀────│   Pattern           │ │
│  │   (Fallback) │     │  Matcher     │     │   Storage           │ │
│  └──────────────┘     └──────────────┘     └──────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Semantic Matcher (`semantic/matcher.py`)

Finds execution patterns using embedding-based similarity.

**Key Features:**
- Graduated confidence levels (HIGH, MEDIUM, LOW)
- Cosine similarity scoring
- Success rate weighting
- Frequency consideration

**Thresholds:**
```python
HIGH_CONFIDENCE = 0.5     # Use pattern directly
MEDIUM_CONFIDENCE = 0.3   # Validate with planner
MIN_SCORE_THRESHOLD = 0.35
```

### 2. Embedding Service (`semantic/embedding_service.py`)

Generates semantic embeddings for goals and patterns.

**Model:** `all-MiniLM-L6-v2` (384 dimensions)

**Text Processing:**
```python
def build_embedding_text(goal_title, goal_description, skills):
    parts = []
    parts.append(goal_title)
    parts.append(goal_description)
    
    # Skills to natural language
    skill_text = " then ".join([
        s.replace("core.", "").replace("_", " ")
        for s in skills
    ])
    parts.append(f"Steps: {skill_text}")
    
    # Intent hints
    if "research" in skill_text.lower():
        parts.append("finding information")
    if "summarize" in skill_text.lower():
        parts.append("condensing information")
    
    return ". ".join(parts)
```

### 3. Pattern Storage

PostgreSQL table for pattern persistence.

**Schema:**
```sql
CREATE TABLE skill_patterns (
    id UUID PRIMARY KEY,
    pattern_id TEXT UNIQUE,
    skill_sequence JSONB,
    frequency INTEGER,
    avg_success_rate FLOAT,
    embedding JSONB,
    goal_text TEXT,
    discovered_at TIMESTAMP,
    last_seen_at TIMESTAMP
);
```

## Evolution Flow

### 1. Pattern Matching Phase

```
Goal Input
    ↓
build_embedding_text(goal_title, description, [])
    ↓
embed_text() → 384-dim vector
    ↓
Query patterns with embeddings
    ↓
For each pattern:
    - Parse embedding
    - Calculate cosine_similarity(query_emb, pattern_emb)
    - Calculate score
    - Track best pattern
    ↓
Return best pattern with confidence level
```

### 2. Execution Phase

```
Pattern found?
    ↓ yes                    ↓ no
Use pattern skills      Use planner
    ↓                        ↓
Execute pipeline       Generate new pipeline
    ↓                        ↓
Collect artifacts      Execute pipeline
    ↓                        ↓
Log execution pattern  Log new pattern
```

### 3. Learning Phase

```
After execution:
    ↓
_log_execution_pattern()
    ↓
Build embedding text from goal + skills
    ↓
Generate embedding
    ↓
Upsert to skill_patterns table:
    - If pattern exists: increment frequency, update avg_success_rate
    - If new: insert with embedding
```

## Scoring Formula

```
semantic_sim = cosine_similarity(query_emb, pattern_emb)
frequency_score = min(frequency / 10.0, 1.0)
score = semantic_sim × 0.7 + success_rate × 0.2 + frequency_score × 0.1
```

**Weights:**
- Semantic similarity: 70%
- Historical success rate: 20%
- Usage frequency: 10%

## Graduated Confidence

| Confidence | Similarity | Action | Example |
|------------|------------|--------|---------|
| HIGH | ≥ 0.5 | Use pattern directly | "summarize AI news" → research+summarize |
| MEDIUM | 0.3-0.5 | Validate with planner | "find ML papers" → research+summarize (partial match) |
| LOW | < 0.3 | Use planner only | "calculate fibonacci" → no match |

## Quality Filters

Patterns are filtered by:
1. **Has embedding**: `WHERE embedding IS NOT NULL`
2. **Success rate**: `WHERE avg_success_rate >= 0.6`
3. **Not generic**: `AND pattern_id != 'core.echo'`
4. **Limit**: `LIMIT 50` (performance)

## Testing

```bash
# Test semantic matching
docker exec ns_core python -c "
import asyncio
from semantic.matcher import semantic_matcher

async def test():
    result = await semantic_matcher.find_best_pattern(
        'summarize latest AI articles',
        'find and summarize recent AI news'
    )
    return result

result = asyncio.run(test())
if result:
    print(f'Skills: {result[\"skill_sequence\"]}')
    print(f'Score: {result[\"score\"]:.2f}')
    print(f'Confidence: {result[\"confidence\"]}')
"

# Test embedding generation
docker exec ns_core python -c "
from semantic.embedding_service import embed_text, build_embedding_text

text = build_embedding_text('test goal', 'test desc', ['core.web_research'])
emb = embed_text(text)
print(f'Embedding dim: {len(emb)}')
"
```

## Database Queries

```sql
-- Check all patterns
SELECT pattern_id, skill_sequence, frequency, avg_success_rate,
       CASE WHEN embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_emb
FROM skill_patterns;

-- Find patterns by skill
SELECT * FROM skill_patterns 
WHERE skill_sequence @> '["core.web_research"]';

-- Top patterns by success
SELECT * FROM skill_patterns 
WHERE avg_success_rate >= 0.6
ORDER BY frequency DESC, avg_success_rate DESC
LIMIT 10;

-- Similar patterns (requires manual comparison)
SELECT pattern_id, embedding <=> (
    SELECT embedding FROM skill_patterns WHERE pattern_id = 'test_multi_skill_pattern'
) as distance
FROM skill_patterns
WHERE pattern_id != 'test_multi_skill_pattern'
ORDER BY distance
LIMIT 5;
```

## Migration Scripts

### Regenerate Embeddings

```bash
docker cp /tmp/semantic_embeddings.py ns_core:/app/
docker exec ns_core python /app/semantic_embeddings.py
```

### Add Embedding Column

```sql
ALTER TABLE skill_patterns ADD COLUMN IF NOT EXISTS embedding JSONB;
ALTER TABLE skill_patterns ADD COLUMN IF NOT EXISTS goal_text TEXT;
```

## Future Enhancements

1. **pgvector Integration**: Native `<->` operator for similarity
2. **Pattern Clustering**: Auto-group similar patterns
3. **Embedding Index**: HNSW or IVFFlat for fast ANN search
4. **Cross-Instance Learning**: Federated pattern sharing
5. **ML-Based Thresholds**: Learn optimal thresholds from data
