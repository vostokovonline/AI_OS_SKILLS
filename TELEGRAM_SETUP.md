# Telegram Integration for AI-OS Questions

## Настройка Telegram бота

### 1. Создание бота в Telegram

1. Откройте Telegram и найдите [@BotFather](https://t.me/botfather)
2. Отправьте команду `/newbot`
3. Следуйте инструкциям:
   - Введите имя бота: `AI-OS Questions Bot`
   - Введите username бота: `YourAIOSQuestionsBot` (должен оканчиваться на `bot`)
4. BotFather пришлет токен вида: `8535085195:AAElCTDhbkI7GeJnAyGV2IfTxsZlW03TBQU`
5. Сохраните токен в `.env` файл:
   ```bash
   TELEGRAM_BOT_TOKEN=8535085195:AAElCTDhbkI7GeJnAyGV2IfTxsZlW03TBQU
   ```

### 2. Получение User ID

1. Откройте диалог с вашим ботом в Telegram
2. Отправьте любое сообщение
3. Перейдите по ссылке: `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Найдите `"from":{"id":123456789}` - это ваш User ID
5. Сохраните его в `.env`:
   ```bash
   TELEGRAM_OWNER_ID=123456789
   ```

### 3. Привязка аккаунта

**Вариант A: Через Telegram бота**
```
/start
/link user-12345678
```

**Вариант B: Через API**
```bash
curl -X POST http://localhost:8000/telegram/link \
  -d "user_id=user-123&chat_id=123456789"
```

**Вариант C: Через Dashboard**
1. Откройте Dashboard → Settings
2. Найдите секцию "Telegram Integration"
3. Введите Telegram User ID
4. Нажмите "Link Account"

### 4. Запуск бота

```bash
cd /home/onor/ai_os_final
docker-compose build telegram
docker-compose up -d telegram
```

### 5. Проверка работы

```bash
# Проверить статус бота
curl http://localhost:8004/health

# Проверить привязку
curl http://localhost:8000/telegram/status/user-123

# Отправить тестовый вопрос
curl -X POST http://localhost:8000/telegram/send_question \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "question_data": {
      "question": "Test question from AI-OS",
      "context": "Testing Telegram integration",
      "priority": "normal",
      "artifact_id": "test-uuid-123"
    }
  }'
```

## Как это работает

```
┌─────────────────────────────────────────────────────┐
│ 1. СИСТЕМА ЗАДАЕТ ВОПРОС                          │
│    AskUserSkill.execute()                          │
│    ├─> Сохраняет в Redis                            │
│    └─> Отправляет в Telegram 📱                     │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│ 2. ПОЛЬЗОВАТЕЛЬ ПОЛУЧАЕТ В TELEGRAM               │
│    🔴 Вопрос от AI-OS                               │
│    Вопрос: Какой формат отчета?                   │
│    [✏️ Ответить] [⏭ Использовать дефолт]        │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│ 3. ПОЛЬЗОВАТЕЛЬ ОТВЕЧАЕТ                          │
│    • Текст: "Markdown формат пожалуйста"           │
│    • Или нажимает "Использовать дефолт"           │
└─────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│ 4. БОТ ПЕРЕДАЕТ ОТВЕТ В СИСТЕМУ                  │
│    POST /questions/{id}/answer                     │
│    ├─> Обновляет artifact                           │
│    ├─> Удаляет из pending                          │
│    └─> Цель продолжается                           │
└─────────────────────────────────────────────────────┘
```

## Команды бота

- `/start` - Начало работы и приветствие
- `/link YOUR_USER_ID` - Привязка аккаунта
- `/unlink` - Отвязка аккаунта
- `/status` - Статус системы (количество вопросов)
- `/questions` - Список ваших вопросов

## API Endpoints

### Проверка привязки
```bash
GET /telegram/status/{user_id}

# Response:
{
  "status": "ok",
  "user_id": "user-123",
  "telegram_linked": true,
  "chat_id": "123456789"
}
```

### Привязка аккаунта
```bash
POST /telegram/link
{
  "user_id": "user-123",
  "chat_id": 123456789
}
```

### Отвязка
```bash
POST /telegram/unlink/{user_id}
```

## Troubleshooting

### Бот не отвечает
1. Проверьте токен в `.env`
2. Проверьте что контейнер запущен: `docker ps | grep telegram`
3. Проверьте логи: `docker logs ns_telegram`

### Не приходят уведомления
1. Проверьте что аккаунт привязан: `GET /telegram/status/{user_id}`
2. Проверьте что Telegram бот запущен
3. Проверьте логи бота

### Ошибка "User not linked"
1. Используйте `/link YOUR_USER_ID` в боте
2. Или привяжите через API/Dashboard
3. Проверьте правильность user_id

## Пример использования

```python
from canonical_skills.ask_user import AskUserSkill, QuestionRequest

skill = AskUserSkill()

request = QuestionRequest(
    question="Какой формат отчета preferred?",
    context="Создаю отчет по анализу кода",
    goal_id="user-123",  # Будет использован для поиска Telegram chat_id
    priority="normal",
    timeout_action="continue_with_default",
    default_answer="markdown"
)

result = await skill.execute(request, llm_call=your_llm_function)

# Если пользователь привязал Telegram, он получит уведомление
# и сможет ответить прямо в Telegram!
```

## Демонстрация

```
📱 Telegram:

🔴 Вопрос от AI-OS

Вопрос: Какой формат отчета preferred?

Контекст: Создаю отчет по анализу кода...

Приоритет: NORMAL
Истекает: 2026-01-18T21:00:00

Варианты ответа:

[✏️ Ответить] [⏭ Использовать дефолт] [🗑 Отклонить]
```

При нажатии "✏️ Ответить":
```
✏️ Введите ваш ответ на вопрос:

Отправьте текстовое сообщение с вашим ответом.
```

Пользователь отправляет: "Markdown формат пожалуйста"

```
✅ Ответ отправлен!

Ваш ответ: Markdown формат пожалуйста...
```
