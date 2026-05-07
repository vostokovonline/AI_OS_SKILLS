# Phase 1: Personality Engine Implementation Plan

**Duration:** 3-4 weeks
**Priority:** CRITICAL (блокирует другие фазы)
**Team:** 1 senior developer + AI assistance

---

## Overview

Personality Engine — ядро индивидуальности ИИ. Без него система принимает решения "для всех одинаково", а не для конкретного пользователя с его ценностями, стилем и предпочтениями.

**Цель фазы:** Создать базовую модель личности пользователя, которая будет влиять на:
1. Какие цели важнее (Goal System)
2. Как принимать решения (Decision Logic)
3. Как общаться (Interface Layer)

---

## Architecture

```
Personality Engine
├── UserProfile (database)
│   ├── core_traits (Big Five: openness, conscientiousness, ...)
│   ├── motivations (growth, achievement, comfort, ...)
│   ├── values [array] (осознанность, здоровье, ...)
│   └── preferences
│       ├── communication_style (tone, humor, detail_level, language)
│       ├── learning_style (через примеры, визуализация, ...)
│       ├── activity_patterns (active_hours, focus_span)
│       └── boundaries (no_autonomous_actions, requires_confirmation_for)
├── Value Matrix
│   ├── prioritization (сортировка целей по ценностям)
│   ├── ethical_filter (проверка решений на соответствие ценностям)
│   └── adaptation (корректировка на основе feedback)
├── Behavioral Style
│   ├── tone_calculator (вычисление тона ответов)
│   ├── humor_level (уровень юмора)
│   └── formality (формальность/неформальность)
└── Adaptation Loop
    ├── feedback_collector (сбор реакций пользователя)
    ├── pattern_analyzer (анализ паттернов)
    └── personality_updater (обновление модели)
```

---

## Week 1-2: Database Models & Basic API

### Task 1.1: Database Schema (2 days)

**File:** `services/core/models.py`

Добавить модели:

```python
class UserProfile(Base):
    """Профиль личности пользователя"""
    __tablename__ = "user_profiles"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, nullable=False)  # reference to telegram_id or system user

    # Core Traits (Big Five)
    openness = Column(Float, default=0.5)        # 0.0 - 1.0
    conscientiousness = Column(Float, default=0.5)
    extraversion = Column(Float, default=0.5)
    agreeableness = Column(Float, default=0.5)
    neuroticism = Column(Float, default=0.5)

    # Motivations
    motivation_growth = Column(Float, default=0.5)
    motivation_achievement = Column(Float, default=0.5)
    motivation_comfort = Column(Float, default=0.5)
    motivation_recognition = Column(Float, default=0.5)
    motivation_social_connection = Column(Float, default=0.5)

    # Meta
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1)

    # Relations
    values = relationship("UserValue", back_populates="profile")
    preferences = relationship("UserPreference", back_populates="profile")


class UserValue(Base):
    """Ценности пользователя (множественные)"""
    __tablename__ = "user_values"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID, ForeignKey("user_profiles.id"))
    value_name = Column(String(100))  # "осознанность", "здоровье", ...
    importance = Column(Float)  # 0.0 - 1.0

    profile = relationship("UserProfile", back_populates="values")


class UserPreference(Base):
    """Предпочтения пользователя"""
    __tablename__ = "user_preferences"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID, ForeignKey("user_profiles.id"))

    # Communication
    tone = Column(String(50))  # "спокойный", "вдохновляющий", "деловой"
    humor = Column(String(50))  # "нет", "умеренный", "высокий"
    detail_level = Column(String(50))  # "минимальный", "средний", "подробный"
    language = Column(String(10))  # "ru", "en"

    # Learning
    learning_style = Column(String(100))  # "через примеры", "визуализация", ...

    # Activity
    active_hours = Column(JSON)  # ["07:00-11:00", "18:00-21:00"]
    focus_span = Column(String(20))  # "45-60 мин"

    # Boundaries
    no_autonomous_actions = Column(Boolean, default=True)
    requires_confirmation_for = Column(JSON)  # ["email_send", "financial_ops"]

    profile = relationship("UserProfile", back_populates="preferences")


class PersonalityFeedback(Base):
    """Feedback для адаптации личности"""
    __tablename__ = "personality_feedback"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID, ForeignKey("user_profiles.id"))

    # Событие
    event_type = Column(String(50))  # "goal_completed", "decision_approved", ...
    context = Column(JSON)  # детали события

    # Реакция пользователя
    reaction = Column(String(20))  # "positive", "negative", "neutral"
    correction = Column(Text)  # текст корректировки

    timestamp = Column(DateTime, default=datetime.utcnow)
```

