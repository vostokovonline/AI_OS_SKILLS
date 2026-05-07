#!/bin/bash
#
# Deploy LLM Control Center - Production-Safe
#
# This script:
# 1. Applies database migration
# 2. Integrates aggregator v3 into scheduler
# 3. Creates telemetry directory structure
# 4. Runs initial backfill (if data exists)
#

set -e

echo "=========================================="
echo "LLM Control Center Deployment"
echo "Production-Safe Version"
echo "=========================================="

# Step 1: Create telemetry directory
echo ""
echo "[1/5] Creating telemetry directory..."
docker exec ns_core mkdir -p /app/telemetry

# Step 2: Copy aggregator
echo "[2/5] Installing aggregator v3..."
docker cp services/core/telemetry/llm_aggregator_v3.py ns_core:/app/telemetry/

# Step 3: Apply database migration
echo "[3/5] Applying database migration..."
# Copy migration file to core container
docker cp services/core/migrations/llm_telemetry_v3.sql ns_core:/app/migrations/
# Run migration via psql from core container
docker exec ns_core python << 'PYTHON'
import subprocess
import os

os.environ['PGPASSWORD'] = 'ns_secure_pass'
result = subprocess.run([
    'psql',
    '-h', 'ns_postgres',
    '-U', 'ns_admin',
    '-d', 'ns_core_db',
    '-f', '/app/migrations/llm_telemetry_v3.sql'
], capture_output=True, text=True)

if result.returncode != 0:
    print(f"Error: {result.stderr}")
    exit(1)

print(result.stdout)
PYTHON

# Step 4: Integrate into scheduler
echo "[4/5] Integrating with scheduler..."
docker exec ns_core python << 'PYTHON'
import asyncio
from scheduler import scheduler
from telemetry.llm_aggregator_v3 import start_llm_telemetry_scheduler_v3

async def integrate():
    await start_llm_telemetry_scheduler_v3(scheduler)
    print("✓ LLM telemetry scheduler integrated")

asyncio.run(integrate())
PYTHON

# Step 5: Deploy
echo "[5/5] Deploying to containers..."
./deploy.sh fast

echo ""
echo "=========================================="
echo "✓ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Wait 5 minutes for first aggregation"
echo "2. Check logs: docker logs ns_core -f | grep llm"
echo "3. Verify data: docker exec ns_core python -c 'from telemetry.llm_aggregator_v3 import LLMMetricsAggregatorV3; ...'"
echo "=========================================="
