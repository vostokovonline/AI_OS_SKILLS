#!/usr/bin/env bash
set -e

ROOT="/home/onor/ai_os_final"
APP="$ROOT/services/core"
CONTAINER_PATH="/app"

TS=$(date +"%Y%m%d_%H%M%S")
REPORT="/tmp/patch_fix_cfg_scope_report_$TS.txt"

echo "PATCH CFG SCOPE — $TS" | tee "$REPORT"
echo "---------------------------------" | tee -a "$REPORT"

############################
# 1. tasks.py — inject cfg into state
############################

TASKS="$APP/tasks.py"

if [[ -f "$TASKS" ]]; then
  cp "$TASKS" "$TASKS.bak_$TS"

  if grep -q "app_graph.astream" "$TASKS"; then
    sed -i \
      -E 's/app_graph\.astream\(([^,]+),\s*cfg,/app_graph.astream({**\1, "cfg": cfg}, cfg,/g' \
      "$TASKS"

    echo "✔ Patched cfg injection in tasks.py" | tee -a "$REPORT"
  else
    echo "⚠ app_graph.astream not found in tasks.py" | tee -a "$REPORT"
  fi
else
  echo "❌ tasks.py not found" | tee -a "$REPORT"
fi

############################
# 2. agent_graph.py — harden supervisor_node
############################

GRAPH="$APP/agent_graph.py"

if [[ -f "$GRAPH" ]]; then
  cp "$GRAPH" "$GRAPH.bak_$TS"

  if grep -q "def supervisor_node" "$GRAPH"; then
    sed -i \
      '/def supervisor_node/{n; a\
    cfg = state.get("cfg", {})\
    limits = cfg.get("limits", {})\
}' \
      "$GRAPH"

    echo "✔ Hardened supervisor_node with state['cfg']" | tee -a "$REPORT"
  else
    echo "⚠ supervisor_node not found" | tee -a "$REPORT"
  fi
else
  echo "❌ agent_graph.py not found" | tee -a "$REPORT"
fi

############################
# 3. Final report
############################

echo "---------------------------------" | tee -a "$REPORT"
echo "DONE. Restart containers." | tee -a "$REPORT"

echo ""
echo "👉 To apply:"
echo "docker compose restart core core_worker"
echo ""
echo "👉 Report:"
echo "$REPORT"