**Migration:** Создать alembic миграцию

### Task 1.2: Personality Engine Core (3 days)

**File:** `services/core/personality_engine.py` (новый)

```python
"""
Personality Engine — ядро индивидуальности ИИ.

Управляет моделью личности пользователя:
- Хранит и обновляет профиль (ценности, стиль, предпочтения)
- Предоставляет данные другим модулям (Goal System, Decision Logic)
- Адаптируется на основе feedback
"""
from typing import Optional, Dict, List
from sqlalchemy import select
from database import AsyncSessionLocal
from models import UserProfile, UserValue, UserPreference, PersonalityFeedback
from pydantic import BaseModel
from datetime import datetime


class PersonalityProfile(BaseModel):
    """Pydantic модель для API"""
    user_id: str
    core_traits: Dict[str, float]
    motivations: Dict[str, float]
    values: List[Dict[str, str]]
    preferences: Dict[str, any]
    version: int


class PersonalityEngine:
    """Главный класс Personality Engine"""

    async def get_profile(self, user_id: str) -> Optional[PersonalityProfile]:
        """Получить профиль пользователя"""
        async with AsyncSessionLocal() as db:
            # Profile
            stmt = select(UserProfile).where(UserProfile.user_id == user_id)
            result = await db.execute(stmt)
            profile_db = result.scalar_one_or_none()

            if not profile_db:
                # Создать дефолтный профиль
                profile_db = await self._create_default_profile(db, user_id)

            # Values
            stmt_vals = select(UserValue).where(UserValue.profile_id == profile_db.id)
            result_vals = await db.execute(stmt_vals)
            values_db = result_vals.scalars().all()

            # Preferences
            stmt_prefs = select(UserPreference).where(UserPreference.profile_id == profile_db.id)
            result_prefs = await db.execute(stmt_prefs)
            prefs_db = result_prefs.scalar_one_or_none()

            # Конвертировать в Pydantic
            return PersonalityProfile(
                user_id=profile_db.user_id,
                core_traits={
                    "openness": profile_db.openness,
                    "conscientiousness": profile_db.conscientiousness,
                    "extraversion": profile_db.extraversion,
                    "agreeableness": profile_db.agreeableness,
                    "neuroticism": profile_db.neuroticism,
                },
                motivations={
                    "growth": profile_db.motivation_growth,
                    "achievement": profile_db.motivation_achievement,
                    "comfort": profile_db.motivation_comfort,
                    "recognition": profile_db.motivation_recognition,
                    "social_connection": profile_db.motivation_social_connection,
                },
                values=[{"name": v.value_name, "importance": v.importance} for v in values_db],
                preferences={
                    "communication_style": {
                        "tone": prefs_db.tone if prefs_db else "спокойный",
                        "humor": prefs_db.humor if prefs_db else "умеренный",
                        "detail_level": prefs_db.detail_level if prefs_db else "средний",
                        "language": prefs_db.language if prefs_db else "ru",
                    },
                    "learning_style": prefs_db.learning_style if prefs_db else "через примеры",
                    "activity_patterns": {
                        "active_hours": prefs_db.active_hours if prefs_db else ["09:00-18:00"],
                        "focus_span": prefs_db.focus_span if prefs_db else "45-60 мин",
                    },
                    "boundaries": {
                        "no_autonomous_actions": prefs_db.no_autonomous_actions if prefs_db else True,
                        "requires_confirmation_for": prefs_db.requires_confirmation_for if prefs_db else [],
                    }
                } if prefs_db else {},
                version=profile_db.version
            )

    async def _create_default_profile(self, db, user_id: str) -> UserProfile:
        """Создать дефолтный профиль для нового пользователя"""
        profile = UserProfile(
            user_id=user_id,
            # Средние значения по умолчанию
            openness=0.5,
            conscientiousness=0.5,
            extraversion=0.5,
            agreeableness=0.5,
            neuroticism=0.5,
            motivation_growth=0.7,
            motivation_achievement=0.6,
            motivation_comfort=0.5,
            motivation_recognition=0.4,
            motivation_social_connection=0.6,
        )
        db.add(profile)
        await db.flush()

        # Дефолтные ценности
        default_values = [
            {"name": "осознанность", "importance": 0.8},
            {"name": "здоровье", "importance": 0.7},
            {"name": "саморазвитие", "importance": 0.7},
            {"name": "честность", "importance": 0.8},
            {"name": "эффективность", "importance": 0.6},
        ]
        for val in default_values:
            db.add(UserValue(
                profile_id=profile.id,
                value_name=val["name"],
                importance=val["importance"]
            ))

        # Дефолтные предпочтения
        prefs = UserPreference(
            profile_id=profile.id,
            tone="спокойный",
            humor="умеренный",
            detail_level="средний",
            language="ru",
            learning_style="через примеры",
            active_hours=["09:00-18:00"],
            focus_span="45-60 мин",
            no_autonomous_actions=True,
            requires_confirmation_for=["email_send", "financial_ops"]
        )
        db.add(prefs)

        await db.commit()
        return profile

    async def update_profile(self, user_id: str, updates: Dict) -> PersonalityProfile:
        """Обновить профиль"""
        async with AsyncSessionLocal() as db:
            stmt = select(UserProfile).where(UserProfile.user_id == user_id)
            result = await db.execute(stmt)
            profile = result.scalar_one_or_none()

            if not profile:
                raise ValueError(f"Profile not found for user {user_id}")

            # Обновить версию
            profile.version += 1
            profile.updated_at = datetime.utcnow()

            # Обновить поля
            if "core_traits" in updates:
                for trait, value in updates["core_traits"].items():
                    setattr(profile, trait, value)

            if "motivations" in updates:
                for motivation, value in updates["motivations"].items():
                    setattr(profile, f"motivation_{motivation}", value)

            await db.commit()
            await db.refresh(profile)

            return await self.get_profile(user_id)

    async def record_feedback(self, user_id: str, event_type: str,
                            reaction: str, context: Dict = None,
                            correction: str = None):
        """Записать feedback для адаптации"""
        async with AsyncSessionLocal() as db:
            # Найти профиль
            stmt = select(UserProfile).where(UserProfile.user_id == user_id)
            result = await db.execute(stmt)
            profile = result.scalar_one_or_none()

            if not profile:
                return

            feedback = PersonalityFeedback(
                profile_id=profile.id,
                event_type=event_type,
                context=context or {},
                reaction=reaction,
                correction=correction
            )
            db.add(feedback)
            await db.commit()

    async def get_value_matrix(self, user_id: str) -> Dict[str, float]:
        """Получить матрицу ценностей для Decision Logic"""
        profile = await self.get_profile(user_id)
        return {v["name"]: v["importance"] for v in profile.values}

    async def get_communication_style(self, user_id: str) -> Dict:
        """Получить стиль общения для Interface Layer"""
        profile = await self.get_profile(user_id)
        return profile.preferences.get("communication_style", {})
```

