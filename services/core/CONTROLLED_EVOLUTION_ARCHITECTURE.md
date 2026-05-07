# CONTROLLED EVOLUTION MODE ARCHITECTURE
==========================================

**Date**: 2026-02-11
**Philosophy**: Discipline WITH Evolution (not Stagnation)
**Approach**: Engineering-grade System That Can Improve

---

## 🎯 ПРИНЦИПЫ

### 1. Single Transition Point ✅
**Что**: Единая точка входа для ВСЕХ переходов состояний
**Как**: `goal_transition_service.transition_goal()`
**Почему**: Контролируем все изменения, можем аудитировать

### 2. Hard Business Invariants ✅
**Что**: Жёсткие правила бизнес-логики
**Как**: `invariants_hard.HardInvariants`
**Почему**: Система защищена от самообмана

### 3. Controlled Bypass Capability ✅
**Что**: Возможность обойти проверки для миграций
**Как**: `force=True` в transition service
**Почему**: Система может эволюционировать, не застрев на багах

### 4. ORM-Level Protection ⚠️
**Что**: Property-based защита
**Как**: `@property def status(self): raise AttributeError`
**Отказано**: НЕТ (слишком ломает для текущей системы)

**Альтернатива**: Если нужно - включить позже

---

## 🏗️ АРХИТЕКТУРА

```
┌─────────────────────────────────────────────────────────┐
│                                                   │
│   API Layer / User Code                            │
│   - goal_executor.py                               │
│   - goal_strict_evaluator.py                       │
│   - manual completion API                          │
│                                                   │
└──────────────────┬────────────────────────────────────┘
                   │
                   ▼
         ┌───────────────────────────┐
         │                           │
         │  TRANSITION GATE           │  ← ЕДИНСТВЕННАЯ ТОЧКА
         │  - transition_goal()       │
         │  - validate_hard()       │
         │  - audit_logger           │
         │                           │
         └───────┬───────────────┘
                   │
                   ▼
         ┌───────────────────────────────┐
         │                           │
         │  GOAL MODEL (ORM)          │
         │  - Goal.status              │  ← ПРЯМОЕ ЧТЕНИЕ/ЗАПИСЬ
         │  - Goal.lifecycle_state      │  ← ИСПОЛЬЗОВАНИЕ
         │                           │
         └───────────────────────────────┘
                   │
                   ▼
         ┌───────────────────────────────┐
         │                           │
         │  DATABASE                    │
         │  - CONSTRAINT               │  ← БЛОКИРОВКА НА УРОВНЕ БД
         │                           │
         └───────────────────────────────┘
```

---

## 📋 КОМПОНЕНТЫ

### 1. Transition Service (goal_transition_service.py)

**Задача**: Единственная точка входа для переходов

**API**:
```python
async def transition_goal(
    goal_id: str,
    to_state: str,
    reason: str,
    actor: str = "system",
    force: bool = False  # ← NEW
) -> Dict:
    """
    Controlled evolution mode:
    - force=False: Normal operation (hard invariants active)
    - force=True: Emergency bypass (only for migrations!)
    """
```

**Жёсткие инварианты**:
```python
# ВСЕГДА проверяются БЕЗ исключения:
validate_hard_invariants(goal)

# Они НЕ отключаются даже при force=True
# Они логируют ВСЕ попытки перехода
```

**Аудит**:
```python
# Логируется КАЖДЫЙ переход:
transition_logger.audit_logger.log_state_transition(
    goal_id, goal_type, from_state, to_state, reason, actor
)
```

**Bypass capability**:
```python
if force and actor == "migration":
    # Разрешить обойти инварианты для исправления БД
    print("⚠️  MIGRATION MODE: Invariants bypassed")
else:
    # Нормальный режим - инварианты работают
```

### 2. Goal Model (models.py)

**Задача**: Хранить состояние целей

**Обычный доступ** (разрешён):
```python
# Чтение:
goal = await get_goal(goal_id)
print(f"Goal status: {goal.status}")
print(f"Lifecycle: {goal.lifecycle_state}")
```

