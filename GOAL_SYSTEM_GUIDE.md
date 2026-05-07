# AI_OS Goal System - Руководство

## Обзор

Новая Goal System реализует многослойную архитектуру для работы с целями разных типов.

**Слои:**
1. **Goal System** - цели и подцели (goal_decomposer.py)
2. **Task Layer** - превращение atomic goal → задачи
3. **Execution** - выполнение через агентов
4. **Self-Evaluation** - проверка выполнения (goal_evaluator.py)
5. **Next Goal Generator** - генерация следующих целей

## Типология целей

### 1. Achievable Goal (выполнимая)
- Можно достичь
- Есть условие завершения
- Стандартный pipeline: Goal → Subgoals → Atomic → Tasks → Execution → Done

### 2. Continuous Goal (непрерывная)
- Нет финальной точки
- Есть метрика улучшения
- Работает в feedback loop, NEVER done

### 3. Directional Goal (векторная)
- Принципиально невыполнима
- Задает направление мышления
- НЕ декомпозируется, НЕ переходит в Task Layer

### 4. Exploratory Goal (исследовательская)
- Можно "закрыть"
- Результат неизвестен
- Декомпозируется по областям поиска

### 5. Meta Goal (мета-цель)
- Управляет самой системой
- Работает через self-eval и self-modification

## API Эндпоинты

POST /goals/create - Создать цель с авто-классификацией
POST /goals/classify - Классифицировать цель
POST /goals/{goal_id}/decompose - Декомпозировать на подцели
POST /goals/{goal_id}/evaluate - Оценить выполнение
GET /goals/{goal_id}/tree - Получить дерево целей
GET /goals/stats - Статистика по целям

См. полную документацию в коде: goal_decomposer.py, goal_evaluator.py