### Task 1.3: API Endpoints (2 days)

**File:** `services/core/main.py`

Добавить endpoints:

```python
@router.get("/personality/{user_id}")
async def get_personality_profile(user_id: str):
    """Получить профиль личности"""
    engine = PersonalityEngine()
    profile = await engine.get_profile(user_id)
    return profile


@router.put("/personality/{user_id}")
async def update_personality_profile(user_id: str, updates: Dict):
    """Обновить профиль личности"""
    engine = PersonalityEngine()
    profile = await engine.update_profile(user_id, updates)
    return profile


@router.post("/personality/{user_id}/feedback")
async def record_personality_feedback(user_id: str, event_type: str,
                                      reaction: str, context: Dict = None,
                                      correction: str = None):
    """Записать feedback"""
    engine = PersonalityEngine()
    await engine.record_feedback(user_id, event_type, reaction, context, correction)
    return {"status": "recorded"}


@router.get("/personality/{user_id}/values")
async def get_value_matrix(user_id: str):
    """Получить матрицу ценностей (для Decision Logic)"""
    engine = PersonalityEngine()
    return await engine.get_value_matrix(user_id)


@router.get("/personality/{user_id}/communication")
async def get_communication_style(user_id: str):
    """Получить стиль общения (для Interface Layer)"""
    engine = PersonalityEngine()
    return await engine.get_communication_style(user_id)
```

