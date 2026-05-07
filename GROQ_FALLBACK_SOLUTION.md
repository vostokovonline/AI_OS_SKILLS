# 🎯 AI_OS: Groq Rate Limit Fix & Auto-Deploy

## 📍 Проблема

### Ошибка в логах (каждые 10 минут):
```
litellm.NotFoundError: NotFoundError: GroqException - 404 page not found.
All fallback attempts failed.
```

**Что происходило:**
1. Groq free tier имеет лимиты: 30 requests/minute или 80K tokens/day
2. При достижении лимита Groq возвращает `404 page not found`
3. litellm пробует retry через 1 секунду, но снова получает 404
4. Это повторяется в логах каждые 10 минут (scheduler cognitive heartbeat)
5. Система тратит ресурсы на бесполезные попытки

---

## ✅ Решение: LLM Fallback Manager

### Что делает новая система:

**1. Детекция ошибки:**
- Распознает `404 page not found` от Groq как rate limit
- Отличает от других 404 ошибок

**2. Умное переключение:**
- При первой 404 ошибке → отключает Groq на **6 часов**
- Переключается на **Ollama Qwen2.5-Coder** (локальный fallback)
- Сохраняет timestamp failure в Redis

**3. Автоматическое восстановление:**
- Через 6 часов автоматически возвращается к Groq
- Проверяет cooldown при каждом вызове
- Можно сбросить вручную через API

**4. Прозрачность:**
- API endpoint для проверки статуса
- Логирование всех переключений
- Метрики cooldown времени

---

## 🛠️ Компоненты решения

### 1. `llm_fallback.py` - Менеджер переключения

**Основные методы:**
```python
# Проверить доступен ли Groq
manager.is_groq_available()

# Пометить Groq как упавший
manager.mark_groq_failed()

# Выполнить вызов с автоматическим fallback
await manager.chat_completion(model, messages, **kwargs)

# Получить статус
manager.get_status()
```

**Ключевые фичи:**
- ✅ Детекция 404 ошибки от Groq
- ✅ Redis хранение состояния (переживает перезапуски)
- ✅ Configurable cooldown duration (через env)
- ✅ Fallback на любую модель (Ollama, OpenAI, etc.)
- ✅ Логирование всех действий

### 2. API Endpoints (`main.py`)

**GET /llm/status**
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

**POST /llm/reset_groq**
- Сбрасывает cooldown вручную
- Включает Groq обратно
- Полезно для тестирования

**POST /llm/test**
- Тестирует LLM вызов с fallback
- Показывает какая модель реально использовалась

### 3. Deploy Script (`deploy.sh`)

**Проблема которую решал:**
- ❌ Ручное копирование через `docker cp` для каждого файла
- ❌ Забывание очистить `__pycache__`
- ❌ Забывание перезапускать контейнеры
- ❌ Нет синхронизации между контейнерами

**Решение:**
```bash
# Быстрый деплой (5 секунд)
./deploy.sh fast

# Полный деплой (10 секунд)
./deploy.sh full

# Деплой одного контейнера
./deploy.sh single ns_core_worker
```

**Что делает скрипт:**
1. ✅ Копирует все `*.py` файлы
2. ✅ Копирует все директории (`agents/`, `canonical_skills/`, etc.)
3. ✅ Очищает `__pycache__` (только при full deploy)
4. ✅ Перезапускает контейнеры
5. ✅ Health check для каждого контейнера
6. ✅ Цветной вывод для удобства

### 4. Makefile

**Удобные команды:**
```bash
make deploy          # Полный деплой
make deploy-fast     # Быстрый деплой
make status          # Статус контейнеров
make logs            # Логи core
make llm-status      # Статус LLM fallback
make llm-reset       # Сбросить Groq cooldown
make test-goal       # Тестовая atomic goal
```

---

## 📊 Результаты

### До (с ошибками):
```
[2026-01-10 04:37:12,165] ❌ SUPERVISOR ERROR: Error code: 500
litellm.NotFoundError: GroqException - 404 page not found
All fallback attempts failed
[... повторяется каждые 10 минут ...]
```

### После (с fallback):
```
[2026-01-10 16:04:15] ⚠️ Groq 404 error detected - rate limit hit!
[2026-01-10 16:04:15] ⚠️ Groq marked as FAILED for 6 hours
[2026-01-10 16:04:15]    Disabled until: 2026-01-10T22:04:15
[2026-01-10 16:04:16] 🔄 Retrying with fallback: ollama/qwen2.5-coder:latest
[2026-01-10 16:04:16] ✅ Fallback LLM call successful
```

