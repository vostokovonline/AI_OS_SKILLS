# API Reference

## Goals API

### Create Goal

```bash
POST /goals/create
```

**Request:**
```json
{
  "title": "Research latest AI news",
  "description": "Find and summarize recent AI articles",
  "goal_type": "achievable",
  "is_atomic": true,
  "parent_id": "uuid-optional",
  "domains": ["research", "ai"]
}
```

**Response:**
```json
{
  "id": "uuid",
  "title": "Research latest AI news",
  "status": "create",
  "goal_type": "achievable",
  "is_atomic": true,
  "created_at": "2026-03-22T10:00:00Z"
}
```

### Execute Goal

```bash
POST /goals/{goal_id}/execute
```

**Response:**
```json
{
  "execution_id": "uuid",
  "status": "executing",
  "skills_used": ["core.web_research", "core.summarize_text"],
  "artifacts": [...]
}
```

### List Goals

```bash
GET /goals/list?status=active&limit=50&offset=0
```

**Response:**
```json
{
  "goals": [...],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

### Get Goal Tree

```bash
GET /goals/{goal_id}/tree
```

**Response:**
```json
{
  "goal": {
    "id": "uuid",
    "title": "Parent Goal",
    "children": [
      {
        "id": "uuid",
        "title": "Child Goal 1",
        "children": []
      }
    ]
  }
}
```

## Semantic Memory API

### Find Patterns

```bash
GET /semantic/find-pattern?title=summarize%20AI%20news&description=find%20and%20summarize
```

**Response:**
```json
{
  "pattern_id": "test_multi_skill_pattern",
  "skill_sequence": ["core.web_research", "core.summarize_text"],
  "semantic_similarity": 0.42,
  "confidence": "medium",
  "score": 0.50
}
```

### Get All Patterns

```bash
GET /semantic/patterns?limit=50&offset=0
```

**Response:**
```json
{
  "patterns": [
    {
      "pattern_id": "test_multi_skill_pattern",
      "skill_sequence": ["core.web_research", "core.summarize_text"],
      "frequency": 3,
      "avg_success_rate": 0.85,
      "has_embedding": true
    }
  ],
  "total": 16
}
```

### Pattern Statistics

```bash
GET /semantic/stats
```

**Response:**
```json
{
  "total_patterns": 16,
  "patterns_with_embeddings": 16,
  "avg_frequency": 2.5,
  "avg_success_rate": 0.78,
  "top_skills": ["core.web_research", "core.summarize_text", "core.echo"]
}
```

## LLM API

### Check LLM Status

```bash
GET /llm/status
```

**Response:**
```json
{
  "primary": "groq",
  "status": "active",
  "model": "qwen2.5-coder:latest",
  "groq_cooldown": {
    "active": false,
    "remaining_hours": 0
  }
}
```

### Reset Groq

```bash
POST /llm/reset_groq
```

**Response:**
```json
{
  "status": "reset",
  "message": "Groq cooldown cleared"
}
```

### LLM Decision Trace

```bash
GET /llm/control/decision/trace?goal_type=precise_reasoning
```

**Response:**
```json
{
  "recommended_model": "deepseek-v3.1:671b-cloud",
  "decision_trace": {
    "goal_type": "precise_reasoning",
    "weights": {
      "success": 0.6,
      "cost": 0.2,
      "latency": 0.2
    },
    "scores": {
      "qwen2.5-coder:latest": 0.82,
      "deepseek-v3.1:671b-cloud": 0.78
    }
  }
}
```

## Artifacts API

### Get Artifacts

```bash
GET /artifacts?goal_id={goal_id}&limit=50&offset=0
```

**Response:**
```json
{
  "artifacts": [
    {
      "id": "uuid",
      "goal_id": "uuid",
      "type": "FILE",
      "content_kind": "report",
      "content_location": "/tmp/report.md",
      "verification_status": "passed",
      "created_at": "2026-03-22T10:05:00Z"
    }
  ],
  "total": 1
}
```

## Alerts API

### Get Alerts

```bash
GET /alerts?status=active&limit=50
```

**Response:**
```json
{
  "alerts": [
    {
      "id": "uuid",
      "type": "performance",
      "severity": "warning",
      "message": "High latency detected",
      "created_at": "2026-03-22T09:00:00Z"
    }
  ]
}
```

### Get Alert Summary

```bash
GET /alerts/summary
```

**Response:**
```json
{
  "total": 5,
  "by_severity": {
    "critical": 0,
    "warning": 3,
    "info": 2
  },
  "by_type": {
    "performance": 3,
    "safety": 1,
    "capacity": 1
  }
}
```

## Interventions API

### Get Intervention Candidates

```bash
GET /interventions/candidates
```

**Response:**
```json
{
  "candidates": [
    {
      "id": "uuid",
      "goal_id": "uuid",
      "intervention_type": "budget_adjustment",
      "current_value": 100,
      "suggested_value": 150,
      "confidence": 0.82
    }
  ]
}
```

### Approve Intervention

```bash
POST /interventions/{id}/approve
```

**Response:**
```json
{
  "status": "approved",
  "applied_change": "budget increased to 150"
}
```

## Health API

### Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "3.0",
  "services": {
    "database": "up",
    "redis": "up",
    "llm": "up"
  }
}
```

### Memory Health

```bash
GET /memory/health
```

**Response:**
```json
{
  "status": "healthy",
  "postgres": "up",
  "neo4j": "up",
  "milvus": "up"
}
```

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Dependency down |

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/goals/create` | 100/min |
| `/goals/execute` | 50/min |
| `/llm/*` | 200/min |
| `/semantic/*` | 500/min |
