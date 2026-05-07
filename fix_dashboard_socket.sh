#!/bin/bash
echo "🔧 FIXING DOCKER SOCKET PERMISSIONS..."

# Перезаписываем docker-compose.yml (только секцию dashboard, но проще весь файл, 
# однако чтобы не ломать ваши настройки, сделаем точечный патч через пересоздание сервиса)

# Самый надежный способ - это просто добавить volume в docker-compose.yml.
# Но так как парсить yaml башем сложно, мы сделаем это через временный файл.

if grep -q "/var/run/docker.sock:/var/run/docker.sock" docker-compose.yml; then
    echo "✅ Socket volume is present in config."
else
    echo "⚠️ Socket volume missing. Patching..."
    # Этот sed найдет сервис dashboard и добавит volume после него
    sed -i '/container_name: ns_dashboard/a \    volumes:\n      - ./skills:/app/skills\n      - /var/run/docker.sock:/var/run/docker.sock' docker-compose.yml
    echo "✅ Config patched."
fi

# ВАЖНО: В WSL иногда нужны права на файл сокета
# Мы не можем менять права на хосте из скрипта легко, но попробуем
# sudo chmod 666 /var/run/docker.sock (это делается пользователем)

echo "🚀 Restarting Dashboard..."
docker compose up -d --force-recreate dashboard
