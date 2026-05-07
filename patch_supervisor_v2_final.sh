#!/usr/bin/env bash
set -e

ROOT="$HOME/ai_os_final"
TS=$(date +%Y%m%d_%H%M%S)
REPORT="/tmp/patch_supervisor_v2_report_$TS.txt"

exec > >(tee "$REPORT") 2>&1

echo "PATCH SUPERVISOR v2 — $TS"
echo "---------------------------------"

# ---------- 1. SCHEMA ----------
SCHEMA_DIR="$ROOT/services/core/schemas/goals"

mkdir -p "$SCHEMA_DIR"
echo "✔ Created schema dir"

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

echo "✔ Goal schema written"

# ---------- 2. SUPERVISOR ----------
SUPERVISOR="$ROOT/services/core/agent_graph.py"

if [ ! -f "$SUPERVISOR" ]; then
  echo "❌ agent_graph.py not found — skipping supervisor patch"
  exit 0
fi

cp "$SUPERVISOR" "$SUPERVISOR.bak_$TS"
echo "✔ Backup created: agent_graph.py.bak_$TS"

python3 <<EOF
from pathlib import Path
import re

path = Path("$SUPERVISOR")
text = path.read_text()

if "async def supervisor_node" not in text:
    print("❌ supervisor_node not found — aborting patch")
    raise SystemExit(0)

new_impl = '''
async def supervisor_node(state):
    goals = state.get("goals", [])

    if not goals:
        state.setdefault("messages", []).append("No goals defined.")
        return state

    active = next((g for g in goals if g.get("status") == "active"), None)

    if not active:
        pending = next((g for g in goals if g.get("status") == "pending"), None)
        if not pending:
            state.setdefault("messages", []).append("All goals completed.")
            return state
        pending["status"] = "active"
        active = pending

    if active.get("type") == "bounded":
        action = f"Execute final step for goal: {active.get('title')}"
        active["status"] = "done"
    else:
        action = f"Incremental improvement for system goal: {active.get('title')}"

    state.setdefault("messages", []).append(action)
    return state
'''

patched, n = re.subn(
    r"async def supervisor_node\\(state\\):[\\s\\S]*?return state",
    new_impl.strip(),
    text,
    count=1
)

if n == 0:
    print("❌ Failed to patch supervisor_node (pattern not matched)")
else:
    path.write_text(patched)
    print("✔ Supervisor v2 successfully injected")
EOF

echo "---------------------------------"
echo "DONE — report saved to $REPORT"