---

## Week 2-3: Integration with Goal System

### Task 2.1: Goal Prioritization by Values (2 days)

**File:** `services/core/goal_decomposer.py`

Изменить логику приоритизации подцелей:

```python
async def _generate_subgoals(self, goal: Goal) -> List[Dict]:
    """Генерирует подцели с учетом ценностей пользователя"""

    # Получить профиль пользователя
    engine = PersonalityEngine()
    value_matrix = await engine.get_value_matrix(goal.user_id)

    # Добавить в промпт контекст ценностей
    values_context = "\n".join([
        f"- {name} (важность: {importance})"
        for name, importance in value_matrix.items()
    ])

    decomposition_prompt = f"""
    Ты - эксперт по декомпозиции целей.

    Цель пользователя: {goal.title}
    Описание: {goal.description}

    ЦЕННОСТИ ПОЛЬЗОВАТЕЛЯ:
    {values_context}

    При декомпозиции учитывай:
    1. Подцели должны быть согласованы с ценностями
    2. Приоритет отдавай целям, соответствующим топ-3 ценностям
    3. Избегай конфликтов с ценностями

    ВЕРНИ ТОЛЬКО JSON:
    {{
        "subgoals": [...],
        "reasoning": "..."
    }}
    """

    # ... LLM вызов
```

### Task 2.2: Goal-Value Conflict Detection (1 day)

**File:** `services/core/goal_contract_validator.py` (новая функция)

```python
async def check_goal_value_conflict(goal: Goal, user_id: str) -> List[str]:
    """Проверить цель на конфликты с ценностями"""

    engine = PersonalityEngine()
    value_matrix = await engine.get_value_matrix(user_id)

    # LLM вызов для анализа конфликта
    prompt = f"""
    Цель: {goal.title}
    Описание: {goal.description}

    Ценности пользователя:
    {value_matrix}

    Есть ли конфликты между целью и ценностями?
    Если да, перечисли их.

    Верни JSON:
    {{
        "conflicts": ["список конфликтов или пустой"]
    }}
    """

    # LLM вызов и парсинг
    # ...
```

---

## Week 3: Integration with Decision Logic (Supervisor)

### Task 3.1: Value-Based Agent Routing (2 days)

**File:** `services/core/agent_graph.py`

Изменить supervisor_node:

