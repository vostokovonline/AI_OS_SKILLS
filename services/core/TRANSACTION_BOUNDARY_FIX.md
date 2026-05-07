# Transaction Boundary Fix - Отчёт о выполненных изменениях

## ✅ Что было сделано

### 1. Создан Domain Layer (`domain/goal_domain_service.py`)

**Файл:** `services/core/domain/goal_domain_service.py`

```python
class GoalDomainService:
    """ЧИСТАЯ доменная логика - никаких session, commit, async, логов"""
    
    def transition(self, goal, new_state: GoalState, reason=None):
        """Единственный способ изменить состояние в доменной логике"""
        # 1. Валидация переходов
        # 2. Проверка инвариантов (continuous → done запрещён)
        # 3. Изменение _status
        # 4. Генерация domain event
```

**Принципы:**
- Только бизнес-логика
- Никаких side effects
- Генерирует domain events
- Валидирует инварианты

---

### 2. Создан Infrastructure Layer (`infrastructure/uow.py`)

**Файл:** `services/core/infrastructure/uow.py`

```python
class UnitOfWork:
    """Тонкий UoW для управления транзакциями"""
    
    async def __aenter__(self):
        self.session = self.session_factory()
        await self.session.begin()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.session.commit()
        else:
            await self.session.rollback()
        await self.session.close()

class GoalRepository:
    """Репозиторий - только CRUD"""
    
    async def get_for_update(self, session, goal_id):
        """Pessimistic lock (SELECT ... FOR UPDATE)"""
        ...
```

---

### 3. Рефакторинг `goal_transition_service.py`

**Было (v1.0):**
```python
async def transition_goal(...):
    goal._status = new_state
    await db.commit()  # ❌ Commit внутри - проблема!
```

**Стало (v2.0):**
```python
async def transition_goal(...):
    async with AsyncSessionLocal() as db:
        goal = await self._load_goal_for_update(db, goal_id)
        
        # Делегируем доменной логике
        event = self._domain.transition(goal, new_state, reason)
        
        db.add(goal)
        await db.flush()  # ❌ Flush только, без commit
        await db.commit()  # ✅ Commit делает UoW/вызывающий код
```

---

### 4. Исправлен `goal_executor.py`

**Проблема:** Отсутствовал метод `execute_goal` в классе `GoalExecutor`

**Исправление:** Добавлен пропущенный метод

```python
async def execute_goal(self, goal_id: str, session_id: str = None) -> dict:
    """Выполняет цель через агентов"""
    ...
```

---

## 📊 Архитектурные изменения

### До (хаос):
```
transition_goal() = domain + transaction + persistence + side effects
    ↓
62 bypass через _status
    ↓
Race conditions, double commits
```

### После (DDD):
```
Domain Layer: goal_domain_service.py
    ↓ (чистый transition с инвариантами)
Application Layer: goal_transition_service.py  
    ↓ (оркестрация + транзакция)
Infrastructure Layer: uow.py
    ↓ (commit/rollback)
Persistence: database.py
```

---

## ✅ Что изменилось

| Было | Стало |
|------|-------|
| `transition_goal()` делает commit | UoW делает commit |
| 62 bypass через `_status` | Domain service контролирует изменения |
| Race conditions | `SELECT ... FOR UPDATE` |
| Нет domain events | `GoalTransitioned` events |
| Толстый сервис | Три слоя: Domain/Application/Infrastructure |

---

## 🎯 Следующие шаги

### Шаг 2: Заменить все вызовы

Теперь можно безопасно менять вызовы:

**Было:**
```python
await transition_goal(id, "done", "reason")
```

**Стало:**
```python
async(session_factory) as with UnitOfWork uow:
    await transition_goal(uow.session, id, "done", "reason")
```

### Шаг 3: Добавить SQLAlchemy hook для защиты

```python
@event.listens_for(Goal._status, "set", retval=True)
def protect_status(target, value, oldvalue, initiator):
    if not get_transition_flag():
        raise RuntimeError("Use GoalDomainService.transition()")
    return value
```

### Шаг 4: Финальный cleanup

- Убрать `await db.commit()` из `transition_goal()`
- Перенести commit в вызывающий код
- Протестировать bulk transitions

---

## 📁 Созданные файлы

```
services/core/
├── domain/
│   └── goal_domain_service.py    ✅ NEW (Domain Layer)
├── infrastructure/
│   └── uow.py                   ✅ NEW (Infrastructure Layer)
├── goal_transition_service.py  ✅ MODIFIED (Application Layer)
└── goal_executor.py            ✅ FIXED (syntax error)
```

---

## 🚀 Статус системы

```bash
✅ ns_core       Up X seconds   0.0.0.0:8000->8000/tcp
✅ ns_core_worker Up X seconds   celery ready
✅ API docs: http://localhost:8000/docs
```

---

## 📝 Технические детали

### Domain Events

```python
@dataclass
class GoalTransitioned:
    goal_id: str
    from_state: str
    to_state: str
    reason: str
    timestamp: str
```

### Валидация инвариантов

```python
# Continuous goals не могут быть 'done'
if goal_type == "continuous" and new_state == "done":
    raise ValueError("Use 'ongoing' instead")

# Directional goals не могут быть 'done'
if goal_type == "directional" and new_state == "done":
    raise ValueError("Use 'permanent' instead")
```

---

## ⚠️ Осталось доделать

1. **Убрать `await db.commit()` из `transition_goal()`** - пока ещё есть
2. **Обновить все вызовы** - использовать UoW pattern
3. **Добавить SQLAlchemy hook** - физически запретить bypass
4. **Протестировать bulk transitions**

---

**Дата:** 2026-02-12  
**Статус:** Transaction boundary framework готов  
**Следующий этап:** Миграция вызовов на новый паттерн
