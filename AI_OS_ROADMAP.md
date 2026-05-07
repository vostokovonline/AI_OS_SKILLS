# 🧠 AI-OS Roadmap — От Execution Engine до Startup Factory

## Реальное техническое состояние (на 2026-03-05)

### Фактическая статистика системы

| Метрика | Значение |
|---------|----------|
| Goals (total) | 28 |
| Goals (done) | 20 |
| Goals (pending) | 5 |
| Goals (active) | 2 |
| Goals (blocked) | 1 |
| V3 Executions | 8+ |
| V3 Success Rate | 100% |
| Avg Duration | ~1s |
| Executions recorded | 761 |
| Experiences recorded | 3 |
| Skill stats entries | 1 (⚠️ broken - skill_id = "unknown") |

---

## Фаза 1 — Stabilized Execution Engine

**Статус:** 🔄 Требует доработки

### Что уже есть (подтверждено)

- ✅ Goals (создание, выполнение, оценка)
- ✅ Skills (registry, selection, execution)
- ✅ Execution pipeline (V3)
- ✅ Evaluation (confidence, passed/failed)
- ✅ Artifacts (verification, storage)
- ✅ Basic skill selection (scoring-based)
- ✅ Execution table (4+ записей)
- ✅ Skill stats table (записывается)
- ✅ Experiences table (4 записи - начали записываться)
- ✅ ExecutionPolicy (выделен в отдельный слой)

### Проблемы Phase 1

#### 1.1 Skill ID Tracking — ✅ ИСПРАВЛЕНО

**Было:** skill_id = "unknown" для всех записей

**Стало:** skill_id = "core.echo" для успешных записей

**Решение:** Добавлена логика обработки случаев когда skill не выбран (early errors)

#### 1.2 Experience Recording — ✅ ИСПРАВЛЕНО

**Было:** 3 experiences при 761 executions

**Стало:** 4 experiences (и растет)

**Решение:** Analytics recording вызывается после каждого V3 execution

#### 1.2 Retry Strategy — ОТСУТСТВУЕТ

```
Текущее поведение:
skill fails → execution = fail
```

**Нужно:**
```
skill fails → try next skill → ...
```

Цепочка:
```
web_research → llm_research → fallback → error
```

#### 1.3 Skill Ranking — Частично

Текущий scoring:
```python
score = capability_match + artifact_match
```

**Нужно добавить:**
- Historical success rate
- Latency penalty

```python
def calculate_skill_score(skill, requirements, history):
    score = 0
    
    # Capability match (существует)
    score += capability_match_score * 5
    
    # Artifact match (существует)
    score += artifact_match_score * 3
    
    # Historical success rate (ДОБАВИТЬ)
    success_rate = get_skill_success_rate(skill)
    score += success_rate * 10
    
    # Latency penalty (ДОБАВИТЬ)
    avg_latency = get_skill_avg_latency(skill)
    if avg_latency > 2000:
        score -= 5
    
    return score
```

### Результат фазы

```
AI-OS = стабильный execution engine с метриками
Метрики: работают (4+ executions, 4+ experiences)
ExecutionPolicy: выделен в отдельный слой
Готовность: 85%
```

### 1.5 ExecutionPolicy (Архитектурное улучшение)

**Создан:** `execution_policy.py`

**Компоненты:**
- `ExecutionPolicy` - базовый абстрактный класс
- `DefaultExecutionPolicy` - текущая логика выбора
- `LearningExecutionPolicy` - с учетом истории (готово к использованию)

**Зачем:**
- A/B testing стратегий выбора
- Policy learning со временем
- Легкая подмена алгоритмов

```python
# Использование
from execution_policy import get_execution_policy, use_learning_policy

# Текущая политика
policy = get_execution_policy()

# Переключиться на обучающуюся
use_learning_policy()
```

---

## Фаза 2 — Experience Layer

**Статус:** 🔄 Таблицы созданы, данные есть (3 записи)

**Цель:** Система запоминает опыт выполнения задач.

### 2.1 Текущее состояние

```sql
-- Таблица существует
SELECT COUNT(*) FROM experiences;
-- 3 записи
```

**Проблема:** Всего 3 записи при 761 executions

**Причина:** Experience recording вызывается не после каждого execution

### 2.2 Pattern Extraction — ОТСУТСТВУЕТ

Нужно реализовать:
```python
def detect_patterns():
    patterns = []
    
    # Анализировать research goals
    research_goals = query("""
        SELECT skill_used, success_rate, avg_duration
        FROM experiences
        WHERE goal_type = 'research'
    """)
    
    return patterns
```

### 2.3 Experience Index (Vector) — ОТСУТСТВУЕТ

```sql
-- Пока не создано
CREATE TABLE experience_embeddings (
    experience_id INT REFERENCES experiences(experience_id),
    goal_embedding VECTOR(384),
    execution_outcome JSONB,
    skill_used VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Результат фазы

```
Система начинает понимать: "что работает лучше"
Готовность: 30%
```

---

## Фаза 3 — Reflection Layer

**Статус:** 🔄 Планируется

**Цель:** Система анализирует выполнение и предлагает улучшения.

### 3.1 Reflection Agent

После каждого выполнения:
```
execution → reflection
```

**Вопросы reflection:**
- Что пошло хорошо?
- Что пошло плохо?
- Можно ли сделать быстрее?
- Есть ли лучший skill?

### 3.2 Reflection Output

```python
class ReflectionResult:
    what_worked_well: List[str]
    what_failed: List[str]
    suggestions: List[str]
    skill_requests: List[str]  # "нужен skill для X"
    goal_patterns: List[str]
