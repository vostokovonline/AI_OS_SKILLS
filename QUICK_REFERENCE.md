# AI-OS Quick Reference для обсуждения с LLM

**Дата:** 31 января 2026

---

## 🎯 One-Pager: Суть системы

**AI-OS v3.0** = Goal Execution System с AI-агентами
- **Главная фича:** Декомпозирует цели (Mission → Strategic → Operational → Atomic) и выполняет их через специализированных агентов
- **Технологии:** FastAPI, LangGraph, 11 агентов, PostgreSQL + Neo4j + Milvus, React Dashboard
- **Зрелость:** ~40% идеальной NS1/NS2 архитектуры

---

## ✅ Что уже работает (Highlights)

### 1. Goal System v3.0 ⭐
- Иерархия: L0 (Mission) → L1 (Strategic) → L2 (Operational) → L3 (Atomic)
- 5 типов: achievable, continuous, directional, exploratory, meta
- Goal Contracts (формальные ограничения)
- Strict Evaluator (проверка выполнения)
- Reflector (causal анализ)
- Artifact Layer (верифицируемые результаты)

### 2. Agent System ⭐
- 11 агентов: Supervisor, Coder, Researcher, Designer, Coach, Innovator, ...
- LangGraph оркестрация
- Skills с контрактами
- Tool calling + MCP

### 3. Memory & Knowledge
- Neo4j (граф) + Milvus (vector) + MinIO (files)
- Memory service (unified API)

### 4. Dashboard v2
- ReactFlow graph visualization
- Inspector panel + artifact modal
- Filter toolbar (atomic goals filter)

---

## 🚧 В разработке (In Progress)

### Personality Engine (Phase 1)
**Что сделано:**
- ✅ UserProfile (Big Five, motivations, values, preferences)
- ✅ Personality Snapshots (версионирование)
- ✅ Contextual Memory (короткосрочная память)
- ✅ Goal Conflict Detection (4 типа)
- ✅ Personality-aware agent prompts

**Что нужно:**
- 🟡 Value Matrix → Goal Contracts
- 🟡 Ethical Filter в Decision Logic
- 🟡 Feedback loop для адаптации

### Temporal.io Integration
**План:**
- Phase 1: Continuous Goals (Cron workflows)
- Phase 2: Mission-level Goals (Long-running)
- Phase 3: Dashboard v2 integration

---

## 📋 Roadmap (7 фаз)

| Фаза | Тема | Длительность | Приоритет |
|------|------|--------------|-----------|
| 1 | Personality Engine | 3-4 недели | 🔴 CRITICAL |
| 2 | Enhanced Decision Logic | 2-3 недели | 🟡 HIGH |
| 3 | Emotional Layer | 4-5 недель | 🔴 CRITICAL |
| 4 | Enhanced Self-Reflection | 2-3 недели | 🟡 HIGH |
| 5 | Cognitive Layer | 3-4 недели | 🟢 MEDIUM |
| 6 | Growth Layer | 4-6 недель | 🟢 MEDIUM |
| 7 | Interface Enhancements | 2-3 недели | 🟢 MEDIUM |

---

## 🎯 Gap Analysis (Критичные пробелы)

### 🔴 Critical (блокируют развитие)
1. **Emotional Layer** (5% зрелости)
   - Нет emotion recognition/simulation/regulation
   - Нет affective memory
   - Нет эмпатии в ответах

2. **Personality Integration** (средняя)
   - Personality Engine создан, но слабо интегрирован
   - Нет Value Matrix в Goal Contracts
   - Нет Behavioral Style adaptation

3. **Continual Learning** (отсутствует)
   - Нет адаптации LLM на основе опыта
   - Нет meta-learning

### 🟡 Medium (ограничивают возможности)
1. **Decision Logic** (базовый)
   - Нет Option Generator
   - Нет многомерного скоринга
   - Нет XAI (объяснений)

2. **Memory Architecture** (неполный)
   - Нет явного разделения типов памяти
   - Нет Affective Memory

---

## 💬 Ключевые вопросы для LLM

### Стратегия
1. **Какой приоритет фаз?**
   - Вариант A: Завершить Personality → Emotional → Growth
   - Вариант B: Personality + Emotional параллельно
   - Вариант C: Сначала Temporal для стабильности

2. **Emotional Layer - как подойти?**
   - NLP модель для emotion recognition?
   - Как собрать данные для обучения?
   - Какой минимальный viable вариант?

3. **Continual Learning - нужно ли?**
   - Fine-tuning LLM или RAG достаточно?
   - Как избежать catastrophic forgetting?

### Тактика
4. **Temporal.io - запускать сейчас?**
   - Преимущества: Гарантированное выполнение continuous goals
   - Риски: Сложность архитектуры

5. **Testing - как тестировать личность?**
   - Unit тесты для Personality Engine?
   - Integration тесты для Goal + Personality?

---

## 📊 Текущая зрелость

```
Core (Goal System):     60% ████████░░░░░░░░░░░░
Cognitive (Memory):     30% ███░░░░░░░░░░░░░░░░░
Emotional:               5% ░░░░░░░░░░░░░░░░░░░░
Behavioral (Agents):    70% ███████████░░░░░░░░
Growth:                 10% ░░░░░░░░░░░░░░░░░░░░
Interface:              50% ██████████░░░░░░░░░

Overall:                40% ████████████░░░░░░░░
```

**Цель:** ~82% через 6-7 месяцев (после Phase 1-7)

---

## 🔑 Ключевые файлы

### Core
- `services/core/models.py` - Database models (Goal, UserProfile, Artifact, ...)
- `services/core/goal_decomposer.py` - Декомпозиция целей
- `services/core/goal_executor.py` - Выполнение целей
- `services/core/goal_strict_evaluator.py` - Проверка результатов
- `services/core/goal_reflector.py` - Рефлексия

### Agents
- `services/core/agent_graph.py` - LangGraph оркестрация
- `services/core/agents/prompts.py` - Промпты агентов

### Personality (NEW)
- `services/core/personality_engine.py` - Personality Engine
- `services/core/goal_conflicts.py` - Conflict Detection

### Temporal (PLANNED)
- `services/temporal/workflows/` - Temporal workflows
- `services/temporal/activities/` - Temporal activities

### Frontend
- `services/dashboard_v2/` - React Dashboard v2

---

## 📚 Полная документация

- `STATUS_AND_PLANS_SUMMARY.md` - Полный обзор
- `ARCHITECTURE_ROADMAP.md` - Детальный roadmap
- `DEVELOPMENT_PLAN.md` - Temporal.io план
- `PHASE1_PERSONALITY_ENGINE.md` - Personality Engine детали
- `CLAUDE.md` - Project overview + development patterns

---

## 🚀 Quick Start для обсуждения

**Шаг 1:** Прочитай STATUS_AND_PLANS_SUMMARY.md (полная картина)
**Шаг 2:** Задай вопросы из раздела "Ключевые вопросы для LLM"
**Шаг 3:** Вместе разработаем план следующих 2-4 недель

**Happy brainstorming! 🧠**
