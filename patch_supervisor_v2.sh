#!/usr/bin/env bash
set -e

ROOT="/home/onor/ai_os_final"
TS=$(date +%Y%m%d_%H%M%S)
REPORT="/tmp/patch_supervisor_v2_report_$TS.txt"

echo "PATCH SUPERVISOR v2 — $TS" | tee "$REPORT"
echo "---------------------------------" | tee -a "$REPORT"

### 1. SCHEMAS
SCHEMA_DIR="$ROOT/services/core/schemas/goals"
mkdir -p "$SCHEMA_DIR" && echo "✔ Created schema dir" | tee -a "$REPORT"

cat > "$SCHEMA_DIR/goal.schema.json" <<'EOF'
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Goal",
  "type": "object",
  "required": ["id", "title", "type", "status"],
  "properties": {
    "id": { "type": "string" },
    "title": { "type": "string" },
    "type": { "enum": ["bounded", "systemic"] },
    "status": { "enum": ["pending", "active", "done", "blocked"] },
    "parent_id": { "type": ["string", "null"] },
    "depth": { "type": "integer", "minimum": 0 }
  }
}
EOF

echo "✔ Goal schema written" | tee -a "$REPORT"

### 2. SUPERVISOR PATCH
SUPERVISOR="$ROOT/services/core/agent_graph.py"

if [ ! -f "$SUPERVISOR" ]; then
  echo "❌ agent_graph.py not found — abort supervisor patch" | tee -a "$REPORT"
  exit 0
fi

cp "$SUPERVISOR" "$SUPERVISOR.bak_$TS"
echo "✔ Backup created" | tee -a "$REPORT"

python <<EOF
from pathlib import Path

p = Path("$SUPERVISOR")
text = p.read_text()

if "supervisor_node" not in text:
    print("❌ supervisor_node not found")
    exit(0)

new = '''
async def supervisor_node(state):
    goals = state.get("goals", [])

    if not goals:
        return {"messages": state.get("messages", []) + ["No goals defined."], "status": "idle"}

    active = next((g for g in goals if g.get("status") == "active"), None)

    if not active:
        pending = next((g for g in goals if g.get("status") == "pending"), None)
        if not pending:
            return {"status": "done"}
        pending["status"] = "active"
        active = pending

    if active.get("type") == "bounded":
        action = f"Execute final step for goal: {active.get('title')}"
        active["status"] = "done"
    else:
        action = f"Improve system goal incrementally: {active.get('title')}"

    state.setdefault("messages", []).append(action)
    return state
'''

import re
patched = re.sub(
    r"async def supervisor_node\\(state\\):[\\s\\S]*?return .*",
    new.strip(),
    text,
    count=1
)

p.write_text(patched)
print("✔ Supervisor v2 injected")
EOF | tee -a "$REPORT"

echo "---------------------------------" | tee -a "$REPORT"
echo "DONE — Review report at $REPORT"
