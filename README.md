# AI-OS - Self-Improving Goal Execution System v3.0

**Autonomous goal-execution system powered by AI agents with semantic memory**

AI-OS is a sophisticated multi-level goal management system that decomposes high-level goals into atomic subgoals, executes them through specialized AI agents, and learns from execution patterns for continuous improvement.

## 🏗️ Architecture

### Core Services

| Service | Port | Purpose |
|---------|------|---------|
| ns_core | 8000 | FastAPI: goal management, execution API |
| ns_core_worker | - | Celery worker for async tasks |
| ns_postgres | 5432 | PostgreSQL with audit trail |
| ns_redis | 6379 | Redis for Celery + caching |
| ns_litellm | 4000 | LLM proxy (Groq, Ollama, OpenAI) |
| ns_memory | 8001 | Neo4j + Milvus for memory |
| dashboard_v2 | 3000 | React dashboard |
| Temporal.io | 8088 | Continuous goal workflows |

### Goal System v3.0

```
Mission (L0) → Strategic (L1) → Operational (L2) → Tactical/Atomic (L3)
```

**Key Features:**
- **Semantic Memory**: Pattern-based execution with embeddings
- **Unit of Work Pattern**: Transaction management with atomic operations
- **Goal State Transitions**: All state changes through `transition_goal()`
- **Audit Trail**: Every transition logged
- **Belief Model v1.0**: Epistemic state with support/confidence
- **Decision Engine v4.0**: Arbitration, regret analysis, safe auto-tuning

## 🧠 Semantic Memory System

### How It Works

```
Goal Input
    ↓
Semantic Embedding (all-MiniLM-L6-v2, 384 dims)
    ↓
Pattern Matching (cosine similarity)
    ↓
Graduated Confidence Scoring
    ↓
Skill Pipeline Selection
    ↓
Execution → Learning → Pattern Storage
```

### Graduated Matching Confidence

| Confidence | Similarity | Action |
|------------|------------|--------|
| HIGH | ≥ 0.5 | Use pattern directly |
| MEDIUM | 0.3 - 0.5 | Validate with planner |
| LOW | < 0.3 | Use planner only |

### Scoring Formula

```
score = semantic_similarity × 0.7 + success_rate × 0.2 + frequency × 0.1
```

### Example

**Goal**: "summarize latest AI articles"

**Matched Pattern**: `["core.web_research", "core.summarize_text"]`

**Scores**:
- Semantic similarity: 0.42
- Success rate: 0.85
- Frequency: 3
- **Total: 0.50** → MEDIUM confidence

## 🔄 Evolution Loop

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Execute    │───▶│   Learn     │───▶│   Match     │
│  Pipeline   │    │   Pattern   │    │   Next      │
└─────────────┘    └─────────────┘    └─────────────┘
      │                                    │
      └────────────────────────────────────┘
                      │
              Pattern Storage (PostgreSQL)
```

### Pattern Structure

```sql
CREATE TABLE skill_patterns (
    id UUID PRIMARY KEY,
    pattern_id TEXT UNIQUE,
    skill_sequence JSONB,      -- ["core.web_research", "core.summarize_text"]
    frequency INTEGER,
    avg_success_rate FLOAT,
    embedding JSONB,           -- 384-dim vector
    goal_text TEXT,
    discovered_at TIMESTAMP,
    last_seen_at TIMESTAMP
);
```

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/onor/ai-os-final.git
cd ai-os-final

# Start services
docker-compose up -d

# Check status
make status
```

### Create and Execute Goal

```bash
# Create atomic goal
curl -X POST http://localhost:8000/goals/create \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Research latest AI news",
    "description": "Find and summarize recent AI articles",
    "goal_type": "achievable",
    "is_atomic": true
  }'

# Execute goal
curl -X POST http://localhost:8000/goals/{goal_id}/execute
```

### Dashboard

- **URL**: http://localhost:3000
- **Features**: Goal graph, timeline, dependency tree, autonomy panel