```python
async def supervisor_node(state):
    # ... existing code ...

    # Получить профиль пользователя
    engine = PersonalityEngine()
    value_matrix = await engine.get_value_matrix(user_id)

    # Добавить ценности в промпт
    values_str = ", ".join([f"{name}({importance:.1f})"
                            for name, importance in value_matrix.items()])

    instruction = f"""
    ...
    ЦЕННОСТИ ПОЛЬЗОВАТЕЛЯ: {values_str}

    При выборе агента учитывай:
    - Если ценность "осознанность" > 0.7 → предпочти Intelligence (глубокий анализ)
    - Если "эффективность" > 0.7 → предпочти Coder (быстрое выполнение)
    - Если "социальная связь" > 0.7 → предпочти Coach или PM

    OUTPUT FORMAT:
    ...
    """

    # ...
```

### Task 3.2: Ethical Filter (2 days)

**File:** `services/core/decision_logic.py` (новый)

```python
"""
Decision Logic с учетом ценностей и этики.
"""
from personality_engine import PersonalityEngine


class EthicalFilter:
    """Этический фильтр решений"""

    async def check_decision(self, decision: Dict, user_id: str) -> Dict:
        """
        Проверить решение на соответствие ценностям.

        Возвращает:
        {
            "allowed": bool,
            "reason": str,
            "adjusted_decision": Dict or None
        }
        """
        engine = PersonalityEngine()
        value_matrix = await engine.get_value_matrix(user_id)
        preferences = await engine.get_profile(user_id)
        boundaries = preferences.preferences.get("boundaries", {})

        # Проверка границ
        if boundaries.get("no_autonomous_actions"):
            if decision.get("autonomous", False):
                return {
                    "allowed": False,
                    "reason": "Пользователь запретил автономные действия",
                    "adjusted_decision": None
                }

        # Проверка конкретных действий
        requires_confirmation = boundaries.get("requires_confirmation_for", [])
        for action in requires_confirmation:
            if action in str(decision.get("actions", [])):
                decision["requires_confirmation"] = True

        # Проверка по ценностям (простая версия)
        # TODO: углубить логику
        return {
            "allowed": True,
            "reason": "OK",
            "adjusted_decision": decision
        }
```

---

## Week 3-4: Interface Integration

### Task 4.1: Adaptive Tone (2 days)

**File:** `services/core/agents/prompts.py`

Добавить динамические промпты:

```python
async def get_system_prompt_with_personality(role: str, user_id: str) -> str:
    """Получить системный промпт с учетом личности"""

    base_prompt = await get_prompt(role)

    engine = PersonalityEngine()
    profile = await engine.get_profile(user_id)
    comm_style = profile.preferences.get("communication_style", {})

    tone = comm_style.get("tone", "спокойный")
    humor = comm_style.get("humor", "умеренный")
    detail = comm_style.get("detail_level", "средний")

    personality_instruction = f"""

    ТОН ОБЩЕНИЯ:
    - Тон: {tone}
    - Юмор: {humor}
    - Детальность: {detail}

    Адаптируй свои ответы под этот стиль.
    """

    return base_prompt + personality_instruction
```

### Task 4.2: Dashboard v2 Integration (2 days)

**File:** `services/dashboard_v2/src/components/profile/PersonalityPanel.tsx` (новый)

Отобразить профиль пользователя и позволить редактировать:

```typescript
interface PersonalityPanelProps {
  userId: string;
}

export const PersonalityPanel: React.FC<PersonalityPanelProps> = ({ userId }) => {
  const [profile, setProfile] = useState<PersonalityProfile | null>(null);

  useEffect(() => {
    fetchPersonalityProfile(userId).then(setProfile);
  }, [userId]);

  if (!profile) return <Loading />;

  return (
    <div className="personality-panel">
      <h2>Профиль личности</h2>

      <section>
        <h3>Ключевые черты</h3>
        <TraitBar label="Открытость" value={profile.core_traits.openness} />
        <TraitBar label="Добросовестность" value={profile.core_traits.conscientiousness} />
        {/* ... */}
      </section>

      <section>
        <h3>Ценности</h3>
        {profile.values.map(v => (
          <ValueBadge key={v.name} name={v.name} importance={v.importance} />
        ))}
      </section>

      <section>
        <h3>Предпочтения</h3>
        <CommStyleEditor style={profile.preferences.communication_style} />
      </section>

      <Button onClick={() => editProfile(userId)}>Редактировать</Button>
    </div>
  );
};
```

