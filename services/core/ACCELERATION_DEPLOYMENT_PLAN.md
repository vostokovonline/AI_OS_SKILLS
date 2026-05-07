# ACCELERATION LAYER - DEPLOYMENT PLAN
==========================================

**Date**: 2026-02-11
**Mode**: Soft Observation → Controlled Intervention → Full Acceleration
**Status**: READY FOR PHASE 2 (SOFT MODE)

---

## 📊 ТЕКУЩЕЕ СОСТОЯНИЕ

### Phase 1: Controlled Evolution ✅ ГОТОВО

**Что deploy'то**:
1. ✅ `goal_transition_service.py` (361 строк) — ЕДИНАЯ точка переходов
2. ✅ `invariants_hard.py` (431 строк) — Hard invariants (I1, I2, A1)
3. ✅ `audit_logger.py` (556 строк) — Полный audit trail
4. ✅ `migrations/add_lifecycle_model.sql` — Новая модель (lifecycle_state, evaluation_state)

**Защита**:
- ✅ Все переходы через `transition_goal()`
- ✅ Hard invariants проверяются ВСЕГДА
- ✅ Аудит КАЖДОГО перехода
- ⚠️ DB constraint в режиме NOT VALID (НЕ блокирует пока)

**Результат**: Система защищена от случайных поломок, но старые цели продолжают работать.

---

### Phase 2: Acceleration Layer (SOFT MODE) ✅ ГОТОВО

**Что создано**:
1. ✅ `goal_velocity_engine.py` (411 строк)
   - Cycle time, completion rate, stagnation detection
   - НЕ меняет статусы, только измеряет

2. ✅ `strategic_drift_detector.py` (569 строк)
   - Recurrent failures, overestimation, reality deviation
   - НЕ вмешивается, только детектирует паттерны

3. ✅ `ai_intervention_layer.py` (501 строка)
   - 10-day rule detection
   - Авто-рекомендации
   - **Требует human approval для действий**

4. ✅ `acceleration_architecture.py` (467 строк)
   - Оркестрация всех слоёв
   - Баланс 30% control / 70% acceleration
   - **Read-only метрики**

**Что НЕ делает (soft mode)**:
- ❌ НЕ меняет goal.status автоматически
- ❌ НЕ использует force=True
- ❌ НЕ включает VALID constraint
- ✅ Только собирает метрики
- ✅ Только логирует наблюдения
- ✅ Только рекомендует действия

---

## 🎯 DEPLOYMENT STRATEGY

### Step 1: Deploy Phase 1 Components (СЕЙЧАС)

```bash
# 1. Скопировать transition service + invariants + audit
cd /home/onor/ai_os_final

docker cp services/core/goal_transition_service.py ns_core:/app/
docker cp services/core/invariants_hard.py ns_core:/app/
docker cp services/core/audit_logger.py ns_core:/app/

# 2. Применить миграцию БД (NOT VALID constraint)
docker exec -i ns_postgres \
  psql -U ns_admin -d ns_core_db \
  -f services/core/migrations/add_lifecycle_model.sql

# 3. Перезапустить core
docker restart ns_core

# 4. Проверить что модули загружаются
docker exec ns_core python3 -c "
from goal_transition_service import goal_transition_service
from invariants_hard import HardInvariants
from audit_logger import audit_logger
print('✅ Phase 1 modules loaded')
"
```

**Результат**: Система защищена, старые цели работают, audit trail включен.

---

### Step 2: Deploy Acceleration Layer (SOFT MODE) (СЕЙЧАС)

```bash
# 1. Скопировать acceleration components
docker cp services/core/goal_velocity_engine.py ns_core:/app/
docker cp services/core/strategic_drift_detector.py ns_core:/app/
docker cp services/core/ai_intervention_layer.py ns_core:/app/
docker cp services/core/acceleration_architecture.py ns_core:/app/

# 2. Перезапустить core
docker restart ns_core

# 3. Проверить что модули загружаются
docker exec ns_core python3 -c "
from goal_velocity_engine import goal_velocity_engine
from strategic_drift_detector import strategic_drift_detector
from ai_intervention_layer import ai_intervention_layer
from acceleration_architecture import acceleration_architecture
print('✅ Acceleration layer loaded (soft mode)')
"
```