## 📊 Monitoring

### Logs

```bash
# Core service logs
make logs

# Worker logs
make logs-worker
```

### Database

```bash
# PostgreSQL shell
make db-shell

# Check patterns
psql> SELECT pattern_id, skill_sequence, frequency FROM skill_patterns;

# Check embeddings
psql> SELECT pattern_id, embedding IS NOT NULL as has_emb FROM skill_patterns;
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/goals/create` | POST | Create new goal |
| `/goals/{id}/execute` | POST | Execute goal |
| `/goals/list` | GET | List all goals |
| `/llm/status` | GET | Check LLM status |
| `/memory/stats` | GET | Memory statistics |

## 🔧 Configuration

### Environment Variables

```bash
# Database
POSTGRES_USER=ns_admin
POSTGRES_PASSWORD=your_password
POSTGRES_DB=ns_core_db

# LLM
LLM_MODEL=cloud-reasoner
FALLBACK_MODEL=ollama/qwen2.5-coder:latest
GROQ_COOLDOWN_HOURS=6

# Semantic Matching
SEMANTIC_MODEL=all-MiniLM-L6-v2
MIN_SEMANTIC_SIMILARITY=0.35
MIN_SCORE_THRESHOLD=0.35
```

### Matcher Configuration

Located in `services/core/semantic/matcher.py`:

```python
class SemanticMatcher:
    HIGH_CONFIDENCE = 0.5    # Direct use
    MEDIUM_CONFIDENCE = 0.3  # Validate with planner
    MIN_SCORE_THRESHOLD = 0.35
    MAX_PATTERNS_TO_CHECK = 50
```

## 🧪 Testing

```bash
# Unit tests
make test-unit

# Integration tests  
make test-e2e

# All tests
make test-all
```

### Manual Pattern Testing

```python
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
print(f'Skills: {result[\"skill_sequence\"]}')
print(f'Score: {result[\"score\"]}')
print(f'Confidence: {result[\"confidence\"]}')
"
```

## 📈 Performance

### Benchmarks

| Operation | Latency |
|------------|----------|
| Embedding generation | ~30ms |
| Pattern matching (50 patterns) | ~100ms |
| Full goal execution | 5-30s |

### Optimization Tips

1. **Limit pattern checks**: `MAX_PATTERNS_TO_CHECK = 50`
2. **Cache embeddings**: SentenceTransformer loaded once
3. **Filter by success rate**: `WHERE avg_success_rate >= 0.6`
4. **pgvector**: Native vector similarity in SQL (planned)

## 📁 Project Structure

```
/home/onor/ai_os_final/
├── services/
│   ├── core/
│   │   ├── main.py                 # FastAPI endpoints
│   │   ├── goal_executor_v2.py     # Execution engine
│   │   ├── semantic/
│   │   │   ├── embedding_service.py # Embedding generation
│   │   │   └── matcher.py          # Pattern matching
│   │   ├── canonical_skills/       # Built-in skills
│   │   └── models.py               # Database models
│   └── dashboard_v2/               # React dashboard
├── tests/
│   ├── unit/
│   └── integration/
└── Makefile
```

## 🔮 Roadmap

- [ ] **pgvector Integration**: Native vector similarity in SQL
- [ ] **Pattern Clustering**: Auto-group similar patterns
- [ ] **Knowledge Graph**: Neo4j for pattern relationships
- [ ] **Federated Learning**: Share patterns across instances
- [ ] **Auto-Tuning**: ML-based threshold optimization

## 🤝 Contributing

1. Fork repository
2. Create feature branch
3. Implement changes
4. Add tests
5. Submit PR

## 📄 License

MIT License

## 🙏 Built With

- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Agent orchestration
- [PostgreSQL](https://www.postgresql.org/) - Database
- [Redis](https://redis.io/) - Caching & queues
- [SentenceTransformers](https://www.sbert.net/) - Embeddings
- [React](https://react.dev/) - Dashboard UI
