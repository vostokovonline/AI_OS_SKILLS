# Phase 2A — Skills: Что Реально Работает

## Правда о Скиллах в Phase 2A

---

## Phase 1 (10%) — Что Реально Участвует

| Скилл | Роль в V3 | Проверяет |
|-------|-----------|-----------|
| **echo** | Smoke/sanity check | Базовая работоспособность |
| **write_file** | Artifact + commit boundary | Транзакционная модель |
| **ask_user / ask_user_simple** | Интерактивные цели | User interaction flow |
| **web_research** | External call + latency | Внешние вызовы |
| **ai_research** | LLM нагрузка | Интеграция с LLM |
| **Retry / Arbitration** | Logging + fallback | Обработка ошибок |
| **Legacy Integrator** | V3 vs Legacy comparison | Delta метрики |

**Это достаточно для проверки:**

- ✅ Транзакционная модель (UOW)
- ✅ Skill → Artifact → Verification flow
- ✅ Latency и retry логика
- ✅ Delta V3 vs Legacy
- ✅ Safe rollback

---

## Phase 1 — Что НЕ Включено

| Компонент | Почему | Когда |
|-----------|--------|-------|
| Skill Auto-Loader | Не нужен для 10% | Phase 2 (30%) |
| Dynamic MCP Discovery | Статических скиллов хватает | Phase 2+ |
| Third-party plugins | Риск неизвестен | После стабилизации |
| Experimental routing | Преждевременно | Phase 2+ |

**Правило:** Phase 1 = проверка ядра, не расширения.

---

## Phase 2 (30%) — Что Добавляется

| Компонент | Статус | Зачем |
|-----------|--------|-------|
| **Skill Auto-Loader** | 🟡 Ready to enable | Динамическая подгрузка |
| **Experiment Controller** | 🟡 Ready to enable | Traffic routing control |
| **Skill-level KPIs** | 🟡 Ready to enable | Success per skill |
| **Latency per skill** | 🟡 Ready to enable | Per-skill метрики |

**Это начинает тест архитектуры:**

- MCP подключение без downtime
- Динамическое обнаружение скиллов
- Scalability проверка

---

## Phase 3-4 (50-100%)

- Все скиллы активны
- MCP контролируется через Experiment Controller
- Auto-rollback готов

---

## ⚠️ Главный Вопрос: Safe Auto-Skill Generation?

**Может ли система сама писать новые skills и подключать MCP безопасно?**

### Текущий Ответ: НЕТ (пока)

**Почему:**

1. **Skill Auto-Loader** требует plugin permissions
2. **Dynamic discovery** не протестирован под нагрузкой
3. **Security boundary** не определён для внешних скиллов
4. **Rollback path** для динамических скиллов не верифицирован

### Что Нужно для Да

| Требование | Статус | Notes |
|------------|--------|-------|
| Skill sandboxing | ❌ None | Изоляция не реализована |
| Version control для скиллов | ❌ None | Нет истории версий |
| A/B testing framework | 🟡 Partial | Experiment Controller pending |
| Safety interlock | ❌ None | Нет kill switch per skill |
| Audit logging | 🟢 Ready | Через Arbitration Trace |

### Ближайшее: Phase 2 (30%)

После стабилизации 30% можно тестировать:

1. Skill Auto-Loader в staging
2. Один кастомный скилл в ограниченном режиме
3. A/B test: static vs auto-loaded

### Вывод

**Для 10% — текущих скиллов достаточно.**

**Для динамической генерации — нужна отдельная архитектурная работа после Phase 2 стабилизации.**

---

## Архитектурные Требования для Safe MCP

### Minimum Viable Safe MCP

```
┌─────────────────────────────────────────────────────────────────┐
│                    SAFE MCP ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [1] Skill Registry ──► Белый список разрешённых скиллов       │
│         │                                                      │
│         ▼                                                      │
│  [2] Sandbox ──► Изоляция выполнения (docker/namespace)        │
│         │                                                      │
│         ▼                                                      │
│  [3] Versioning ──► Git-like история версий скиллов            │
│         │                                                      │
│         ▼                                                      │
│  [4] Safety Interlock ──► Kill switch per skill                │
│         │                                                      │
│         ▼                                                      │
│  [5] Audit ──► Полное логирование через Arbitration Trace      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Что Сейчас Есть

| Компонент | Есть? |
|----------|-------|
| Skill Registry | ✅ Белый список готов |
| Sandbox | ❌ Нужна реализация |
| Versioning | ❌ Нужна реализация |
| Safety Interlock | ❌ Нужна реализация |
| Audit | ✅ Arbitration Trace готов |

---

## Резюме: Что Проверяет Phase 1

| # | Проверка | Status |
|---|----------|--------|
| 1 | V3 корректно выбирает скилл | ✅ |
| 2 | V3 не ломает UOW | ✅ |
| 3 | V3 не создаёт stale locks | ✅ |
| 4 | V3 не ухудшает success rate | ✅ |
| 5 | V3 можно безопасно откатить | ✅ |

**Если все 5 зелёные → скиллы можно масштабировать.**

**Если нет → расширять MCP бессмысленно.**

---

##结论

**До запуска ничего по скиллам делать не нужно.**

Они:
- ✅ Зарегистрированы
- ✅ Работают через registry
- ✅ Возвращают SkillResult
- ✅ Поддерживают async
- ✅ Совместимы с V3

**Этого достаточно для 10%.**

---

*Updated: 2026-03-04*
*Status: Ready for Phase 1 (10%)*
