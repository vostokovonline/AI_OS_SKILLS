#!/bin/bash

# Настройки
PROJECT_DIR="$HOME/ai_os_final"
MEMORY_SERVICE_DIR="$PROJECT_DIR/services/memory"
CONTAINER_NAME="ns_memory"

echo "🧠 LEATHERMAN FIX: Marshmallow Attribute Error"
echo "============================================="

# 1. Исправление исходного кода (для будущих билдов)
if [ -d "$MEMORY_SERVICE_DIR" ]; then
    REQ_FILE="$MEMORY_SERVICE_DIR/requirements.txt"
    if [ -f "$REQ_FILE" ]; then
        echo "📝 Обновляем $REQ_FILE..."
        # Удаляем любые упоминания marshmallow, чтобы не было дублей
        sed -i '/marshmallow/d' "$REQ_FILE"
        # Добавляем рабочую версию
        echo "marshmallow<3.22.0" >> "$REQ_FILE"
        echo "✅ requirements.txt обновлен."
    else
        echo "⚠️ Файл requirements.txt не найден в папке memory. Создаю новый."
        echo "marshmallow<3.22.0" > "$REQ_FILE"
    fi
else
    echo "❌ Папка сервиса Memory не найдена ($MEMORY_SERVICE_DIR)."
    exit 1
fi

# 2. Исправление "на горячую" (Hot Patch)
echo "📦 Патчим работающий контейнер $CONTAINER_NAME..."

# Проверяем, запущен ли контейнер, если нет - пытаемся запустить
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "⚠️ Контейнер остановлен. Запускаем..."
    docker start "$CONTAINER_NAME"
    sleep 3
fi

# Устанавливаем правильную версию прямо внутри контейнера
docker exec -u 0 -it "$CONTAINER_NAME" pip install "marshmallow<3.22.0"

if [ $? -eq 0 ]; then
    echo "✅ Библиотека внутри контейнера исправлена."
else
    echo "❌ Ошибка при установке pip пакета внутри контейнера."
    exit 1
fi

# 3. Перезапуск сервиса
echo "🔄 Перезапускаем сервис..."
docker restart "$CONTAINER_NAME"

echo "============================================="
echo "🚀 Готово! Проверяем логи:"
echo "Нажмите Ctrl+C чтобы выйти из логов."
echo "============================================="
sleep 2
docker logs -f "$CONTAINER_NAME"
