#!/bin/bash
##############################################################################
# LiteLLM Deployment Script with Fallback Chain Testing
# Развертывание конфигурации LiteLLM и проверка fallback chain
##############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

ROOT="/home/onor/ai_os_final"
CONFIG_SOURCE="${ROOT}/litellm_config.yaml"
CONFIG_TARGET="${ROOT}/infra/litellm_config.yaml"

# =============================================================================
# 1. Проверка что контейнеры запущены
# =============================================================================

log_info "Проверка статуса контейнеров..."

if ! docker ps | grep -q "ns_litellm"; then
    log_error "Контейнер ns_litellm НЕ запущен"
    echo "Запустите контейнеры: docker compose up -d litellm"
    exit 1
fi

log_success "ns_litellm запущен"

# =============================================================================
# 2. Резервное копирование текущей конфигурации
# =============================================================================

log_info "Резервное копирование текущей конфигурации..."
if [ -f "$CONFIG_TARGET" ]; then
    BACKUP_NAME="litellm_config.yaml.bak.$(date +%s)"
    cp "$CONFIG_TARGET" "${ROOT}/infra/${BACKUP_NAME}"
    log_success "Резервная копия: ${BACKUP_NAME}"
fi

# =============================================================================
# 3. Копирование новой конфигурации
# =============================================================================

log_info "Копирование конфигурации LiteLLM..."
if [ ! -f "$CONFIG_SOURCE" ]; then
    log_error "Исходный файл конфигурации не найден: $CONFIG_SOURCE"
    exit 1
fi

cp "$CONFIG_SOURCE" "$CONFIG_TARGET"
log_success "Конфигурация скопирована"

# =============================================================================
# 4. Перезапуск LiteLLM контейнера
# =============================================================================

log_info "Перезапуск LiteLLM контейнера..."
docker restart ns_litellm
sleep 3

# Проверка что контейнер запустился
if docker ps | grep -q "ns_litellm"; then
    log_success "LiteLLM перезапущен"
else
    log_error "LiteLLM не запустился"
    docker logs ns_litellm --tail 20
    exit 1
fi

# =============================================================================
# 5. Проверка здоровья LiteLLM
# =============================================================================

log_info "Проверка здоровья LiteLLM..."
sleep 2

HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:4000/health 2>/dev/null || echo "000")

if [ "$HEALTH_STATUS" = "200" ]; then
    log_success "LiteLLM здоров (HTTP $HEALTH_STATUS)"
else
    log_warning "LiteLLM вернул HTTP $HEALTH_STATUS"
    docker logs ns_litellm --tail 10
fi

# =============================================================================
# 6. Получение списка моделей
# =============================================================================

log_info "Получение списка моделей..."
MODELS=$(curl -s -H "Authorization: Bearer sk-1234" http://localhost:4000/v1/model/list 2>/dev/null | python3 -c "import sys,json; data=json.load(sys.stdin); print('\n'.join([m.get('id','') for m in data.get('data',[])]))" 2>/dev/null || echo "Ошибка получения списка")

echo -e "${YELLOW}Доступные модели:${NC}"
echo "$MODELS"

# =============================================================================
# 7. Тестирование fallback chain
# =============================================================================

log_info "Тестирование fallback chain..."

# Тест 1: Проверка primary модели (local-coder)
log_info "Тест 1: local-coder (primary)..."
RESPONSE1=$(curl -s -X POST http://localhost:4000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer sk-1234" \
    -d '{
        "model": "local-coder",
        "messages": [{"role": "user", "content": "Say ONLY: ok"}],
        "max_tokens": 10
    }' 2>/dev/null)

if echo "$RESPONSE1" | grep -q "ok"; then
    log_success "✓ local-coder работает"
else
    log_warning "✗ local-coder: $(echo "$RESPONSE1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error',{}).get('message','unknown'))" 2>/dev/null || echo 'no response')"
fi

# Тест 2: Проверка deepseek-reasoner
log_info "Тест 2: deepseek-reasoner (fallback)..."
RESPONSE2=$(curl -s -X POST http://localhost:4000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer sk-1234" \
    -d '{
        "model": "deepseek-reasoner",
        "messages": [{"role": "user", "content": "Say ONLY: ok"}],
        "max_tokens": 10
    }' 2>/dev/null)

if echo "$RESPONSE2" | grep -q "ok"; then
    log_success "✓ deepseek-reasoner работает"
else
    log_warning "✗ deepseek-reasoner: $(echo "$RESPONSE2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error',{}).get('message','unknown'))" 2>/dev/null || echo 'no response')"
fi

# Тест 3: Проверка fallback chain через glm-fallback
log_info "Тест 3: glm-fallback (final fallback)..."
RESPONSE3=$(curl -s -X POST http://localhost:4000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer sk-1234" \
    -d '{
        "model": "glm-fallback",
        "messages": [{"role": "user", "content": "Say ONLY: ok"}],
        "max_tokens": 10
    }' 2>/dev/null)

if echo "$RESPONSE3" | grep -q "ok"; then
    log_success "✓ glm-fallback работает"
else
    log_warning "✗ glm-fallback: $(echo "$RESPONSE3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error',{}).get('message','unknown'))" 2>/dev/null || echo 'no response')"
fi

# =============================================================================
# Итоги
# =============================================================================

echo ""
log_success "=============================================="
log_success "Развертывание LiteLLM завершено!"
log_success "=============================================="
echo ""
echo "URL: http://localhost:4000"
echo "Master Key: sk-1234"
echo ""
echo "Fallback chain:"
echo "  local-coder → deepseek-reasoner → glm-fallback"
echo ""
