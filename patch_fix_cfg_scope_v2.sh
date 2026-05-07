#!/usr/bin/env bash
set -e

ROOT="/home/onor/ai_os_final"
TASKS="$ROOT/services/core/tasks.py"
TS=$(date +"%Y%m%d_%H%M%S")
REPORT="/tmp/patch_fix_cfg_scope_v2_$TS.txt"

echo "PATCH CFG SCOPE v2 — $TS" | tee "$REPORT"
echo "---------------------------------" | tee -a "$REPORT"

if [[ ! -f "$TASKS" ]]; then
  echo "❌ tasks.py not found" | tee -a "$REPORT"
  exit 1
fi

cp "$TASKS" "$TASKS.bak_$TS"

# Проверяем, используется ли cfg
if ! grep -q "astream(inputs, cfg" "$TASKS"; then
  echo "⚠ cfg not used in astream — nothing to patch" | tee -a "$REPORT"
  exit 0
fi

# Проверяем, определён ли cfg
if grep -q "^ *cfg *= *" "$TASKS"; then
  echo "✔ cfg already defined — skipping" | tee -a "$REPORT"
  exit 0
fi

# Вставляем cfg сразу после sid
awk '
/sid *=/ {
  print
  print "    cfg = {\"configurable\": {\"thread_id\": sid}}"
  next
}
{print}
' "$TASKS" > "$TASKS.tmp"

mv "$TASKS.tmp" "$TASKS"

echo "✔ cfg defined safely in tasks.py" | tee -a "$REPORT"
echo "---------------------------------" | tee -a "$REPORT"
echo "DONE" | tee -a "$REPORT"

echo ""
echo "👉 Restart:"
echo "docker compose restart core core_worker"
echo ""
echo "👉 Report:"
echo "$REPORT"
	
