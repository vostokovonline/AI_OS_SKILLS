# Skill Evolution Loop - Architecture

## Concept

**Проблема**: Текущие AI-системы статичны - skills написаны вручную и не эволюционируют.

**Решение**: Skill Evolution Loop - система, которая:
1. Анализирует выполнение goals
2. Выявляет паттерны удачных execution chains
3. Генерирует новые skills через composition
4. Бенчмаркирует кандидатов
5. Замещает слабые навыки сильными

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    AI_OS Core                               │
│  - Goal Execution                                           │
│  - Execution Tracking                                       │
│  - Skill Selection                                          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Skill Evolution Engine                         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Pattern Extraction                                │  │
│  │  - Анализ execution chains                            │  │
│  │  - Выявление повторяющихся паттернов                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  2. Skill Graph Builder                               │  │
│  │  - Nodes: primitive skills                            │  │
│  │  - Edges: composition relationships                   │  │
│  │  - Weights: success metrics                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  3. Composition Engine                                │  │
│  │  - Генерация candidate skills                        │  │
│  │  - Skill chain composition                           │  │
│  │  - Parameter optimization                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  4. Benchmark Engine                                  │  │
│  │  - A/B testing candidates vs current                  │  │
│  │  - Performance metrics collection                    │  │
│  │  - Statistical significance                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  5. Evolution Selector                                │  │
│  │  - Compare candidate vs baseline                      │  │
│  │  - Promote if +20% improvement                        │  │
│  │  - Deprecate weak skills                             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              MCP Skill Fabric                               │
│  - Skill Registry                                           │
│  - Execution Workers                                        │
│  - Version Control                                          │
└─────────────────────────────────────────────────────────────┘
```

## Компоненты

### 1. Pattern Extraction

**Задача**: Найти повторяющиеся паттерны в execution traces.

**Вход**:
```python
execution_trace = {
    "goal_id": "...",
    "skill_chain": ["web_research", "summarize", "write_file"],
    "duration_ms": 5000,
    "success": true,
    "artifacts": [...]
}
```

**Выход**:
```python
pattern = {
    "pattern_id": "research_summarize_write",
    "frequency": 45,  # встречается 45 раз
    "avg_success_rate": 0.91,
    "avg_duration_ms": 4800,
    "skill_sequence": ["web_research", "summarize", "write_file"]
}
```

**Алгоритм**:
1. Сбор execution chains за последние N executions
2. Подсчёт частот последовательностей
3. Фильтрация по success_rate > 0.8
4. Сортировка по frequency × success_rate

### 2. Skill Graph

**Структура**:
```python
class SkillNode:
    id: str  # "web_research"
    type: SkillType  # PRIMITIVE | COMPOSITE
    version: str
    metrics: SkillMetrics

class SkillEdge:
    from_skill: str
    to_skill: str
    weight: float  # вероятность перехода
    success_rate: float  # success rate при переходе
    avg_latency_ms: float

class SkillGraph:
    nodes: Dict[str, SkillNode]
    edges: List[SkillEdge]

    def find_common_patterns(self, min_length: int = 2) -> List[SkillPath]:
        """Найти часто используемые пути в графе"""

    def find_optimal_path(self, from_requirements: dict) -> SkillPath:
        """Найти оптимальный путь для требований goals"""
```

**Пример графа**:
```
[web_research] (0.9)
       │
       │ (weight: 0.7, success: 0.95)
       ▼
  [summarize] (0.85)
       │
       ├─ (0.4) → [write_file] (0.9)
       │
       └─ (0.6) → [format_markdown] (0.88)
                    │
                    └─ (1.0) → [write_file] (0.9)
