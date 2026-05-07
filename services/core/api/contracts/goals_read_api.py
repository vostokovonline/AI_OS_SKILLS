# Goals Read API Contract

## Canonical Endpoint
```
GET /api/v1/goals
```

## Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| cursor | string | null | Pagination cursor (created_at_id format) |
| limit | int | 50 | Max items per request (max: 100) |
| status | string | null | Filter: pending, active, done, blocked, archived |
| goal_type | string | null | Filter: achievable, continuous, directional, exploratory, meta |
| is_atomic | bool | null | Filter: atomic vs non-atomic goals |
| include_archived | bool | **false** | Include archived goals (default: NO) |
| created_after | datetime | null | Filter: goals created after this date |
| created_before | datetime | null | Filter: goals created before this date |
| order_by | string | created_at | Sort: created_at, updated_at, title, status |
| order_dir | string | desc | Sort direction: asc, desc |

## Response Schema

```json
{
  "goals": [
    {
      "id": "uuid",
      "parent_id": "uuid|null",
      "title": "string",
      "description": "string|null",
      "status": "pending|active|done|blocked|archived",
      "progress": 0.0-1.0,
      "goal_type": "achievable|continuous|directional|exploratory|meta",
      "depth_level": 0-3,
      "is_atomic": true|false,
      "created_at": "ISO8601",
      "updated_at": "ISO8601"
    }
  ],
  "pagination": {
    "next_cursor": "2026-04-18T20:00:00Z_uuid|null",
    "has_more": true|false,
    "total_count": 2457
  },
  "filters_applied": {
    "status": "active|null",
    "goal_type": "null",
    "include_archived": false
  }
}
```

## Cursor Format
```
{created_at ISO8600}_{goal_id uuid}
```

Example: `2026-04-18T20:00:00Z_a1b2c3d4-...`

## Default Behavior (IMPORTANT)
- **exclude archived by default** - `include_archived=false` is the default
- **limit max 100** - prevent UI from choking
- **status filter** - if not specified, shows pending + active + done (not archived)
- **created_at ordering** - descending by default (newest first)

## Deprecated Endpoints (to be removed)
1. `/goals/list` (main.py) - replace with /api/v1/goals
2. `/goals/list` (api/endpoints) - replace with /api/v1/goals  
3. `/api/goals` (dashboard compatibility) - replace with /api/v1/goals

## Migration Path
1. Create `/api/v1/goals` with new contract
2. Update dashboard to use new endpoint
3. Add deprecation headers to old endpoints
4. Remove old endpoints after dashboard migration