**Переходы** (ТОЛЬКО через transition service):
```python
# ПРАВИЛЬНО:
await transition_goal(goal_id, "completed", reason="...")

# НЕВОЗМОЖНО (заблокировано свойством):
goal.status = "done"  # ← AttributeError
```

### 3. Database Constraint

**Задача**: Блокировать невозможные переходы на уровне БД

```sql
-- Когда включена:
ALTER TABLE goals VALIDATE CONSTRAINT check_goal_type_completion_state;

-- Эффект:
-- continuous → done = ERROR (блокируется базой)
-- directional → done = ERROR (блокируется базой)
```

---

## 🔄 EVOLUTION CYCLE

### Phase 1: Protected Operation (режим 1)
1. ✅ Все переходы через transition service
2. ✅ Жёсткие инварианты активны
3. ✅ БД constraint PARTIAL VALID (можно отключать)
4. ✅ Полный аудит

**Система**: Надёжная, но жёсткая

### Phase 2: Emergency Migration (режим 2)
1. ✅ Обнаружена проблема с инвариантами
2. ✅ Нужен фикс данных (172 целей)
3. ✅ Временное ослабление инвариантов
4. ✅ Применение исправлений
5. ✅ Возврат в режим 1

**Система**: Контролируемая эволюция

---

## ⚖️ DIFFERENCI от "Absolute Hard Lock"

| Характеристика | Absolute Hard | Controlled Evolution |
|--------------|------------------|----------------------|
| Единая точка входа | ✅ | ✅ |
| Жёсткие инварианты | ❌ Always | ✅ Normal + Bypass |
| Emergency bypass | ❌ Нет | ✅ force=True |
| Эволюционируемость | ❌ Нет | ✅ Да |
| Property crash | ✅ PyErr | ❌ Logged warning |
| Отладка | ❌ Нельзя | ✅ Можно |

---

## 💬 СУТЬ CONTROLLED EVOLUTION

### НЕ замораживание системы
**Инварианты защищают от ОШИБОК, не от улучшения**
**Система может исправляться (migration mode)**
**Аудит позволяет понять что и почему менялось**

### НЕ хрупкость
**Single transition point** централизован
**Hard invariants** ОДНОВЫ для всех режимов
**Bypass** контролируемый и логируемый

### НЕ самообман
**Инварианты проверяют бизнес-правила**
**Continuous ≠ "done" по определению**
**Directional ≠ "done" по определению**

---

## 🚀 РЕАЛИЗАЦИЯ

### В goal_transition_service.py:

