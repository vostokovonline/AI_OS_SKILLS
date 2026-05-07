#!/usr/bin/env bash
set -e

ROOT="/home/onor/ai_os_final"
TASKS="$ROOT/services/core/tasks.py"
TS=$(date +"%Y%m%d_%H%M%S")
REPORT="/tmp/patch_fix_cfg_scope_v3_$TS.txt"

echo "PATCH CFG SCOPE v3 — $TS" | tee "$REPORT"
echo "---------------------------------" | tee -a "$REPORT"

if [[ ! -f "$TASKS" ]]; then
  echo "❌ tasks.py not found at $TASKS" | tee -a "$REPORT"
  exit 1
fi

cp "$TASKS" "$TASKS.bak_$TS"

# Проверка: используется ли cfg вообще
if ! grep -q "cfg" "$TASKS"; then
  echo "⚠ cfg not referenced in tasks.py — nothing to patch" | tee -a "$REPORT"
  exit 0
fi

# Проверка: определён ли cfg
if grep -q "cfg *= *{" "$TASKS"; then
  echo "✔ cfg already defined — skipping" | tee -a "$REPORT"
  exit 0
fi

# Вставляем cfg сразу после sid =
awk '
/sid *=/ && !done {
  print
  print "    cfg = {\"configurable\": {\"thread_id\": sid}}"
  done=1
  next
}
{print}
' "$TASKS" > "$TASKS.tmp"

mv "$TASKS.tmp" "$TASKS"

echo "✔ cfg injected successfully" | tee -a "$REPORT"
echo "---------------------------------" | tee -a "$REPORT"
echo "DONE" | tee -a "$REPORT"

echo ""
echo "👉 Rebuild & restart REQUIRED:"
echo "docker compose build core core_worker"
echo "docker compose up -d"
echo ""
echo "👉 Report:"
echo "$REPORT"
	
