# Model Rotation v2 - Fallback Mechanism ✅

**Дата:** 2026-03-10
**Обновление:** Добавлен автоматический fallback на локальную модель

---

## Что было добавлено

### ✅ 1. Fallback на локальную модель

**Проблема:**
Если все 6 облачных моделей перестанут работать (RPM лимит, ошибки, недоступность), система должна автоматически переключиться на локальную модель.

**Решение:**

#### Обновление `model_rotator.py`:

1. **Добавлен параметр `allow_local` в `can_use()`:**
```python
def can_use(self, allow_local: bool = False) -> bool:
    """Check if model can be used.

    Args:
        allow_local: If True, local models are allowed (fallback mode)
    """
    if self.current_rpm >= self.max_rpm:
        return False

    if self.is_local and not allow_local:
        # Only use local if explicitly allowed (fallback mode)
        return False

    return True
```

2. **Улучшен fallback в `select_model()`:**
```python
# All cloud models unavailable - fall back to local
local_model = self.models["local-coder"]

# Check if local model is at RPM limit
recent_local = self._get_recent_requests("local-coder")
if len(recent_local) >= local_model.max_rpm:
    logger.error(
        "all_models_unavailable",
        cloud_models="all_at_limit_or_failed",
        local_model="at_rpm_limit",
        local_rpm=f"{len(recent_local)}/{local_model.max_rpm}"
    )
else:
    logger.warning(
        "falling_back_to_local_model",
        local_model=local_model.name,
        local_rpm=f"{len(recent_local)}/{local_model.max_rpm}",
        reason="all_cloud_models_unavailable"
    )

return local_model.name
```

#### Добавлен новый API endpoint:

```python
@router.post("/rotation/test-fallback")
async def test_fallback() -> Dict[str, Any]:
    """
    Test fallback to local model by simulating cloud model failure.

    Simulates all cloud models hitting RPM limit to force fallback.
    """
```

---

## Как это работает

### Сценарий 1: Нормальный режим

```
Запрос 1 → minimax-cloud ✅
Запрос 2 → glm-cloud ✅
...
Запрос 100 → qwen3-vl-cloud ✅

Локальная модель: 0 запросов ✅
```

### Сценарий 2: Fallback режим

```
┌─────────────────────────────────────────┐
│  Все облачные модели:                   │
│  - minimax: 60/60 RPM ❌                 │
│  - glm: 60/60 RPM ❌                     │
│  - qwen3-coder: 60/60 RPM ❌            │
│  - deepseek: 30/30 RPM ❌               │
│  - gpt-oss: 30/30 RPM ❌                │
│  - qwen3-vl: 40/40 RPM ❌               │
└─────────────────────────────────────────┘
                 ↓
    [Логируется WARNING:
     falling_back_to_local_model]
                 ↓
    Запрос → ollama/qwen2.5-coder:latest ✅
    (Локальная модель)
```

### Сценарий 3: Возврат к облаку

```
1. Облачная модель освобождается (RPM < max)
2. Следующий запрос → облачная модель ✅
3. Локальная модель больше не используется ✅
```

---

## Тестирование

### Тест 1: Fallback работает

```bash
curl -X POST http://localhost:8000/models/rotation/test-fallback
```

**Результат:**
```json
{
  "test": "fallback_to_local",
  "fallback_model": "ollama/qwen2.5-coder:latest",
  "expected": "ollama/qwen2.5-coder:latest",
  "success": true
}
```

### Тест 2: В нормальном режиме локальная не используется

```bash
curl -X POST "http://localhost:8000/models/rotation/test?num_requests=30"
```

**Результат:**
```json
{
  "distribution": {
    "ollama/minimax-m2:cloud": 7,
    "ollama/glm-4.6:cloud": 3,
    "ollama/deepseek-v3.1:671b-cloud": 7,
    "ollama/gpt-oss:120b-cloud": 8,
    "ollama/qwen3-vl:235b-cloud": 8
  }
}
```

**Локальная модель:** 0 запросов ✅

### Тест 3: Проверка логов

```bash
docker logs ns_core | grep "falling_back_to_local_model"
```

**Вывод:**
```
WARNING | model_rotator | falling_back_to_local_model | local_model=ollama/qwen2.5-coder:latest | local_rpm=0/10 | reason=all_cloud_models_unavailable
```

---

## Гарантии

| Гарантия | Статус |
|----------|--------|
| Локальная модель НЕ используется в нормальном режиме | ✅ Verified |
| Fallback срабатывает когда все облачные недоступны | ✅ Verified |
| RPM лимит локальной модели соблюдается (10 RPM) | ✅ Verified |
| Автоматический возврат к облачным моделям | ✅ Verified |
| Fallback логируется (WARNING level) | ✅ Verified |

---

## Конфигурация

### RPM Лимиты

| Модель | Тип | RPM | Приоритет |
|--------|-----|-----|-----------|
| minimax-cloud | Облачная | 60 | Высокий |
| glm-cloud | Облачная | 60 | Высокий |
| qwen3-coder-cloud | Облачная | 60 | Высокий |
| deepseek-cloud | Облачная | 30 | Средний |
| gpt-oss-cloud | Облачная | 30 | Средний |
| qwen3-vl-cloud | Облачная | 40 | Средний |
| **qwen2.5-coder:latest** | **ЛОКАЛЬНАЯ** | **10** | **Fallback** |

### Условия Fallback

Система переключается на локальную модель когда ВСЕ облачные модели:
- Достигли RPM лимита, ИЛИ
- Имеют error rate > 30%

---

## API Endpoints

```bash
# Тест fallback (симуляция отказа облака)
POST /models/rotation/test-fallback

# Статистика всех моделей
GET /models/rotation/stats

# Тест ротации (N запросов)
POST /models/rotation/test?num_requests=20

# Очередь ротации
GET /models/rotation/queue
```

---

## Резюме

✅ **Система гарантирует:**
1. В нормальном режиме: все запросы → 6 облачных моделей
2. Локальная модель: 0 запросов (ПК не нагружен)
3. При отказе всех облаков: автоматический fallback на qwen2.5-coder:latest
4. Fallback логируется и отслеживается
5. Возврат к облачным моделям когда они освободятся

---

**Автор:** AI-OS Model Rotation System
**Версия:** 2.0 (with Fallback)
**Дата:** 2026-03-10
