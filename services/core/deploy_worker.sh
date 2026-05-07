#!/bin/bash
# Remote LLM Worker Deployment Script
# Usage: ./deploy_worker.sh [worker-host] [--max-concurrency N]

set -e

WORKER_HOST="${1:-}"
MAX_CONCURRENCY="${MAX_CONCURRENCY:-3}"

if [ -z "$WORKER_HOST" ]; then
    echo "Usage: $0 <worker-host> [--max-concurrency N]"
    echo "Example: $0 192.168.1.102 --max-concurrency 2"
    exit 1
fi

WORKER_USER="${WORKER_USER:-root}"
WORKER_DIR="/app"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"

echo "=============================================="
echo "LLM Worker Remote Deployment"
echo "=============================================="
echo "Worker Host: $WORKER_HOST"
echo "Max Concurrency: $MAX_CONCURRENCY"
echo "=============================================="

# Step 1: Copy files
echo "[1/4] Copying files to $WORKER_HOST..."
rsync -avz --exclude '__pycache__' --exclude '*.pyc' \
    -e "ssh $SSH_OPTS" \
    ./services/core/llm_worker.py \
    ./services/core/llm/ \
    "$WORKER_USER@$WORKER_HOST:$WORKER_DIR/" || {
    echo "ERROR: Failed to copy files"
    exit 1
}

# Step 2: Install dependencies
echo "[2/4] Installing dependencies..."
ssh $SSH_OPTS "$WORKER_USER@$WORKER_HOST" << 'EOF'
    cd /app
    pip install redis httpx pydantic --quiet
EOF

# Step 3: Stop existing worker
echo "[3/4] Stopping existing worker..."
ssh $SSH_OPTS "$WORKER_USER@$WORKER_HOST" "pkill -f llm_worker.py || true"

# Step 4: Start new worker
echo "[4/4] Starting worker..."
ssh $SSH_OPTS "$WORKER_USER@$WORKER_HOST" << EOF
    cd /app
    MAX_CONCURRENCY=$MAX_CONCURRENCY nohup python3 llm_worker.py \
        --redis-host $(hostname -I | awk '{print $1}') \
        --redis-port 6379 \
        --max-concurrency $MAX_CONCURRENCY \
        >> /var/log/llm-worker.log 2>&1 &
    
    sleep 2
    if pgrep -f llm_worker.py > /dev/null; then
        echo "Worker started successfully"
    else
        echo "ERROR: Worker failed to start"
        exit 1
    fi
EOF

echo "=============================================="
echo "Deployment complete!"
echo "=============================================="

# Verify
echo ""
echo "Verifying worker..."
WORKER_ID=$(ssh $SSH_OPTS "$WORKER_USER@$WORKER_HOST" "cat /var/run/llm-worker.pid 2>/dev/null || pgrep -f llm_worker.py | head -1")
echo "Worker PID: $WORKER_ID"

# Show logs
echo ""
echo "Last 5 lines of worker log:"
ssh $SSH_OPTS "$WORKER_USER@$WORKER_HOST" "tail -5 /var/log/llm-worker.log 2>/dev/null || echo 'No log file'"