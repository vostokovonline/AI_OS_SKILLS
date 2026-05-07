# Dashboard Access Guide - AI-OS

## ✅ ОБА DASHBOARD'А РАБОТАЮТ!

---

## 🚀 Dashboard v1 (Streamlit)

**URL:** http://localhost:8501

**Статус:** ✅ РАБОТАЕТ

**Что внутри:**
- Список всех goals
- Статистика выполнения
- Artifact viewer
- Графики и метрики

**Доступ:** Откройте в браузере http://localhost:8501

---

## 🎨 Dashboard v2 (React v2 - NEW!)

**URL:** http://localhost:3000

**Статус:** ✅ РАБОТАЕТ (уже запущен с Jan 28)

**Что внутри (НОВОЕ!):**
- ✅ Graph Canvas - визуализация goal decomposition
- ✅ Inspector Panel - детальная информация о goals
- ✅ Conflicts Section - проверка конфликтов (НОВОЕ!)
- ✅ Personality Context - emotional tone и recent goals (НОВОЕ!)
- ✅ Artifact Viewer - просмотр artifacts
- ✅ Interactive UI - современный React интерфейс

**Доступ:** Откройте в браузере http://localhost:3000

---

## 🔧 Если НЕ открываются:

### Dashboard v1 (8501):
```bash
# Проверить статус
docker ps | grep dashboard

# Перезапустить
docker restart ns_dashboard

# Посмотреть логи
docker logs ns_dashboard --tail 50
```

### Dashboard v2 (3000):
```bash
# Проверить запущен ли процесс
ps aux | grep vite

# Если НЕ запущен - запустить:
cd /home/onor/ai_os_final/services/dashboard_v2
npm run dev

# Если порт занят - убить процесс
lsof -i :3000
kill -9 <PID>
npm run dev
```

---

## 📊 Быстрый доступ:

| Dashboard | URL | Статус | Технология |
|-----------|-----|--------|------------|
| **v1** | http://localhost:8501 | ✅ Работает | Streamlit (Python) |
| **v2** | http://localhost:3000 | ✅ Работает | React + Vite |

---

## 🎯 Что выбрать?

### Используйте Dashboard v1 если:
- Нужно увидеть полный список goals
- Нужны простые графики
- Любите классический интерфейс Streamlit

### Используйте Dashboard v2 если:
- ✅ Хотите видеть goal decomposition graph
- ✅ Нужна проверка conflicts (НОВОЕ!)
- ✅ Хотите видеть personality context (НОВОЕ!)
- ✅ Любите современные React интерфейсы
- ✅ Нужен interactive graph canvas

---

## 🐛 Исправленные проблемы:

### 1. Dashboard v1 - NaN Error ✅
**Было:** `ValueError: cannot convert float NaN to integer`
**Исправлено:** Добавлен `or 0` для обработки NaN значений

### 2. Dashboard v2 - Port 3000 already in use ✅
**Было:** Порт был занят старым процессом
**Исправлено:** Процесс найден (PID 3815), работает корректно

---

## 🚀 Следующие шаги:

1. Откройте http://localhost:3000 (Dashboard v2)
2. Кликните на любой goal чтобы увидеть Inspector Panel
3. Нажми "Check Conflicts" чтобы проверить конфликты
4. Нажми "Personality Context" чтобы увидеть personality данные
5. Исследуй Graph Canvas и artifacts

---

**Оба dashboard'а готовы к использованию!** 🎉
