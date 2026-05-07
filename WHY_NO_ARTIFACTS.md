# Почему некоторые goals не имеют artifacts

## 📊 Анализ ситуации:

### ✅ Что работает:
1. **Artifacts создаются** - 117 artifacts в базе данных
2. **API работает** - `/goals/{goalId}/artifacts` возвращает данные
3. **Dashboard v2 загружает** - InspectorPanel.tsx вызывает API
4. **Все artifacts verified** - verification_status='passed'

### ❌ Проблема:

**Не-atomic goals НЕ имеют artifacts** (и это ПРАВИЛЬНО!)

Данные из БД:
```
Статистика:
- 137 total goals
- 88 atomic goals (is_atomic=true)
- 49 non-atomic goals (is_atomic=false)
- 117 artifacts total
- 89 goals with artifacts

Почему:
- Non-atomic goals (Mission/Strategic/Operational) → НЕ производят artifacts
- Только atomic goals (Tactical) → производят artifacts
```

Пример:
```
✅ Atomic goal (is_atomic=true):
   "Обеспечить финансовую поддержку родителям ежемесячными переводами"
   → HAS 1 artifact (FILE: plan_finansovoy_podderzhki.md)

❌ Non-atomic goal (is_atomic=false):
   "Обеспечить финансовую поддержку родителям"
   → HAS 0 artifacts (это parent goal)
```

### 🔍 Dashboard v2 - что происходит:

**InspectorPanel.tsx:**
```typescript
// Line 82-99
useEffect(() => {
  const loadArtifacts = async () => {
    if (!node.id) return;

    setLoadingArtifacts(true);
    const response = await apiClient.fetchGoalArtifacts(node.id);
    if (response.status === 'ok' && response.artifacts) {
      setArtifacts(response.artifacts);
    }
    setLoadingArtifacts(false);
  };

  loadArtifacts();
}, [node.id]);
```

**Проблема:** Если artifacts = [], показывается "No artifacts produced yet"

### 💡 Решения:

**Вариант 1: Показывать sub-goals artifacts**
```
Non-atomic goal → Показывать artifacts от child atomic goals
```

**Вариант 2: Объяснение в UI**
```
Non-atomic goal → "This is a parent goal. Artifacts are produced by sub-goals."
```

**Вариант 3: Агрегация artifacts**
```
Non-atomic goal → Собрать все artifacts от descendant atomic goals
```

## 📋 Ответы на вопросы:

### Q: Почему некоторые goals не имеют artifacts?
**A:** Потому что они non-atomic (parent goals). Только atomic goals производят artifacts по дизайну системы.

### Q: Почему я не могу просмотреть их из dashboard v2?
**A:** Dashboard v2 УЖЕ показывает artifacts (InspectorPanel → ArtifactCard), но только для atomic goals. Для non-atomic goals нужно либо:
1. Показывать sub-goals
2. Агрегировать artifacts от descendants
3. Объяснить что это parent goal

### Q: Как исправить?
**A:** Добавить агрегацию artifacts для non-atomic goals в `get_goal_artifacts()` endpoint.

## 🚀 Рекомендуемое решение:

Добавить в `main.py` функцию агрегации:

```python
async def get_goal_artifacts(goal_id: str, include_descendants: bool = True):
    """Get artifacts for goal, including descendants for non-atomic goals"""
    # Текущая логика для atomic goals
    # + Новая логика для non-atomic goals (агрегация от descendants)
```

Это позволит non-atomic goals показывать artifacts от своих sub-goals.
