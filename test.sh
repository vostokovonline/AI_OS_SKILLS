#!/bin/bash
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
echo "🔍 SYSTEM DIAGNOSTIC..."

check() {
    if curl -s -o /dev/null -w "%{http_code}" $2 | grep -q "200\|404"; then
        echo -e "   ✅ $1: ${GREEN}ONLINE${NC}"
    else
        echo -e "   ❌ $1: ${RED}OFFLINE${NC}"
    fi
}

check "Core API" "http://localhost:8000/docs"
check "Dashboard" "http://localhost:8501/_stcore/health"
check "Webhook" "http://localhost:8007/docs"
check "MinIO" "http://localhost:9001"

echo "Containers:"
docker ps --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "🧠 Core Logic Test:"
docker logs --tail 5 ns_core_worker