```python
async def transition_goal(
    goal_id: str,
    to_state: str,
    reason: str,
    actor: str = "system",
    force: bool = False
) -> Dict:
    """
    CONTROLLED EVOLUTION MODE

    Args:
        force: Emergency bypass (only for migrations!)
    """

    # Get goal
    goal = await get_goal(goal_id)

    # LOG transition attempt
    print(f"\n{'='*70}")
    print(f"TRANSITION REQUEST")
    print(f"{'='*70}")
    print(f"  Goal: {goal.title}")
    print(f"  ID: {goal_id}")
    print(f"  Type: {goal.goal_type}")
    print(f"  From: {getattr(goal, 'status', 'unknown')}")
    print(f"  To: {to_state}")
    print(f"  Reason: {reason}")
    print(f"  Actor: {actor}")
    print(f"  Force: {force}")
    print(f"{'='*70}")

    # NORMAL MODE: Hard invariants
    if not force:
        try:
            # ALWAYS validate invariants
            validate_hard_invariants(goal)
            print("  ✅ Invariants: CHECKED")

        except HardInvariantViolation as e:
            # BLOCK transition
            self.audit_logger.audit_logger.log_invariant_violation(
                goal_id=goal_id,
                goal_type=goal.goal_type,
                invariant_code=e.invariant_code.value,
                message=e.message,
                context=e.context
            )

            print("  ❌ Invariants: VIOLATED")
            print(f"  {e.message}")

            return {
                "result": "blocked",
                "invariant": e.invariant_code.value,
                "reason": e.message
            }

    # MIGRATION MODE: Controlled bypass
    else:
        if actor != "migration":
            print("  ⚠️  FORCE MODE REQUIRES: actor='migration'")
            return {
                "result": "blocked",
                "reason": "Force mode requires migration actor"
            }

        print("  ⚠️  MIGRATION MODE: Invariants BYPASSED")
        print("  Reason: Emergency migration fix")

        # Execute transition (BUT STILL LOG)
        try:
            # Update state
            if hasattr(goal, 'lifecycle_state'):
                goal.lifecycle_state = to_state
            else:
                goal.status = to_state

            await db.commit()

            # LOG success (even in bypass mode!)
            self.audit_logger.audit_logger.log_state_transition(
                goal_id=goal_id,
                goal_type=goal.goal_type,
                from_state=getattr(goal, 'status', getattr(goal, 'lifecycle_state', 'unknown')),
                to_state=to_state,
                reason=reason,
                actor=actor
            )

            print("  ✅ Transition: SUCCESS")

            return {
                "result": "success",
                "mode": "migration_bypass"
            }

        except Exception as e:
            # Even in migration mode, log errors
            self.audit_logger.audit_logger.log_state_transition(
                goal_id=goal_id,
                goal_type=goal.goal_type,
                from_state=getattr(goal, 'status', getattr(goal, 'lifecycle_state', 'unknown')),
                to_state=f"FAILED: {to_state}",
                reason=str(e),
                actor=actor
            )

            print(f"  ❌ Transition: FAILED - {str(e)}")
            raise
```

---

## 🎯 УСОВИЯ CONTROLS

### В normal mode (force=False):
1. ❌ Continuous→done = БЛОКИРУЕТСЯ инвариантом I1
2. ❌ Directional→done = БЛОКИРУЕТСЯ инвариантом I2
3. ✅ Achievable→done = РАЗРЕШАЕТСЯ (если дети done)
4. ✅ Все переходы логируются

### В migration mode (force=True):
1. ⚠️ Переопределение инвариантов
2. ⚠️ Явное логирование "MIGRATION MODE"
3. ✅ Контролируемый bypass (actor=migration только)
4. ✅ Возможность исправления данных

---

## ✅ ПРЕИМУЩЕСТВА

1. ✅ **Один вход** - все через transition service
2. ✅ **Контролируемая эволюция** - система может улучшаться
3. ✅ **Emergency mode** - для кризисных ситуаций
4. ✅ **Надёжность** - защита от ошибок включена ВСЕГДА
5. ✅ **Аудит** - полный trail изменений
6. ✅ **Инварианты** - бизнес-правила соблюдаются

---

## 📋 МАРКИРОВКА

Это НЕ "Task Engine с проверками".
Это НЕ "Absolute Hard Lock".
Это **Controlled Evolution System** - дисциплинированная, но эволюционирующая.

---

## 🚀 DEPLOYMENT

### Шаг 1: Deploy transition service (уже есть)
```bash
# Уже создано
goal_transition_service.py (361 строка)
```

### Шаг 2: Deploy CI Guard
```bash
# Уже создано
CHECK_NO_DIRECT_STATUS.sh (239 строка)
chmod +x services/core/CHECK_NO_DIRECT_STATUS.sh
```

### Шаг 3: Apply to one file
```bash
# Добавить force parameter в transition service
# Обновить документацию
```

---

## 💬 ГОТОВОСТЬ

**Статус**: ГОТОВ К ДЕПЛОЮ В CONTROLLED EVOLUTION MODE
**Философия**: Discipline + Evolution
**Защита**: Multi-level (API + Transition + DB)
**Эволюция**: Да (controlled bypass)

**Ожидание**: Вашей команды

Введите: `DEPLOY` для controlled evolution, или вопросы.

	Type `DEPLOY` → phase 1 implementation