---

## Week 4: Testing & Documentation

### Task 5.1: Unit Tests (2 days)

**File:** `services/core/tests/test_personality_engine.py` (новый)

```python
import pytest
from personality_engine import PersonalityEngine


@pytest.mark.asyncio
async def test_create_default_profile():
    """Создание дефолтного профиля"""
    engine = PersonalityEngine()
    profile = await engine.get_profile("test-user-123")

    assert profile is not None
    assert profile.user_id == "test-user-123"
    assert len(profile.values) == 5  # дефолтные ценности


@pytest.mark.asyncio
async def test_update_profile():
    """Обновление профиля"""
    engine = PersonalityEngine()

    updated = await engine.update_profile("test-user-123", {
        "core_traits": {"openness": 0.8}
    })

    assert updated.core_traits["openness"] == 0.8


@pytest.mark.asyncio
async def test_value_matrix():
    """Получение матрицы ценностей"""
    engine = PersonalityEngine()
    matrix = await engine.get_value_matrix("test-user-123")

    assert "осознанность" in matrix
    assert matrix["осознанность"] >= 0.0
    assert matrix["осознанность"] <= 1.0
```

Запуск: `pytest services/core/tests/test_personality_engine.py`

### Task 5.2: Integration Test (1 day)

**File:** `services/core/tests/test_personality_integration.py`

Тест интеграции с Goal System:

```python
@pytest.mark.asyncio
async def test_goal_prioritization_with_values():
    """Цели приоритизируются по ценностям"""

    # Создать пользователя с ценностью "здоровье" = 0.9
    engine = PersonalityEngine()
    await engine.update_profile("health-user", {
        "values": [{"name": "здоровье", "importance": 0.9}]
    })

    # Создать цель "Начать бегать по утрам"
    # Декомпозировать
    # Проверить, что подцели связаны со здоровьем

    # TODO: реализовать
```

### Task 5.3: Documentation (2 days)

Обновить:
1. CLAUDE.md — добавить раздел про Personality Engine
2. API.md — описать новые endpoints
3. ARCHITECTURE_ROADMAP.md — отметить Phase 1 как completed

---

## Success Criteria

Фаза считается завершённой, когда:

1. ✅ UserProfile сохраняется в БД с корректными миграциями
2. ✅ API endpoints работают (проверить через curl/Postman)
3. ✅ Goal System учитывает ценности при декомпозиции
4. ✅ Supervisor (agent_graph.py) использует ценности при маршрутизации
5. ✅ Dashboard v2 отображает профиль личности
6. ✅ Unit tests покрывают >80% кода PersonalityEngine
7. ✅ Интеграционные тесты проходят
8. ✅ Документация обновлена

---

## Risk Mitigation

| Риск | Митигация |
|------|-----------|
| Сложность определения ценностей из диалогов | Начать с explicit declaration (пользователь заполняет анкету) |
| Проблемы с адаптацией (Feedback Loop) | Отложить до Phase 2, сначала статический профиль |
| Конфликты ценностей с целями | Simple warning в UI, не блокировать создание цели |

---

## Next Phase

После завершения Phase 1:
1. Phase 2: Enhanced Decision Logic (Option Generator, Ethical Filter, XAI)
2. Phase 3: Emotional Layer (потребуется Personality Engine как база)

---

**Автор:** Claude (AI-OS Architecture Team)
**Дата:** 2026-01-27
**Статус:** Ready for Implementation
