#!/usr/bin/env bash
set -e

ROOT="/home/onor/ai_os_final"
TASKS="$ROOT/services/core/tasks.py"
REPORT="/tmp/patch_tasks_v3_$(date +%s).log"

log() { echo "$1" | tee -a "$REPORT"; }

log "PATCH tasks.py v3 — $(date)"
log "---------------------------------"

if [ ! -f "$TASKS" ]; then
  log "❌ tasks.py not found, abort"
  exit 1
fi

cp "$TASKS" "$TASKS.bak_$(date +%s)"
log "📦 Backup created"

cat > "$TASKS" <<'EOF'
"""
SUPERVISOR TASKS — NON RECURSIVE
"""
from celery import shared_task
from core.llm.client import call_llm
from core.llm.schema_loader import load_schema
from core.llm.schema_validator import validate_or_fail

PLAN_SCHEMA = load_schema("plan.schema.json")

@shared_task(bind=True)
def run_goal_plan(self, goal: dict):
    """
    Entry point: Goal already classified (bounded/systemic)
    """
    plan = _generate_plan(goal)
    validate_or_fail(plan, PLAN_SCHEMA, "PLAN")

    results = []
    for task in plan["tasks"]:
        results.append(_execute_task(task))

    return {
        "goal_id": goal["id"],
        "status": "completed",
        "tasks_executed": len(results),
        "results": results
    }

def _generate_plan(goal: dict) -> dict:
    """
    SINGLE LLM CALL
    """
    response = call_llm(
        messages=[
            {"role": "system", "content": "You are a planner. Output JSON only."},
            {"role": "user", "content": str(goal)}
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "plan",
                "schema": PLAN_SCHEMA
            }
        }
    )
    return response["choices"][0]["message"]["content"]

def _execute_task(task: dict):
    """
    ATOMIC execution stub
    """
    return {
        "task_id": task["id"],
        "action": task["action"],
        "status": "done"
    }
EOF

log "✔ tasks.py replaced with non-recursive supervisor"
log "DONE"
echo
cat "$REPORT"
