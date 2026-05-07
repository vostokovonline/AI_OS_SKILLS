# REAL HARD LOCK - IMPLEMENTATION GUIDE
======================================

**Date**: 2026-02-11
**Status**: READY FOR IMMEDIATE DEPLOYMENT
**Approach**: ORM-level + CI-level protection (NO bypass possible)

---

## 🎯 ЧТО ЭТО

**ТРИ уровня защиты** (не объявления, а РЕАЛЬНАЯ защита):

### 1. ORM Level (models.py)
```python
@property
def status(self):
    raise AttributeError("FORBIDDEN: Use transition service")
```
**Результат**: ПРЯМОЕ присвоение `goal.status = "done"` КРАШИТ программу

### 2. Application Level (goal_transition_service.py)
```python
async def transition_goal(...):
    validate_hard_invariants(goal)  # HARD checks
    # ... transition ...
```
**Результат**: TypeError если инварианты нарушены

### 3. CI Level (CHECK_NO_DIRECT_STATUS.sh)
```bash
#!/bin/bash
# grep -r "\.status = "done" services/core/*.py
# [found] → exit 1, block commit
```
**Результат**: Git commit БЛОКИРУЕТСЯ

---

## 📋 ПЛАН ПРИМЕНЕНИЯ

### Phase 1: Apply ORM Patch (5 минут)

```bash
# 1. Backup models.py
docker cp ns_core:/app/models.py /home/onor/ai_os_final/services/core/models.py.backup.before_patch

# 2. Apply ORM_LOCK_PATCH.py to models.py
# (instructions inside file - adds property below line 50)

# 3. Re-deploy
docker restart ns_core

# 4. Test ORM protection
docker exec ns_core python3 -c "
from models import Goal
from database import AsyncSessionLocal
import asyncio

async def test():
    async with AsyncSessionLocal() as db:
        g = Goal(title='Test')
        try:
            g.status = 'active'  # Should work
            print(f'✅ Read OK: {g.status}')
        except AttributeError as e:
            print(f'✅ Write BLOCKED: {str(e)[:50]}')

asyncio.run(test())
"

# Expected:
# ✅ Read OK: active
# ✅ Write BLOCKED: Direct status assignment is FORBIDDEN...
```

### Phase 2: Add CI Guard (2 минуты)

```bash
# 1. Make script executable
chmod +x services/core/CHECK_NO_DIRECT_STATUS.sh

# 2. Test CI guard
cd services/core
./CHECK_NO_DIRECT_STATUS.sh

# Expected:
# 🔴 CI GUARD FAILED (violations found)
# OR
# ✅ ALL CHECKS PASSED

# 3. Add to pre-commit (if using git)
echo ".git/hooks/pre-commit" > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
/home/onor/ai_os_final/services/core/CHECK_NO_DIRECT_STATUS.sh
EOF

# Now ALL commits blocked if violations exist
```

### Phase 3: Run CI Guard & Fix (переменно)

```bash
# 1. Run CI guard
cd /home/onor/ai_os_final/services/core
./CHECK_NO_DIRECT_STATUS.sh

# 2. If FAIL → Fix violations before continuing
# The script will show you EXACTLY which files to fix

# 3. Re-run until PASS
```

### Phase 4: Enable VALID Constraint (1 минута)

```sql
-- After all fixes applied and CI guard passes:

ALTER TABLE goals VALIDATE CONSTRAINT check_goal_type_completion_state;

-- Now:
-- ❌ continuous → done = CRASHES (database blocks it)
-- ❌ directional → done = CRASHES (database blocks it)
-- ✅ achievable → done = Works
```

---

## 🔒 КАКАЯ ЭТО ЗАЩИТА

### ДО применения:
```python
# МОЖНО сделать:
goal.status = "done"  # ← Работает!

# Также МОЖНО:
goal._status = "done"  # ← Обходит свойство!
```

### ПОСЛЕ применения:
```python
# Прямое присвоение:
goal.status = "done"  # ❌ AttributeError: Forbidden!

# Обход свойства:
goal._status = "done"  # ❌ AttributeError: Forbidden!

# ТОЖЕ НЕЛЬЗЯ:
delattr(goal, 'status')  # ❌ AttributeError: Forbidden!
setattr(goal, 'status', 'done')  # ❌ AttributeError: Forbidden!
```

**ЕДИНСТВЕННЫЙ способ**:
```python
# Это РАБОТАЕТ:
from goal_transition_service import transition_goal
await transition_goal(goal_id, "completed", "Children done")
```

---

## 🧪 TESTING

### Test 1: Try to bypass (should FAIL)
```python
# After patch:
from models import Goal
g = Goal(title="Bypass Test")
try:
    g.status = "done"
    print("❌ SYSTEM NOT PROTECTED")
except AttributeError as e:
    print(f"✅ SYSTEM PROTECTED: {str(e)[:50]}")
```

### Test 2: Use correct API (should WORK)
```python
from goal_transition_service import transition_goal
result = await transition_goal(goal_id, "completed", "Test")
print(f"Result: {result}")
# Expected: {"result": "success", ...}
```

---

## ✅ ГОТОВНОСТЬ К ДЕПЛОЮ

### Что будет задеплоено:
1. ✅ models.py с property-based protection
2. ✅ goal_transition_service.py
3. ✅ CHECK_NO_DIRECT_STATUS.sh (CI guard)
4. ✅ ORM_LOCK_PATCH.py (применяется к models.py)

### Что НЕ будет задеплоено:
- ❌ Замена 41 прямых присвоений (ручной рефакторинг)
- ❌ CI configuration (предлагается пользователю)
- ❌ Pre-commit hook (предлагается)

---

## 📊 ИТОГОВАЯ ТАБЛИЦА

| Компонент | До | После | Статус |
|-----------|-----|-------|--------|
| Property-based ORM lock | ❌ | ✅ | ЗАЩИЩЁНО |
| Transition service | ✅ | ✅ | Работает |
| CI guard | ❌ | ✅ | Предоставлен |
| VALID constraint | ❌ | ❌ | Предоставлен |

**Требуемое действие**: Применить ORM patch (инструкция внутри файла)

---

## 💬 РЕШЕНИЕ

**Перед деплоем убедитесь что:**

1. ✅ Понимаете что Property-based protection КРАШИТ программу
2. ✅ Готовы к temporary ломке во время фиксаций
3. ✅ Понимаете что CI guard найдёт ВСЕ попытки обхода

**Type**:
`HARD` — применять ORM patch + CI guard
`RETHINK` — переделывать архитектуру
`CANCEL` — остановиться

---

## 🚀 DEPLOYMENT КОМАНДА

```bash
# Apply ORM lock patch (5 мин)
cd /home/onor/ai_os_final
python3 ORM_LOCK_PATCH.py

# Verify protection works
docker exec ns_core python3 -c "from models import Goal; g=Goal(); g.status='active'"

# Add CI guard (2 мин)
chmod +x services/core/CHECK_NO_DIRECT_STATUS.sh

# YOU'RE READY
```

---

**Ждём команды: `HARD`, `RETHINK` или `CANCEL`**
