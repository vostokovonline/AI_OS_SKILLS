# AI_OS Deployment Guide

## 🚀 Быстрый старт

### Самое быстрое развертывание изменений:
```bash
make deploy-fast
```

Это скопирует все Python файлы в контейнеры и перезапустит их (~5 секунд).

---

## 📋 Команды Makefile

### Деплой
| Команда | Описание |
|---------|-----------|
| `make deploy` | Полный деплой (sync + очистка кеша + restart) |
| `make deploy-fast` | Быстрый деплой (sync + restart, без очистки кеша) |
| `make deploy-core` | Деплой только в ns_core |
| `make deploy-worker` | Деплой только в ns_core_worker |

### Статус и логи
| Команда | Описание |
|---------|-----------|
| `make status` | Статус контейнеров |
| `make logs` | Логи ns_core (tail -f) |
| `make logs-worker` | Логи ns_core_worker (tail -f) |

### Перезапуск
| Команда | Описание |
|---------|-----------|
| `make restart` | Перезапустить все контейнеры |
| `make restart-core` | Перезапустить только ns_core |
| `make restart-worker` | Перезапустить только ns_core_worker |

### LLM управление
| Команда | Описание |
|---------|-----------|
| `make llm-status` | Статус LLM fallback системы |
| `make llm-reset` | Сбросить Groq cooldown вручную |
| `make test-llm` | Протестировать LLM вызов |

### Тесты
| Команда | Описание |
|---------|-----------|
| `make test-goal` | Создать тестовую atomic goal |

---

## 🔧 LLM Fallback System

### Проблема
Когда Groq достигает rate limit (каждые 30 запросов или 80K tokens), система начинает возвращать ошибку `404 page not found`, которая сыпется в логи каждые 10 минут.

### Решение
**LLM Fallback Manager** (`llm_fallback.py`):
- Детектирует 404 ошибку от Groq
- Отключает Groq на **6 часов** (настраивается)
- Переключается на **Ollama Qwen2.5-Coder**
- Автоматически возвращается к Groq после cooldown
- Сохраняет состояние в Redis

### API endpoints

#### 1. Проверить статус
```bash
curl http://localhost:8000/llm/status
```

Ответ:
```json
{
  "status": "ok",
  "llm_status": {
    "groq_available": true,
    "fallback_model": "ollama/qwen2.5-coder:latest",
    "cooldown_hours": 6,
    "last_failure": "2026-01-10T16:04:15",
    "groq_disabled_until": "2026-01-10T22:04:15",
    "cooldown_remaining": "5:59:59"
  }
}
```

#### 2. Сбросить cooldown вручную
```bash
curl -X POST http://localhost:8000/llm/reset_groq
```

#### 3. Тестировать LLM
```bash
curl -X POST http://localhost:8000/llm/test \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say Hello World!"}'
```

---

## 🛠️ Deploy Script

### Полное использование:
```bash
./deploy.sh [command] [options]
```

Команды:
- `full` - Полный деплой (default)
- `fast` - Быстрый деплой (без очистки кеша)
- `single <container>` - Деплой в один контейнер
- `status` - Статус контейнеров
- `logs <container>` - Логи контейнера
- `restart <container>` - Перезапуск контейнера

Примеры:
```bash
# Полный деплой
./deploy.sh full

# Быстрый деплой
./deploy.sh fast

# Деплой только worker
./deploy.sh single ns_core_worker

# Проверить статус
./deploy.sh status

# Логи core
./deploy.sh logs ns_core
```

---

## 📦 Что происходит при деплое

### Fast Deploy (быстрый):
1. ✅ Копируются все `*.py` файлы из `services/core/` в контейнеры
2. ✅ Копируются директории (`agents/`, `canonical_skills/`, etc.)
3. ✅ Перезапускаются контейнеры
4. ✅ Проверяется что контейнеры запустились

Время: **~5 секунд**

### Full Deploy (полный):
1. ✅ Всё то же что fast deploy
2. ✅ Очищается `__pycache__` в контейнерах
3. ✅ Удаляются `*.pyc` файлы
4. ✅ Health check для каждого контейнера

Время: **~10 секунд**

---

## ⚙️ Настройка

### Гроq cooldown duration
`.env` файл:
```bash
GROQ_COOLDOWN_HOURS=6  # На сколько часов отключать Groq при rate limit
```

### Fallback модель
`.env` файл:
```bash
FALLBACK_MODEL=ollama/qwen2.5-coder:latest
FALLBACK_API_BASE=http://host.docker.internal:11434
```

---

## 🐛 Troubleshooting

### 1. Контейнер не запускается после деплоя
```bash
# Проверить логи
docker logs ns_core --tail 100

# Проверить статус
make status
```

### 2. Ошибка "ModuleNotFoundError"
```bash
# Сделать полный деплой (с очисткой кеша)
make deploy
```

### 3. Ошибка "AttributeError: 'Goal' object has no attribute"
```bash
# Это значит models.py не синхронизирован
# Полный деплой решит это
make deploy
```

### 4. Groq fallback не работает
```bash
# Проверить статус
make llm-status

# Сбросить cooldown вручную
make llm-reset

# Проверить Redis
make redis-cli
> GET llm:groq:disabled_until
```

---

## 📊 Мониторинг

### Проверить execution trace:
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c \
  "SELECT title, status, progress, execution_trace IS NOT NULL as has_trace \
   FROM goals WHERE is_atomic = true ORDER BY created_at DESC LIMIT 5;"
```

### Проверить логи worker:
```bash
make logs-worker
```

---

## 🎯 Best Practices

1. **После изменений в моделях (`models.py`):**
   - Используй `make deploy` (с очисткой кеша)
   - Или добавь поля в БД: `ALTER TABLE goals ADD COLUMN ...`

2. **После создания новых модулей:**
   - Используй `make deploy-fast`
   - Файлы автоматически скопируются

3. **При частых изменениях:**
   - Используй `make deploy-fast` для скорости
   - Иногда делай `make deploy` для очистки кеша

4. **Когда Groq упал:**
   - Система автоматически переключится на fallback
   - Через 6 часов автоматически вернется к Groq
   - Можно ускорить: `make llm-reset`

---

## 🔐 Безопасность

### Контейнер изоляция
- Код копируется через `docker cp`, не volume mounts
- Python cache очищается при полном деплое
- Контейнеры перезапускаются, загружая новый код

### Redis состояние
- Groq cooldown хранится в Redis
- Автоматически истекает через N часов
- Можно сбросить вручную через API

---

## 📝 Changelog

### 2026-01-10 - LLM Fallback System
- ✅ Создан `llm_fallback.py` - умный fallback при rate limits
- ✅ Добавлены API endpoints: `/llm/status`, `/llm/reset_groq`, `/llm/test`
- ✅ Создан `deploy.sh` - автоматический деплой
- ✅ Создан `Makefile` - удобные команды
- ✅ Groq 404 ошибки теперь детектируются и обрабатываются
- ✅ Автоматическое переключение на fallback на 6 часов
- ✅ Автоматическое возвращение к Groq после cooldown

---

## 🚀 Next Steps

1. **Настроить CI/CD** для автоматического деплоя
2. **Добавить monitoring** для Groq rate limit
3. **Алертинг** когда fallback активирован
4. **Метрики** использования Groq vs fallback
