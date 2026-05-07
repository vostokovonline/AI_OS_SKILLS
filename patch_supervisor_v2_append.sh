#!/usr/bin/env bash
set -e

ROOT="$HOME/ai_os_final"
TS=$(date +%Y%m%d_%H%M%S)
REPORT="/tmp/patch_supervisor_v2_append_$TS.txt"

exec > >(tee "$REPORT") 2>&1

SUPERVISOR="$ROOT/services/core/agent_graph.py"

echo "PATCH SUPERVISOR v2 (APPEND MODE) — $TS"
echo "---------------------------------"

if [ ! -f "$SUPERVISOR" ]; then
  echo "❌ agent_graph.py not found"
  exit 0
fi

cp "$SUPERVISOR" "$SUPERVISOR.bak_$TS"
echo "✔ Backup created: agent_graph.py.bak_$TS"

python3 <<EOF
from pathlib import Path

path = Path("$SUPERVISOR")
text = path.read_text()

if "def supervisor_v2" in text:
    print("⚠ supervisor_v2 already exists — skipping append")
    raise SystemExit(0)

block = '''
# ==============================
# Supervisor v2 — Goal-driven, no recursion
# ==============================

async def supervisor_v2(state):
    goals = state.get("goals", [])

    if not goals:
        state.setdefault("messages", []).append(
            "Supervisor: no goals defined."
        )
        return state

    active = next((g for g in goals if g.get("status") == "active"), None)

    if not active:
        pending = next((g for g in goals if g.get("status") == "pending"), None)
        if not pending:
            state.setdefault("messages", []).append(
                "Supervisor: all goals completed."
            )
            return state
        pending["status"] = "active"
        active = pending

    if active.get("type") == "bounded":
        action = f"[GOAL DONE] {active.get('title')}"
        active["status"] = "done"
    else:
        action = f"[SYSTEM GOAL STEP] {active.get('title')}"

    state.setdefault("messages", []).append(action)
    return state
'''

text += "\\n\\n" + block
path.write_text(text)

print("✔ supervisor_v2 appended")

# --- Try to rewire graph ---
if "add_node(\"Supervisor\"" in text:
    print("⚠ Graph wiring not auto-modified — manual check required")
else:
    print("ℹ Could not detect graph wiring location")
EOF

echo "---------------------------------"
echo "DONE — report: $REPORT"
