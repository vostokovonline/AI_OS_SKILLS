#!/bin/bash
# LLM Worker Startup Script with Auto-Update
# Location: /app/start_worker.sh

set -e

APP_DIR="/app"
LOG_FILE="/var/log/llm-worker.log"
PID_FILE="/var/run/llm-worker.pid"

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
MAX_CONCURRENCY="${MAX_CONCURRENCY:-3}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Main loop
while true; do
    log "========================================="
    log "Starting LLM Worker..."
    log "Redis: $REDIS_HOST:$REDIS_PORT"
    log "Max Concurrency: $MAX_CONCURRENCY"
    
    # Check for code update
    if [ -f "$APP_DIR/.worker_needs_update" ]; then
        NEW_VERSION=$(cat "$APP_DIR/.worker_needs_update")
        log "Update required to version: $NEW_VERSION"
        
        # Check git is available
        if command -v git &> /dev/null; then
            log "Pulling latest code..."
            cd "$APP_DIR"
            if git pull --quiet 2>&1 | tee -a "$LOG_FILE"; then
                log "Code updated successfully"
                rm -f "$APP_DIR/.worker_needs_update"
            else
                log "WARNING: git pull failed, continuing with current code"
            fi
        else
            log "WARNING: git not available, skipping update"
        fi
    fi
    
    # Start worker
    cd "$APP_DIR"
    python3 llm_worker.py \
        --redis-host "$REDIS_HOST" \
        --redis-port "$REDIS_PORT" \
        --max-concurrency "$MAX_CONCURRENCY" \
        --app-dir "$APP_DIR" \
        >> "$LOG_FILE" 2>&1 &
    
    WORKER_PID=$!
    echo $WORKER_PID > "$PID_FILE"
    log "Worker started with PID: $WORKER_PID"
    
    # Wait for worker to exit
    wait $WORKER_PID
    EXIT_CODE=$?
    
    log "Worker exited with code: $EXIT_CODE"
    
    # Check if update was requested
    if [ -f "$APP_DIR/.worker_needs_update" ]; then
        log "Update requested, restarting..."
        rm -f "$APP_DIR/.worker_needs_update"
    elif [ $EXIT_CODE -eq 0 ]; then
        log "Worker exited cleanly, not restarting"
        break
    else
        log "Worker crashed, will restart in 5 seconds..."
        sleep 5
    fi
    
    log "---"
done

log "Worker service stopped"