```

### 3. Composition Engine

**Задача**: Создать новые composite skills на основе паттернов.

**Вход**: Pattern из Pattern Extraction
```python
pattern = {
    "skill_sequence": ["web_research", "summarize", "write_file"],
    "frequency": 45,
    "avg_success_rate": 0.91
}
```

**Выход**: Новый composite skill
```python
composite_skill = {
    "id": "research_summarize_write_v1",
    "type": "composite",
    "component_skills": ["web_research", "summarize", "write_file"],
    "execution_strategy": "sequential",
    "estimated_success_rate": 0.91,
    "estimated_latency_ms": 4800
}
```

**Стратегии композиции**:

1. **Sequential Chain** (простая)
   ```
   web_research → summarize → write_file
   ```

2. **Parallel Fan-out** (для независимых tasks)
   ```
   web_research ─┬→ summarize_en ─┬→ write_file_en
                └→ summarize_ru ─┘
   ```

3. **Conditional Routing** (context-dependent)
   ```
   if task_type == "research":
       web_research → summarize
   else:
       llm_generate
   ```

4. **Loop Optimization** (retry с вариацией)
   ```
   try:
       web_research(query)
   except:
       web_research(query, different_source)
   ```

### 4. Benchmark Engine

**Задача**: Сравнить candidate skill с текущим best-in-class.

**Процесс**:
```python
async def benchmark_candidate(
    candidate_skill: CompositeSkill,
    baseline_skill: Skill,
    test_goals: List[Goal]
) -> BenchmarkResult:
    """
    Запустить A/B тест:
    - 50% test_goals → candidate
    - 50% test_goals → baseline
    - Сравнить metrics
    """

    candidate_metrics = await execute_batch(candidate_skill, test_goals)
    baseline_metrics = await execute_batch(baseline_skill, test_goals)

    return BenchmarkResult(
        candidate_id=candidate_skill.id,
        baseline_id=baseline_skill.id,
        improvement_score=calculate_improvement(candidate_metrics, baseline_metrics),
        statistical_significance=check_significance(candidate_metrics, baseline_metrics),
        recommendation="promote" if improvement_score > 0.2 else "reject"
    )
```

**Метрики для сравнения**:
- Success Rate (вес: 0.5)
- Latency (вес: 0.2)
- Cost (tokens, API calls) (вес: 0.15)
- Artifact Quality (вес: 0.15)

**Statistical Significance**:
- Минимум 50 executions per variant
- T-test для success rate
- 95% confidence interval

### 5. Evolution Selector

**Задача**: Принять решение о замене skill.

**Правила**:
```python
if improvement_score > 0.2 and p_value < 0.05:
    action = "PROMOTE"  # Заменить baseline на candidate
elif improvement_score > 0.1 and p_value < 0.1:
    action = "A/B_CONTINUE"  # Продолжить тестирование
else:
    action = "REJECT"  # Отклонить candidate

# Логирование
log_evolution_decision(
    candidate_id=candidate_skill.id,
    baseline_id=baseline_skill.id,
    improvement_score=improvement_score,
    action=action
)
```

**Version Control**:
```python
skill_versions = {
    "research_summarize_write": {
        "v1": {"status": "deprecated", "reason": "slower than v2"},
        "v2": {"status": "active", "promoted_at": "2026-03-05"},
        "v3_candidate": {"status": "testing", "ab_test_running": True}
    }
}
```

## Полный цикл эволюции

```python
async def evolution_cycle():
    """
    Запускается каждые 24 часа или каждые 100 executions
    """

    # Step 1: Pattern Extraction
    patterns = await extract_patterns_from_executions(
        lookback_executions=100,
        min_frequency=5,
        min_success_rate=0.8
    )

    # Step 2: Build Skill Graph
    graph = await build_skill_graph(patterns)

    # Step 3: Generate Candidates
    candidates = []
    for pattern in patterns:
        candidate = await compose_skill_from_pattern(pattern)
        candidates.append(candidate)

    # Step 4: Benchmark
    benchmark_results = []
    for candidate in candidates:
        baseline = get_baseline_skill_for_capability(candidate.capability)
        result = await benchmark_candidate(candidate, baseline, test_goals)
        benchmark_results.append(result)

    # Step 5: Evolution Selection
    for result in benchmark_results:
        if result.recommendation == "promote":
            await promote_skill(result.candidate_id, deprecate=result.baseline_id)
            log_skill_evolution(
                event="skill_promoted",
                candidate_id=result.candidate_id,
                improvement=result.improvement_score
            )
        elif result.recommendation == "reject":
            await archive_candidate(result.candidate_id)
```

## Интеграция с текущей AI_OS

### Изменения в models.py

```python
class SkillPattern(Base):
    """Обнаруженный паттерн execution chains"""
    __tablename__ = "skill_patterns"

    id = Column(PG_UUID, primary_key=True)
    pattern_id = Column(String(255), unique=True)
    skill_sequence = Column(JSONB)  # ["web_research", "summarize", "write_file"]
    frequency = Column(Integer)
    avg_success_rate = Column(Float)
    avg_duration_ms = Column(Float)
    discovered_at = Column(DateTime)
    last_seen_at = Column(DateTime)

