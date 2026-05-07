#!/bin/bash
set -e

ROOT="/home/onor/ai_os_final"
CORE="$ROOT/services/core"

echo "🛠 Fixing Python package structure for core service..."

cd "$CORE"

# 1. Backup
echo "📦 Creating backup..."
cp -r . ../core_backup_$(date +%Y%m%d_%H%M%S)

# 2. Create core package if not exists
if [ ! -d core ]; then
  echo "📁 Creating core/ package..."
  mkdir core
fi

touch core/__init__.py

# 3. Move modules into core/
for ITEM in llm supervisor.py memory governor utils; do
  if [ -e "$ITEM" ]; then
    echo "➡️  Moving $ITEM -> core/$ITEM"
    mv "$ITEM" core/
  fi
done

# 4. Ensure llm is a package
if [ -d core/llm ]; then
  touch core/llm/__init__.py
fi

# 5. Fix imports inside core
echo "🔧 Fixing internal imports..."
grep -Rl "from services.core" core | xargs -r sed -i 's/from services.core/from core/g'
grep -Rl "import services.core" core | xargs -r sed -i 's/import services.core/import core/g'

# 6. Ensure PYTHONPATH
echo "🔧 Ensuring PYTHONPATH=/app in docker-compose..."
cd "$ROOT"

if ! grep -q "PYTHONPATH: /app" docker-compose.yml; then
  sed -i '/core_worker:/,/environment:/{
    /environment:/a\      PYTHONPATH: /app
  }' docker-compose.yml
fi

# 7. Restart stack
echo "🔄 Restarting containers..."
docker compose down
docker compose up -d --build

echo "✅ Core package structure fixed successfully."
echo "👉 Test with:"
echo "docker exec -i ns_core_worker python - <<'EOF'"
echo "from core.llm.client import call_llm"
echo "print(call_llm([{\"role\":\"user\",\"content\":\"ОК\"}])[\"choices\"][0][\"message\"][\"content\"])"
echo "EOF"
