#!/bin/bash

# Скрипт для настройки cron для автоматического запуска pending целей
# Добавляет задачу в crontab для выполнения каждые 5 минут

CRON_JOB="*/5 * * * * /home/onor/ai_os_final/scripts/resume_pending_goals.sh"
CRON_TMP="/tmp/cron_tmp"

echo "Setting up auto-resume cron job..."
echo "Cron job: $CRON_JOB"

# Проверяем, существует ли уже задача
current_cron=$(crontab -l 2>/dev/null || echo "")

if echo "$current_cron" | grep -q "resume_pending_goals.sh"; then
    echo "⚠️  Cron job already exists. Removing old entry..."
    current_cron=$(echo "$current_cron" | grep -v "resume_pending_goals.sh")
fi

# Добавляем новую задачу
echo "$current_cron" > "$CRON_TMP"
echo "$CRON_JOB" >> "$CRON_TMP"

# Устанавливаем новый crontab
crontab "$CRON_TMP"
rm "$CRON_TMP"

echo "✅ Cron job installed successfully!"
echo ""
echo "Current crontab:"
crontab -l | grep -E "(resume_pending_goals|# m h  dom mon dow|hourly|PATH)"
echo ""
echo "To view full crontab: crontab -l"
echo "To remove: crontab -e (delete the line with resume_pending_goals.sh)"