class CompositeSkill(Base):
    """Сгенерированный composite skill"""
    __tablename__ = "composite_skills"

    id = Column(PG_UUID, primary_key=True)
    skill_id = Column(String(255), unique=True)
    version = Column(Integer)
    component_skills = Column(JSONB)  # ["web_research", "summarize", "write_file"]
    execution_strategy = Column(String(50))  # sequential, parallel, conditional
    status = Column(String(50))  # candidate, testing, active, deprecated

    # Metrics from benchmarking
    success_rate = Column(Float)
    avg_latency_ms = Column(Float)
    improvement_over_baseline = Column(Float)

    # Version tracking
    parent_pattern_id = Column(PG_UUID, ForeignKey("skill_patterns.id"))
    created_at = Column(DateTime)
    promoted_at = Column(DateTime, nullable=True)

class SkillEvolutionLog(Base):
    """История evolution решений"""
    __tablename__ = "skill_evolution_log"

    id = Column(PG_UUID, primary_key=True)
    event_type = Column(String(50))  # pattern_discovered, candidate_created, promoted, rejected
    candidate_skill_id = Column(String(255))
    baseline_skill_id = Column(String(255), nullable=True)
    improvement_score = Column(Float, nullable=True)
    reason = Column(Text)
    timestamp = Column(DateTime)
```

### Изменения в goal_executor_v2.py

```python
# В _execute_atomic_goal_with_uow():

# После успешного выполнения:
if result.success:
    # Текущее: запись execution metrics
    await record_execution_metrics(...)

    # НОВОЕ: триггер pattern extraction (асинхронно, non-blocking)
    asyncio.create_task(
        analyze_execution_for_patterns(
            goal_id=goal.id,
            skill_chain=[skill.id],
            execution_trace=trace
        )
    )
```

## Пример работы системы

### Initial State
```
Skills: [web_research, summarize, write_file]
Execution chains: 100
```

### Cycle 1 (Pattern Extraction)
```
Найдены паттерны:
1. web_research → summarize → write_file (45 times, 91% success)
2. web_research → write_file (20 times, 75% success)
3. summarize → write_file (35 times, 88% success)
```

### Cycle 2 (Composition)
```
Созданы candidates:
1. research_summarize_write_v1 (composite)
2. research_write_v1 (composite)
3. summarize_write_v1 (composite)
```

### Cycle 3 (Benchmark)
```
research_summarize_write_v1 vs manual_chain:
- Success: 94% vs 91% (+3%)
- Latency: 4600ms vs 5200ms (-12%)
- Improvement score: +15%
→ Рекомендация: A/B_CONTINUE (нужно больше данных)
```

### Cycle 4 (Promotion)
```
После 200 executions:
research_summarize_write_v2:
- Success: 96% vs 91% (+5%)
- Latency: 4500ms vs 5200ms (-13%)
→ РЕШЕНИЕ: PROMOTE

Результат:
- research_summarize_write_v2 → ACTIVE
- manual chain → DEPRECATED
```

## Преимущества архитектуры

1. **Автоматическая эволюция**: Skills улучшаются без manual intervention
2. **Data-driven**: Решения основаны на metrics, не на мнениях
3. **Постоянное улучшение**: Каждый cycle → лучше система
4. **Версионирование**: Все изменения отслежены, можно откатиться
5. **Statistical rigor**: Бенчмаркинг с significance testing
6. **Composition > Generation**: Композиция существующих skills безопаснее генерации с нуля

## Следующие шаги для реализации

1. **Database schema** (migrations):
   - skill_patterns
   - composite_skills
   - skill_evolution_log

2. **Pattern Extraction Engine**:
   - Анализ execution traces
   - Поиск частых sequences
   - Вычисление metrics

3. **Skill Graph Builder**:
   - Graph representation
   - Path finding algorithms

4. **Composition Engine**:
   - Sequential composition
   - Parallel fan-out
   - Conditional routing

5. **Minimal MCP Skill Fabric** (для изоляции execution)

6. **Benchmark Runner** (A/B testing)

7. **Evolution Scheduler** (запуск cycles)

---

Это архитектура, которая превращает AI_OS из "orchestrator" в "self-improving ecosystem".