---

## 🚀 Как использовать

### 1. Быстрый старт

**После изменения кода:**
```bash
# Самый быстрый способ
make deploy-fast
```

### 2. Проверить статус Groq
```bash
make llm-status
```

### 3. Сбросить cooldown вручную
```bash
make llm-reset
```

### 4. Мониторинг

**Проверить логи:**
```bash
make logs-worker
```

**Найти fallback переключения:**
```bash
docker logs ns_core_worker | grep -E "(Groq|fallback|404)"
```

---

## ⚙️ Конфигурация

### .env настройки:
```bash
# На сколько часов отключать Groq при rate limit
GROQ_COOLDOWN_HOURS=6

# Fallback модель
FALLBACK_MODEL=ollama/qwen2.5-coder:latest
FALLBACK_API_BASE=http://host.docker.internal:11434
```

### litellm_config.yaml:
Уже настроен с fallbacks:
```yaml
model_list:
  - model_name: groq-primary
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: os.environ/GROQ_API_KEY
      rpm: 600
      tpm: 100000
      fallbacks: [{"model": "ollama/qwen2.5-coder:latest"}]
```

---

## 📈 Метрики

### Экономия времени:
- **До:** Бесконечные retries (каждые 10 минут, 20+ секунд)
- **После:** Одно переключение + 6 часов стабильной работы

### Экономия ресурсов:
- **До:** Повторные попытки → нагрузка на litellm
- **После:** Fallback на локальный Ollama → 0 нагрузку

### Надежность:
- **До:** Ошибки в логах каждые 10 минут
- **После:** Ошибок нет, переключение происходит 1 раз

---

## 🐛 Troubleshooting

### 1. Fallback не срабатывает

**Проверьте:**
```bash
# 1. Проверьте что модуль загружен
docker exec ns_core python3 -c "from llm_fallback import llm_fallback; print('OK')"

# 2. Проверьте статус
make llm-status

# 3. Проверьте Redis
make redis-cli
> KEYS llm:*
```

### 2. Groq не возвращается после cooldown

**Решение:**
```bash
# Проверьте время
make llm-status

# Сбросьте вручную если нужно
make llm-reset
```

### 3. Контейнеры не запускаются после деплоя

**Проверьте:**
```bash
# Логи
docker logs ns_core --tail 50

# Если import ошибки - полный деплой
make deploy  # (с очисткой кеша)
```

---

## 🎯 Best Practices

### 1. После изменений в моделях (models.py)
```bash
make deploy  # Полный деплой с очисткой кеша
```

### 2. После создания новых модулей
```bash
make deploy-fast  # Быстрый деплой
```

### 3. При разработке (частые изменения)
```bash
make deploy-fast  # Быстро
# Иногда:
make deploy  # Для очистки кеша
```

### 4. Когда Groq rate limit достигнут
- **Ничего не делать!** Система автоматически переключится
- Через 6 часов автоматически вернется
- Можно проверить: `make llm-status`

---

## 📝 Чек-лист после установки

- [x] Создан `llm_fallback.py`
- [x] Добавлены API endpoints в `main.py`
- [x] Создан `deploy.sh`
- [x] Создан `Makefile`
- [x] Создана документация `DEPLOYMENT.md`
- [x] Протестирован fallback механизм
- [x] Протестирован deploy скрипт
- [x] Протестирован Makefile

---

## 🚀 Next Steps

1. **Monitoring:** Добавить алерты при переключении
2. **Metrics:** График использования Groq vs fallback
3. **Auto-tuning:** Адаптивный cooldown duration
4. **CI/CD:** Интегрировать с Git push

---

## 📚 Дополнительные файлы

- `DEPLOYMENT.md` - Полное руководство по деплою
- `deploy.sh` - Скрипт автоматического деплоя
- `Makefile` - Удобные команды
- `llm_fallback.py` - Менеджер переключения LLM

---

## ✅ Итоговый статус

| Компонент | Статус | Описание |
|-----------|--------|-----------|
| LLM Fallback Manager | ✅ DONE | Умное переключение при rate limits |
| API Endpoints | ✅ DONE | /llm/status, /llm/reset, /llm/test |
| Deploy Script | ✅ DONE | Автоматический деплой контейнеров |
| Makefile | ✅ DONE | Удобные команды управления |
| Documentation | ✅ DONE | Полное руководство |
| Testing | ✅ DONE | Протестировано и работает |

**🎉 Проблема решена!**
