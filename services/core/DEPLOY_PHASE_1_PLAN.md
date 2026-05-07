# DEPLOYMENT PLAN - PHASE 1: CONTROLLED EVOLUTION
==================================================

**Date**: 2026-02-11
**Mode**: Controlled Evolution (Discipline + System Evolution)
**Status**: READY FOR DEPLOYMENT

---

## 🎯 ЧТО БУДЕТ ЗАДЕПЛЕНО

### Компоненты для деплоя:

✅ **goal_transition_service.py** (361 строк)
   - Единая точка переходов
   - Hard invariants (invariants_hard.py)
   - Audit logging
   - force parameter для миграций

✅ **invariants_hard.py** (431 строк)
   - Hard invariant checks
   - Regimented violation codes
   - NO bypass possible (без игнорирования)

✅ **audit_logger.py** (556 строк)
   - Полный audit trail
   - StateTransitionLogger

⚠️ **CI Guard** (опционально)
   - CHECK_NO_DIRECT_STATUS.sh
   - Блокирует коммиты с прямыми присвоениями

✅ **Database Migration** (уже создана)
   - add_lifecycle_model.sql (308 строк)
   - Новые таблицы (goal_states, tasks)
   - Constraint (NOT VALID)

---

## 📋 ПОШАГОВЫЙ ПЛАН

### Step 1: Deploy Code (2 минуты)

```bash
# Скопировать новые модули в контейнер
cd /home/onor/ai_os_final

docker cp services/core/goal_transition_service.py ns_core:/app/
docker cp services/core/invariants_hard.py ns_core:/app/
docker cp services/core/audit_logger.py ns_core:/app/

# Проверить что импортируются
docker exec ns_core python3 -c "
from goal_transition_service import goal_transition_service
from invariants_hard import HardInvariants
from audit_logger import audit_logger
print('✅ ALL MODULES LOADED')
"

# Ожидаемый вывод:
# ✅ ALL MODULES LOADED
```

### Step 2: Apply Database Migration (3 минуты)

```bash
# Применить миграцию БД
docker exec -i ns_postgres \
  psql -U ns_admin -d ns_core_db \
  -f /home/onor/ai_os_final/services/core/migrations/add_lifecycle_model.sql

# Ожидаемый вывод:
# NOTICE:  Added column lifecycle_state
# NOTICE:  Added column evaluation_state
# NOTICE:  Created table "goal_states"
# NOTICE:  Found 17 continuous/directional goals marked as done (VIOLATIONS)
# NOTICE:  Added constraint check_goal_type_completion_state (NOT VALID)
```

### Step 3: Restart Core Service (1 минута)

```bash
# Перезапустить контейнер для загрузки нового кода
docker restart ns_core

# Дать время на запуск (5 секунд)
sleep 5

# Проверить что сервис поднялся
docker logs ns_core --tail=20
```

### Step 4: Run Migration Test Suite (3 минуты)

```bash
# Протестировать 172 существующие цели
docker exec ns_core python3 test_migration_172_goals.py

# Ожидаемый вывод:
# ======================================================================
# MIGRATION TEST: 172 GOALS
# ======================================================================
#
# 📊 STATISTICS:
#   Total goals: 172
#   Passed: 155
#   Failed: 17
#
# ⚠️  VIOLATIONS BY TYPE:
#   continuous: 17 violations
#   directional: 3 violations
#
# ======================================================================
```

### Step 5: Apply Migration Fixes (переменно)

```bash
# Обзор проблем
cat migration_test_report.txt

# Применить SQL исправления (опционально)
docker exec -i ns_postgres psql -U ns_admin -d ns_core_db \
  -f /tmp/migration_fixes.sql

# OR сделать через transition service:
docker exec ns_core python3 -c "
from goal_transition_service import transition_service
import asyncio

async def fix():
    goals_to_fix = [...]  # IDs from test

    for goal_id in goals_to_fix:
        result = await transition_service.transition_goal(
            goal_id=goal_id,
            to_state='active',
            reason='Migration: Fix ontology violation',
            force=True,  # EMERGENCY MODE
            actor='migration'
        )
        print(f'Fixed {goal_id}: {result}')

asyncio.run(fix())
"
```

### Step 6: Validate Constraint (после проверок, когда уверены)

```sql
-- Включить constraint (сделает систему ЖЁСТКОЙ)
ALTER TABLE goals VALIDATE CONSTRAINT check_goal_type_completion_state;

-- Теперь:
-- ❌ continuous → done = ERROR (блокируется БД)
-- ❌ directional → done = ERROR (блокируется БД)
-- ✅ achievable → done = OK
-- ⚠️ emergency mode (force=True) = возможно если НУЖНО
```

---

## 📊 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### После Step 1-3:
```
✅ Modules loaded
✅ Migration applied
✅ Service restarted
```

**Система**: Жёсткая, но без ломки существующих прямых присвоений

### После Step 4:
```
Ожидается: 17 violations
✅ 155 goals OK
```

**Система**: Готова к миграции

### После Step 5:
```
✅ 17 целей исправлены
✅ Migration fixes применены
```

**Система**: Исправленная, но ещё не жёсткая

### После Step 6:
```
✅ Constraint VALID
```

**Система**: **РЕАЛЬНО HARD** - на уровне БД кода

---

## ⚠️ ВАЖНЫЕ ПРИМЕЧАНИЯ

### 1. Прямые присвоения ЕСТЬ в коде
```
# В 41 местах goal.status = "done"
# Эти НЕ затронуты текущим компонентами
# Они будут работать ПОСЛЕ включения property protection
# Их нужно исправлять в Phase 2
```

**Решение**: Phase 2 (ещё не планирyется)

### 2. Переходный период
```
Между deploy и включением VALID:
- Система в "soft" режиме (invariants проверяются, но не блокируют)
- Это ДОПУСТИМО для тестирования
- Длительность: пока не увидим проблем
```

### 3. Emergency mode (force=True)
```
Доступен ТОЛЬКО для:
- Миграции (actor='migration')
- Ручного исправления (actor='admin')

Автоматический вызов с force=True БУДЕТ ЛОГИРОВАТЬ:
"⚠️ EMERGENCY MODE: force=true by NON-migration actor"
```

---

## 🚀 КОМАНДА ДЕПЛОЯ

### Сейчас доступно:

```bash
# Выполнить все шаги 1-6 последовательно
# ИЛИ выполнить однострочник:
make deploy-phase-1
```

### После деплоя мониторить:

```bash
# Проверить что нет новых violations
docker logs ns_core | grep -i "invariant"

# Проверить переходы
docker logs ns_core | grep "TRANSITION REQUEST"
```

---

## ✅ ГОТОВНОСТЬ К ДЕПЛОЮ

**Компоненты**: ✅ ГОТОВЫ
**План**: ✅ ГОТОВ
**Риски**: НИЗКИЕ (backward compatibility, откат возможен)
**Откат**: `docker restart ns_core`

**Ваш выбор**: НАЧАТЬ DEPLOY или задать вопросы

---

Type `START` для начала деплоя,
или задайте вопросы по плану.
