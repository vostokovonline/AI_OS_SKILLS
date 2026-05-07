# MemorySignal v4 - Implementation Complete ✅

## 🎯 Что создано

**MemorySignal v4** - система памяти как давления, а не как знания.

### 3 новых файла:

1. **`memory_signal.py`** - модели данных
   - `MemorySignal` - единичный сигнал памяти
   - `MemoryRegistry` - реестр активных сигналов
   - TTL-based decay

2. **`memory_generator.py`** - генерация сигналов
   - `from_task_retry()` - при ретраях
   - `from_executor_failure()` - при падениях
   - `from_high_cost()` - при перерасходе
   - `from_manual_override()` - при ручном вмешательстве

3. **`decision_field.py`** - поле давления
   - `DecisionField.evaluate()` - вычисляет bias
   - Интегрирует Goal + Memory → Bias
   - Memory НЕ может отменить GoalPressure

4. **`v3_v4_integration.py`** - примеры + тесты
   - Полный рабочий пример
   - Все тесты ✅ passed

---

## 🚀 Как использовать

### Минимальная интеграция (3 шага)

#### Шаг 1: Перед выполнением - вычислить bias

```python
from decision_field import DecisionField, DecisionFieldInput, GoalPressure
from memory_signal import memory_registry

# Собрать входные данные
goal_pressure = GoalPressure(
    goal_id="current",
    title="Explore X",
    priority="high",
    direction=["exploration"],
    magnitude=0.7
)

bias = DecisionField.evaluate(
    DecisionFieldInput(
        goals=[goal_pressure],
        constraints=[],
        memory=memory_registry.get_active(),
        system_state=None
    )
)

# Применить bias к execution context
execution_context = {
    "prefer_skills": bias.prefer_skills,
    "avoid_skills": bias.avoid_skills,
    "depth": bias.depth,
    "speed": bias.speed,
    "llm_profile": bias.llm_profile
}
```

#### Шаг 2: После ошибки - создать сигнал

```python
from memory_generator import memory_generator

# При ошибке
memory_generator.from_executor_failure(
    skill_name="web_research",
    error="timeout after 120s"
)

# При ретраях
memory_generator.from_task_retry(
    task_name="task_x",
    retries=4,
    skill_name="web_research"
)
```

#### Шаг 3: Каждый цикл - decay память

```python
from decision_field import decay_memory_signals

# Вызывается каждый цикл планирования
decay_memory_signals(memory_registry)
```

---

## 📊 Результаты тестов

```
✅ MemorySignal created and added
✅ MemorySignal decay works
✅ MemorySignal expired and removed
✅ DecisionField works
✅ Memory successfully affected bias
```

**Пример влияния памяти:**

```
БЕЗ памяти:
  Prefer: ['web_research', 'analyze']
  Avoid: []
  Risk tolerance: 0.5

ПОСЛЕ ошибки web_research:
  Prefer: ['analyze']  # web_research удален
  Avoid: ['web_research']  # добавлен в avoid
  Risk tolerance: 0.36  # снижен
```

---

## 🎨 Принципы работы

### 1. Memory ≠ Knowledge

- Memory НЕ хранится в БД
- Memory живёт только в runtime (/runtime/memory_signals)
- Memory самоудаляется по TTL

### 2. Goal > Memory всегда

Memory НЕ может отменить GoalPressure.
Memory только ослабляет или смещает bias.

### 3. Автоматическая генерация

MemorySignal создаётся автоматически из:
- ❌ НЕ из LLM рассуждений
- ✅ Из executor failures
- ✅ Из ретраев
- ✅ Из перерасхода ресурсов
- ✅ Из ручных override

---

## 🔧 Типы MemorySignal

| Тип | Когда создается | Влияние |
|-----|----------------|---------|
| `recent_failure` | Ошибка executor | Избегать skill, снизить risk |
| `resource_exhaustion` | Timeout | Снизить depth, ускориться |
| `false_success` | Ручной override | Снизить retry aggressiveness |
| `overfitting` | Повторяющийся успех | Сменить стратегию |
| `high_cost_low_gain` | Перерасход | Ускориться, снизить depth |

---

## 📈 Что это даёт на практике

### Было (v3):
```
Ошибка в skill → повторяется → повторяется → ...
→ Добавляешь if/else в код
→ Логика пухнет
```

### Стало (v3+v4):
```
Ошибка → MemorySignal → bias изменяется → система адаптируется
→ Без изменения кода
→ Самоочищение через TTL
```

---

## 🚦 Следующие шаги

Теперь у тебя есть:

✅ MemorySignal models
✅ MemorySignal generation
✅ DecisionField integration
✅ TTL-based decay
✅ Полные тесты

**Что дальше (выбирай):**

A) Интегрировать в GoalExecutor v2 (реальное использование)
B) Сделать UI-инспектор поля (read-only dashboard)
C) Добавить GoalPressure в БД целей
D) Формализовать Failure Modes

---

## ⚙️ Конфигурация

```python
# .env (уже добавлено)
GROQ_COOLDOWN_HOURS=1  # Cooldown для Groq
LLM_MODEL=cloud-reasoner  # Ollama по умолчанию
```

```yaml
# litellm_config.yaml (уже обновлён)
# Groq с fallback на Ollama
model_list:
  - model_name: groq/llama-3.3-70b-versatile
    fallbacks:
      - local-coder
```

---

## 🎯 Ключевой эффект

Система теперь:

1. **Адаптируется** к ошибкам без изменения кода
2. **Самоочищается** через TTL (не цементирует ошибки)
3. **Не застревает** при конфликте целей
4. **Использует LLM правильно** (реагируют на давление, а не следуют плану)

---

**Без магии. Без философии. Просто работающий код.** ✅