**Результат**: Система собирает метрики, НЕ вмешивается.

---

### Step 3: Add API Endpoints (READ-ONLY)

Добавить в `main.py` endpoints для чтения метрик:

```python
# =============================================================================
# ACCELERATION LAYER ENDPOINTS (SOFT MODE - READ ONLY)
# =============================================================================

from acceleration_architecture import acceleration_architecture
from goal_velocity_engine import goal_velocity_engine
from strategic_drift_detector import strategic_drift_detector
from ai_intervention_layer import ai_intervention_layer


@app.get("/acceleration/health")
async def get_acceleration_health():
    """
    GET /acceleration/health — Full system health report

    READ-ONLY: Returns metrics, recommendations
    DOES NOT modify any goals
    """
    try:
        health = await acceleration_architecture.get_system_health()
        return health
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/acceleration/velocity")
async def get_velocity_metrics():
    """
    GET /acceleration/velocity — Velocity metrics only

    READ-ONLY: Cycle time, completion rate, stagnation
    """
    try:
        velocity = await goal_velocity_engine.calculate_velocity_metrics()
        return velocity
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/acceleration/drift")
async def get_drift_report():
    """
    GET /acceleration/drift — Drift detection report

    READ-ONLY: Recurrent failures, overestimation, patterns
    """
    try:
        drift = await strategic_drift_detector.detect_all_drifts()
        return drift
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/acceleration/interventions")
async def get_intervention_report():
    """
    GET /acceleration/interventions — Required interventions

    READ-ONLY: 10-day rule violations, recommendations
    DOES NOT apply interventions automatically
    """
    try:
        interventions = await ai_intervention_layer.scan_for_interventions()
        return interventions
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/acceleration/balance")
async def get_control_acceleration_balance():
    """
    GET /acceleration/balance — Control vs Acceleration balance

    READ-ONLY: Returns 30:70 ratio or current state
    """
    try:
        balance = await acceleration_architecture.get_control_acceleration_balance()
        return balance
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
```

**Важно**: Все endpoints READ-ONLY, не меняют состояние.

---

### Step 4: Monitor for 30 Days (НАБЛЮДЕНИЕ)

**Что делать**:
1. ✅ Проверять `/acceleration/health` ежедневно
2. ✅ Анализировать drift patterns
3. ✅ Смотреть на stagnation ratio
4. ✅ НЕ включать VALID constraint
5. ✅ НЕ давать force=True

**Что искать**:
- Какие цели систематически застревают?
- Какие типы целей overestimated?
- Есть ли recurrent failure patterns?

**Длительность**: 30 дней минимальный период для сбора статистики.

---

### Step 5: Evaluate & Decide (ПОСЛЕ 30 ДНЕЙ)

**Вариант A: Система работает хорошо**
- Нет critical drifts
- Стагнация < 20%
- Velocity stable или improving

→ **Действие**: Включить AI Intervention Layer (с human approval)

**Вариант B: Система drifting**
- Много recurrent failures
- Stagnation > 30%
- Некоторые goal types overestimated

→ **Действие**: Исправить обнаруженные проблемы, затем переоценить

**Вариант C: Критические проблемы**
- Множество critical drifts
- Stagnation > 50%
- Система не движется

→ **Действие**: PAUSE new goals, фокус на completions, emergency fixes

---

## ⚖️ СОСТОЯНИЯ СИСТЕМЫ

