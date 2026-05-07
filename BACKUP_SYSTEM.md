# AI-OS Backup System

Автоматическая система резервного копирования целей и результатов работы AI-OS.

## 📁 Что backing up

- **Goals** - все цели системы (включая статусы, прогресс, parent-child связи)
- **Artifacts** - результаты выполнения задач
- **Messages** - история сообщений
- **Full database** - полный дамп PostgreSQL

## 🔄 Автоматические бэкапы

**Расписание:** Ежедневно в 3:00 AM (ночью)

**Хранение:** Последние 30 дней бэкапов

**Локация:** `/home/onor/ai_os_final/backups/`

## 📋 Использование

### Ручной бэкапа

```bash
# Запустить бэкап вручную
./scripts/backup_goals.sh
```

### Восстановление из бэкапа

```bash
# Посмотреть доступные бэкапы
./scripts/restore_goals.sh

# Восстановить из конкретного файла
./scripts/restore_goals.sh /home/onor/ai_os_final/backups/goals_backup_20260119_000500.sql.gz
```

### Создание старых целей

```bash
# Создать исторические цели (из логов системы)
./scripts/create_old_goals.sh
```

## 📊 Структура бэкапа

```
backups/
├── goals_backup_20260119_000500.sql.gz    # Полный дамп БД
├── goals_json_20260119_000500.json        # JSON экспорт целей
└── backup_log.txt                          # Лог всех бэкапов
```

## ⚙️ Настройка

### Изменить время бэкапа

Отредактируйте cron:
```bash
crontab -e
# Формат: мин час день месяц день_недели команда
0 3 * * * /home/onor/ai_os_final/scripts/backup_goals.sh
```

### Изменить период хранения

Отредактируйте `RETENTION_DAYS` в `scripts/backup_goals.sh`:
```bash
RETENTION_DAYS=30  # Хранить 30 дней
```

## 🔍 Проверка бэкапа

```bash
# Размер последнего бэкапа
ls -lh /home/onor/ai_os_final/backups/goals_backup_*.sql.gz | tail -1

# Количество целей в последнем бэкапе
cat /home/onor/ai_os_final/backups/goals_json_*.json | tail -1

# Лог бэкапов
tail /home/onor/ai_os_final/backups/backup_log.txt
```

## 🚨 Восстановление после сбоя

Если база данных повреждена:

1. **Остановить сервисы:**
   ```bash
   docker-compose stop core worker
   ```

2. **Восстановить из последнего бэкапа:**
   ```bash
   BACKUP=$(ls -t /home/onor/ai_os_final/backups/goals_backup_*.sql.gz | head -1)
   ./scripts/restore_goals.sh "$BACKUP"
   ```

3. **Запустить сервисы:**
   ```bash
   docker-compose start core worker
   ```

4. **Проверить:**
   ```bash
   curl http://localhost:8000/goals/list
   ```

## 📈 Текущие цели в системе

Восстановленные исторические цели:
1. **Оставить след в истории человечества** - создать значимый вклад
2. **Помогать близким и родным** - поддержка семьи
3. **Получение устойчивого дохода** - финансовая свобода

Технические цели:
4. Создать AI-OS систему
5. Настроить Dashboard v2
6. Интегрировать Telegram бота
7. Разработать Core сервис
8. Реализовать Worker сервис
9. Настроить Memory сервис
10. Настроить Telegram бот

**Всего: 10 целей**
