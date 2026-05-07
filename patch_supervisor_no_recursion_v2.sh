#!/usr/bin/env bash
set -e

ROOT="/home/onor/ai_os_final"
REPORT="/tmp/patch_report_$(date +%Y%m%d_%H%M%S).txt"

log() {
  echo "$1"
  echo "$1" >> "$REPORT"
}

backup() {
  if [ -f "$1" ]; then
    cp "$1" "$1.bak_$(date +%s)"
    log "📦 Backup created: $1"
  fi
}

log "PATCH REPORT — $(date)"
log "---------------------------------"

############################################
# 1. SCHEMAS
############################################

SCHEMA_DIR="$ROOT/services/core/schemas"
mkdir -p "$SCHEMA_DIR"
log "✔ Ensured schema directory: $SCHEMA_DIR"

cat > "$SCHEMA_DIR/goal.schema.json" <<'EOF'
{
  "type": "object",
  "required": ["id", "title", "type", "policy"],
  "properties": {
    "id": { "type": "string" },
    "title": { "type": "string" },
    "type": { "enum": ["bounded", "systemic"] },
    "policy": { "$ref": "policy.schema.json" }
  }
}
EOF
log "✔ goal.schema.json written"

cat > "$SCHEMA_DIR/policy.schema.json" <<'EOF'
{
  "type": "object",
  "required": ["max_depth", "max_tasks", "max_goals"],
  "properties": {
    "max_depth": { "type": "integer", "minimum": 0 },
    "max_tasks": { "type": "integer", "minimum": 0 },
    "max_goals": { "type": "integer", "minimum": 0 },
    "cadence_days": { "type": "integer", "minimum": 1 }
  }
}
EOF
log "✔ policy.schema.json written"

cat > "$SCHEMA_DIR/plan.schema.json" <<'EOF'
{
  "type": "object",
  "required": ["goal_id", "tasks"],
  "properties": {
    "goal_id": { "type": "string" },
    "tasks": {
      "type": "array",
      "maxItems": 10,
      "items": {
        "type": "object",
        "required": ["id", "action"],
        "properties": {
          "id": { "type": "string" },
          "action": { "type": "string" }
        }
      }
    }
  }
}
EOF
log "✔ plan.schema.json written"

############################################
# 2. SCHEMA LOADER + VALIDATOR
############################################

LLM_DIR="$ROOT/services/core/llm"
mkdir -p "$LLM_DIR"

cat > "$LLM_DIR/schema_loader.py" <<'EOF'
import json
from pathlib import Path

BASE = Path(__file__).parent.parent / "schemas"

def load_schema(name: str):
    path = BASE / name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    with open(path) as f:
        return json.load(f)
EOF
log "✔ schema_loader.py created"

cat > "$LLM_DIR/schema_validator.py" <<'EOF'
from jsonschema import validate, ValidationError

def validate_or_fail(data, schema, label="schema"):
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        raise RuntimeError(f"❌ {label} validation failed: {e.message}")
EOF
log "✔ schema_validator.py created"

############################################
# 3. PATCH llm/client.py
############################################

CLIENT="$LLM_DIR/client.py"

if [ -f "$CLIENT" ]; then
  backup "$CLIENT"

  if ! grep -q "schema_loader" "$CLIENT"; then
    cat >> "$CLIENT" <<'EOF'

# === JSON SCHEMA ENFORCEMENT ===
from core.llm.schema_loader import load_schema
from core.llm.schema_validator import validate_or_fail
EOF
    log "✔ Injected schema imports into client.py"
  else
    log "ℹ client.py already contains schema logic"
  fi
else
  log "❌ client.py not found — skipped"
fi

############################################
# 4. PATCH tasks.py (SUPERVISOR STOP)
############################################

TASKS="$ROOT/services/core/tasks.py"

if [ -f "$TASKS" ]; then
  backup "$TASKS"

  if grep -q "recursion" "$TASKS"; then
    sed -i '/recursion/d' "$TASKS"
    log "✔ Removed recursion references in tasks.py"
  fi

  if ! grep -q "STOP AFTER PLAN" "$TASKS"; then
    cat >> "$TASKS" <<'EOF'

# === STOP AFTER PLAN (ANTI-RECURSION GUARD) ===
def _stop_after_plan(plan):
    if not plan or not plan.get("tasks"):
        return True
    return False
EOF
    log "✔ Added STOP guard to tasks.py"
  fi
else
  log "❌ tasks.py not found — skipped"
fi

############################################
# 5. FINAL REPORT
############################################

log "---------------------------------"
log "DONE"
log ""
log "👉 Next steps:"
log "1. Add jsonschema to services/core/requirements.txt"
log "2. docker compose build core core_worker"
log "3. Restart stack"
log ""
log "Test:"
log "docker exec -i ns_core_worker python - <<'EOF'"
log "from core.llm.schema_loader import load_schema"
log "print(load_schema('plan.schema.json').keys())"
log "EOF"

echo
cat "$REPORT"
	