```
┌─────────────────────────────────────────────────────────────┐
│                                                   │
│   PHASE 1: CONTROLLED EVOLUTION ✅                   │
│   - Single transition gate                            │
│   - Hard invariants ALWAYS checked                     │
│   - Audit trail COMPLETE                              │
│   - DB constraint: NOT VALID (мягкий режим)         │
│                                                   │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                                                   │
│   PHASE 2: ACCELERATION LAYER (SOFT MODE) ✅        │
│   - Velocity metrics collected                         │
│   - Drift patterns detected                           │
│   - Interventions RECOMMENDED (not applied)           │
│   - NO automatic status changes                        │
│   - NO force=True allowed                            │
│   - READ-ONLY API endpoints                          │
│                                                   │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼ (30 days observation)
                  │
┌─────────────────────────────────────────────────────────────┐
│                                                   │
│   PHASE 3: CONTROLLED INTERVENTION (FUTURE)          │
│   - AI Intervention Layer ACTIVE                       │
│   - 10-day rule enforcements                         │
│   - Human approval REQUIRED                           │
│   - Emergency mode AVAILABLE (not auto)               │
│                                                   │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼ (when stable)
                  │
┌─────────────────────────────────────────────────────────────┐
│                                                   │
│   PHASE 4: VALID CONSTRAINT (FUTURE)                 │
│   - DB constraint VALID                                │
│   - Hard enforcement at ALL levels                    │
│   - Force=True ONLY for emergencies                   │
│                                                   │
└───────────────────────────────────────────────────────────┘
```

---

## 🎯 КОНТРОЛЬНЫЕ ТОЧКИ

### CHECK 1: Module Loading (сразу после deploy)
```bash
docker exec ns_core python3 -c "
# Phase 1
from goal_transition_service import goal_transition_service
from invariants_hard import HardInvariants
from audit_logger import audit_logger

# Phase 2
from goal_velocity_engine import goal_velocity_engine
from strategic_drift_detector import strategic_drift_detector
from ai_intervention_layer import ai_intervention_layer
from acceleration_architecture import acceleration_architecture

print('✅ ALL MODULES LOADED')
print('Phase 1: Controlled Evolution = ACTIVE')
print('Phase 2: Acceleration Layer = SOFT MODE')
"
```

### CHECK 2: API Endpoints (после рестарта)
```bash
# Проверить health endpoint
curl http://localhost:8000/acceleration/health

# Ожидаемый вывод:
{
  "overall_state": "stable",
  "confidence": 0.75,
  "velocity": {...},
  "drift": {...},
  "interventions": {...},
  "control_vs_acceleration": {
    "control": 0.30,
    "acceleration": 0.70,
    "ratio": "30:70"
  }
}
```

### CHECK 3: No Automatic Changes (ежедневно)
```bash
# Проверить что никто не использует force=True
docker logs ns_core | grep "MIGRATION MODE" | grep -v "actor='migration'"

# Должно быть пусто (или только migration actor)
```

---

## 📋 МАРКИРОВКА

**Текущий статус**: Phase 2 (SOFT MODE)
**Что можно**: Сбор метрик, рекомендации, анализ
**Что нельзя**: Auto-intervention, force=True, VALID constraint

**Философия**:
1. Phase 1 = Фундамент защиты ✅
2. Phase 2 = Наблюдение и понимание ✅
3. Phase 3 = Контролируемое вмешательство (будущее)
4. Phase 4 = Полная жёсткость (будущее, когда всё стабильно)

---

## ✅ ГОТОВНОСТЬ

**Phase 1 (Controlled Evolution)**: ✅ ГОТОВ К DEPLOY
**Phase 2 (Acceleration Soft Mode)**: ✅ ГОТОВ К DEPLOY
**API Endpoints**: ✅ ГОТОВЫ К ДОБАВЛЕНИЮ
**Transition Plan**: ✅ ОПИСАН

**Ваш выбор**: `DEPLOY_PHASE_1_AND_2` или задать вопросы

---

Type `DEPLOY_PHASE_1_AND_2` для деплоя Phase 1 + Phase 2 (soft mode),
или задайте вопросы по плану.