```

### 3.3 Integration

```python
async def after_execution(goal, result):
    reflection = await reflection_agent.analyze(goal, result)
    
    if reflection.skill_requests:
        await skill_generator.queue_request(reflection.skill_requests)
    
    await experience_layer.record(reflection)
```

### Результат фазы

```
AI-OS начинает сам улучшать свою архитектуру
Готовность: 0%
```

---

## Фаза 4 — Skill Evolution

**Статус:** 🔄 Планируется

**Цель:** Система улучшает существующие skills.

### 4.1 Skill Mutation

```
web_research_v1 → система создаёт → web_research_v2
```

**Улучшения v2:**
- Better scraping
- More sources
- Parallel search

### 4.2 A/B Testing

```python
async def ab_test_skill(skill_v1, skill_v2, test_goals):
    results_v1 = []
    results_v2 = []
    
    for goal in test_goals:
        results_v1.append(await skill_v1.execute(goal))
        results_v2.append(await skill_v2.execute(goal))
    
    v1_score = calculate_score(results_v1)
    v2_score = calculate_score(results_v2)
    
    return "v2" if v2_score > v1_score else "v1"
```

### 4.3 Skill Promotion

```python
def should_promote(v2, v1):
    if v2.success_rate > v1.success_rate * 1.1:
        return True
    if v2.avg_latency < v1.avg_latency * 0.8:
        return True
    return False
```

### Результат фазы

```
Система эволюционирует навыки
Готовность: 0%
```

---

## Фаза 5 — Skill Generation

**Статус:** 🔄 Планируется

**Цель:** Система создаёт новые skills.

### 5.1 Skill Request Pipeline

```
reflection: "нужен academic_search"
         → skill_generator
```

### 5.2 Skill Generator

LLM генерирует новый skill:

```python
class GeneratedSkill:
    name: str
    capabilities: List[str]
    produces: List[str]
    code: str
    tests: List[str]
    metadata: dict
```

### 5.3 Auto Tests

```python
def generate_tests(skill):
    return [
        test_valid_input(),
        test_empty_input(),
        test_timeout(),
        test_invalid_format()
    ]
```

### 5.4 Sandbox Execution

```python
async def sandbox_test(skill, tests):
    results = []
    for test in tests:
        result = await run_in_sandbox(skill, test)
        results.append(result)
    
    success_rate = sum(r.passed for r in results) / len(results)
    
    if success_rate >= 0.8:
        await skill_registry.register(skill)
    
    return results
```

### Результат фазы

```
AI-OS становится саморасширяемой системой
Готовность: 0%
```

---

## Фаза 6 — Goal Intelligence Layer

**Статус:** 🔄 Планируется

**Цель:** Система умно управляет задачами.

### 6.1 Goal Optimizer

```
research → analysis → report
```

### 6.2 Goal Decomposition

```
"market research" 
  ↓
collect_data (skill: web_research)
analyze_competitors (skill: competitor_analysis)  
summarize_trends (skill: llm_summary)
```

### 6.3 Goal Prioritization

- Impact (влияние)
- Effort (затраты)
- Dependencies (зависимости)

### Результат фазы

```
AI-OS начинает думать стратегически
Готовность: 0%
```

---

## Фаза 7 — Startup Factory

**Статус:** 🔄 Vision

**Цель:** AI-OS генерирует стартапы.

### Pipeline

```
trend research
    ↓
problem detection
    ↓
solution generation
    ↓
market validation
    ↓
MVP build
```

### Required Skills

```yaml
skills:
  - market_research: Поиск рыночных трендов
  - competitor_analysis: Анализ конкурентов
  - idea_generation: Генерация идей
  - mvp_builder: Создание MVP
  - landing_page_builder: Создание лендингов
```

### Output

```json
{
  "startup_name": "AI-CodeReview",
  "problem": "Developers spend 30% time on code reviews",
  "solution": "AI-powered code review assistant",
  "market_size": "$5B",
  "mvp_features": ["GitHub integration", "AI review", "Team dashboard"],
  "tech_stack": ["Python", "FastAPI", "React"]
}
```

---

## 📊 Итоговая зрелость системы

| Фаза | Компонент | Готовность | Записей в DB |
|------|-----------|------------|--------------|
| 1 | Stabilized Execution Engine | 85% | 4+ executions |
| 2 | Experience Layer | 40% | 4 experiences |
| 3 | Reflection Layer | 0% | 0 |
| 4 | Skill Evolution | 0% | 0 |
| 5 | Skill Generation | 0% | 0 |
| 6 | Goal Intelligence | 0% | 0 |
| 7 | Startup Factory | 0% | 0 |

---

## 🚀 Следующие шаги (приоритет)

### P0 — Критично ✅ ВЫПОЛНЕНО

1. ✅ **Починить skill_id tracking** — теперь пишется корректно
2. ✅ **Записывать experience после каждого execution** — теперь работает
3. ✅ **ExecutionPolicy выделен** — готов к использованию

### P1 — Важно

4. **Retry strategy** — при failure пробовать следующий skill
5. **Skill ranking** — добавить success rate и latency в scoring
6. **Learning policy** — активировать LearningExecutionPolicy

### P2 — Развитие

7. Pattern extraction
8. Reflection agent
9. Skill evolution

---

## ⚠️ Важное предупреждение

**80% AI-агентных систем умирают на фазе 1–2.**

Причина: Нет experience layer.

**Правильный порядок:**
1. Стабилизировать execution (Фаза 1)
2. Добавить memory (Фаза 2)
3. Добавить reflection (Фаза 3)
4. Только потом — evolution и generation

---

*Document version: 2.0*
*Updated: 2026-03-05*
*Status: Actual state verified via database queries*
