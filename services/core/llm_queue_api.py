"""
LLM Distributed Queue API

Async job system for distributed LLM workers.
Supports submitting tasks and polling for results.

Flow:
    POST /llm/queue → enqueue → Redis → Worker → result → Redis → GET /llm/result/{task_id}
"""
import os
import uuid
import time
import json
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/llm", tags=["llm-queue"])

REDIS_HOST = os.getenv("REDIS_HOST", os.getenv("REDIS_HOST", "redis"))
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

QUEUE_IN = "llm:queue"
RESULT_PREFIX = "llm:result"
METRICS_KEY = "llm:worker:metrics"
TTL_RESULTS = 300


def get_redis():
    """Get Redis connection"""
    import redis
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)


class LLMRequest(BaseModel):
    messages: List[Dict[str, str]]
    max_tokens: Optional[int] = 500
    timeout: Optional[float] = 30.0


class LLMResponse(BaseModel):
    task_id: str
    status: str  # queued, processing, done, not_found


class TaskResult(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict] = None
    error: Optional[str] = None


@router.post("/queue", response_model=LLMResponse)
async def submit_llm_task(request: LLMRequest):
    """
    Submit LLM task to distributed queue.
    
    Returns task_id for polling.
    """
    try:
        r = get_redis()
        
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id,
            "type": "llm_request",
            "payload": {
                "messages": request.messages,
                "max_tokens": request.max_tokens
            },
            "created_at": time.time(),
            "status": "queued"
        }
        
        # Push to queue
        r.lpush(QUEUE_IN, json.dumps(task))
        
        # Log
        from logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("llm_task_queued", task_id=task_id, queue_size=r.llen(QUEUE_IN))
        
        return LLMResponse(
            task_id=task_id,
            status="queued"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/result/{task_id}", response_model=TaskResult)
async def get_llm_result(task_id: str):
    """
    Poll for LLM task result.
    
    Status:
    - queued: waiting in queue
    - processing: being processed by worker
    - done: result ready
    - not_found: task expired or never existed
    """
    try:
        r = get_redis()
        
        # Check result
        result_key = f"{RESULT_PREFIX}:{task_id}"
        result_json = r.get(result_key)
        
        if result_json:
            result = json.loads(result_json)
            return TaskResult(
                task_id=task_id,
                status="done",
                result=result,
                error=result.get("error")
            )
        
        # Check if in processing (optional)
        # processing_key = f"{RESULT_PREFIX}:processing:{task_id}"
        # if r.exists(processing_key):
        #     return TaskResult(task_id=task_id, status="processing")
        
        return TaskResult(
            task_id=task_id,
            status="not_found",
            result=None
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/stats")
async def get_queue_stats():
    """
    Get queue statistics.
    """
    try:
        r = get_redis()
        
        queue_size = r.llen(QUEUE_IN)
        
        # Get worker metrics
        worker_metrics = r.hgetall(METRICS_KEY)
        workers = []
        if worker_metrics:
            for worker_id, metrics_json in worker_metrics.items():
                try:
                    m = json.loads(metrics_json)
                    # Filter stale workers (no update in 60s)
                    if time.time() - m.get("last_update", 0) < 60:
                        workers.append(m)
                except:
                    pass
        
        return {
            "queue_size": queue_size,
            "workers": workers,
            "total_workers": len(workers)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/result/{task_id}")
async def delete_result(task_id: str):
    """Delete result from Redis (cleanup)"""
    try:
        r = get_redis()
        result_key = f"{RESULT_PREFIX}:{task_id}"
        r.delete(result_key)
        return {"status": "deleted", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))