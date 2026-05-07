#!/bin/bash

# Скрипт для автоматического запуска pending целей
# Использование: ./resume_pending_goals.sh

API_URL="http://localhost:8000"
LOG_FILE="/home/onor/ai_os_final/logs_auto_resume.log"

echo "===========================================" | tee -a "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Checking for pending goals..." | tee -a "$LOG_FILE"

# Получаем список pending целей
pending_goals=$(curl -s "$API_URL/goals/list" | jq -r '.goals[] | select(.status=="pending") | .id')

if [ -z "$pending_goals" ]; then
    echo "No pending goals found." | tee -a "$LOG_FILE"
    exit 0
fi

# Подсчет количества
count=$(echo "$pending_goals" | wc -l)
echo "Found $count pending goal(s). Starting execution..." | tee -a "$LOG_FILE"

# Запускаем каждую цель
started=0
failed=0

for goal_id in $pending_goals; do
    echo "→ Executing goal: $goal_id" | tee -a "$LOG_FILE"

    response=$(curl -s -X POST "$API_URL/goals/execute" \
        -H "Content-Type: application/json" \
        -d "{\"goal_id\": \"$goal_id\"}")

    status=$(echo "$response" | jq -r '.status // "error"')

    if [ "$status" == "success" ]; then
        echo "  ✅ Started successfully" | tee -a "$LOG_FILE"
        ((started++))
    else
        echo "  ❌ Failed to start: $response" | tee -a "$LOG_FILE"
        ((failed++))
    fi
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"
echo "Summary: $started started, $failed failed" | tee -a "$LOG_FILE"
echo "===========================================" | tee -a "$LOG_FILE"

exit 0
