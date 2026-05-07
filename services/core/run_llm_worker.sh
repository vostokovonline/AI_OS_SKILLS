#!/bin/bash
# LLM Worker Startup Script
# Usage: ./run_llm_worker.sh [--max-concurrency N] [--redis-host HOST]

set -e

WORKER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/llm-worker.log"
PID_FILE="/var/run/llm-worker.pid"

MAX_CONCURRENCY=${MAX_CONCURRENCY:-3}
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

while [[ $# -gt 0 ]]; do
    case $1 in
        --max-concurrency)
            MAX_CONCURRENCY="$2"
            shift 2
            ;;
        --redis-host)
            REDIS_HOST="$2"
            shift 2
            ;;
        --redis-port)
            REDIS_PORT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "Starting LLM Worker..."
echo "  Redis: $REDIS_HOST:$REDIS_PORT"
echo "  Max Concurrency: $MAX_CONCURRENCY"

cd "$WORKER_DIR"

# Check Redis connectivity
python3 -c "
import redis
r = redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT)
r.ping()
print('Redis connection OK')
" || {
    echo "ERROR: Cannot connect to Redis at $REDIS_HOST:$REDIS_PORT"
    exit 1
}

# Start worker
python3 llm_worker.py \
    --redis-host "$REDIS_HOST" \
    --redis-port "$REDIS_PORT" \
    --max-concurrency "$MAX_CONCURRENCY" \
    >> "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "Worker started with PID $(cat $PID_FILE)"