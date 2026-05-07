#!/usr/bin/env python3
"""
LLM Worker Service - Runs on secondary laptops

This worker:
1. Consumes LLM tasks from Redis queue
2. Executes using DirectLLMRouter
3. Returns results to Redis
4. Supports adaptive concurrency per machine power
5. Auto-update mechanism for distributed deployments

Usage:
    python llm_worker.py [--max-concurrency N] [--host HOST]
"""
import os
import sys
import argparse
import asyncio
import signal
import time
import json
import uuid
import subprocess
from datetime import datetime

# Version info - should match git tag
WORKER_VERSION = "1.0.0"
SYSTEM_VERSION_KEY = "system:version"
SYSTEM_COMMANDS_KEY = "system:commands"

sys.path.insert(0, '/app')

from llm.direct_router import DirectLLMRouter
from llm.adaptive_concurrency import AdaptiveConcurrencyController
from logging_config import get_logger

logger = get_logger(__name__)


class LLMWorker:
    """
    Distributed LLM Worker
    
    Consumes tasks from Redis queue:
    - llm:queue (main queue)
    - llm:processing (currently processing, for reliability)
    
    Returns results to:
    - llm:result:{task_id}
    """
    
    QUEUE_IN = "llm:queue"
    QUEUE_PROCESSING = "llm:processing"
    RESULT_PREFIX = "llm:result"
    METRICS_KEY = "llm:worker:metrics"
    TTL_RESULTS = 300  # 5 minutes
    
    def __init__(
        self,
        redis_host: str,
        redis_port: int = 6379,
        max_concurrency: int = 3,
        worker_id: str = None,
        app_dir: str = "/app"
    ):
        import redis
        
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=0,
            decode_responses=True
        )
        
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.max_concurrency = max_concurrency
        self.app_dir = app_dir
        self.router = DirectLLMRouter()
        self.controller = AdaptiveConcurrencyController(
            initial_limit=max_concurrency,
            max_limit=max_concurrency,
            min_limit=1,
        )
        
        self._running = False
        self._should_restart = False
        self._draining = False
        self._tasks = 0
        self._errors = 0
        self._completed_after_drain = 0
        self._start_time = time.time()
        
        # Register version
        self._register_version()
        
        logger.info(
            "llm_worker_init",
            worker_id=self.worker_id,
            redis_host=redis_host,
            max_concurrency=max_concurrency,
            version=WORKER_VERSION
        )
    
    def _register_version(self):
        """Register worker version in Redis"""
        try:
            self.redis.hset(
                f"{self.METRICS_KEY}:versions",
                self.worker_id,
                json.dumps({
                    "version": WORKER_VERSION,
                    "registered_at": time.time(),
                    "hostname": os.getenv("HOSTNAME", "unknown")
                })
            )
        except Exception as e:
            logger.warning("version_register_failed", error=str(e))
    
    def send_heartbeat(self):
        """Send worker heartbeat to Redis"""
        try:
            heartbeat_data = {
                "worker_id": self.worker_id,
                "tasks_completed": self._tasks,
                "errors": self._errors,
                "max_concurrency": self.max_concurrency,
                "status": "running" if self._running else "stopped",
                "uptime_seconds": int(time.time() - self._start_time),
                "last_update": time.time()
            }
            # Write to METRICS_KEY hash for API to read
            key = f"{self.METRICS_KEY}"
            self.redis.hset(key, self.worker_id, json.dumps(heartbeat_data))
            self.redis.expire(key, 60)  # 60s TTL
        except Exception as e:
            logger.warning("heartbeat_failed", error=str(e))
    
    def check_for_updates(self):
        """Check if new version available and trigger update"""
        try:
            # Check system version
            system_version = self.redis.get(SYSTEM_VERSION_KEY)
            
            if system_version and system_version != WORKER_VERSION:
                logger.info(
                    "version_mismatch",
                    current=WORKER_VERSION,
                    required=system_version
                )
                
                # Trigger update via file flag
                update_flag = f"{self.app_dir}/.worker_needs_update"
                with open(update_flag, 'w') as f:
                    f.write(system_version)
                
                logger.info("update_flag_created", version=system_version)
            
            # Check for commands
            command = self.redis.hget(SYSTEM_COMMANDS_KEY, self.worker_id)
            if command:
                if command == "restart":
                    logger.info("restart_command_received")
                    self._should_restart = True
                    self.redis.hdel(SYSTEM_COMMANDS_KEY, self.worker_id)
                elif command == "drain":
                    logger.info("drain_command_received")
                    self._draining = True
                    self.redis.hdel(SYSTEM_COMMANDS_KEY, self.worker_id)
        except Exception as e:
            logger.warning("update_check_failed", error=str(e))
    
    async def process_task(self, task_data: dict) -> dict:
        """Process a single LLM task"""
        task_id = task_data.get("task_id")
        payload = task_data.get("payload", {})
        messages = payload.get("messages", [])
        
        if not messages:
            return {"success": False, "error": "no_messages"}
        
        try:
            result = await self.router.call_with_fallback(messages)
            return result
        except Exception as e:
            logger.error("task_execution_error", task_id=task_id, error=str(e))
            return {"success": False, "error": str(e)}
    
    def brpoplpush(self, timeout: int = 1):
        """Atomic move from queue to processing"""
        try:
            result = self.redis.brpoplpush(
                self.QUEUE_IN,
                self.QUEUE_PROCESSING,
                timeout=timeout
            )
            return result
        except Exception:
            return None
    
    def lrem_processing(self, task_json: str):
        """Remove from processing queue"""
        try:
            self.redis.lrem(self.QUEUE_PROCESSING, 1, task_json)
        except Exception:
            pass
    
    def store_result(self, task_id: str, result: dict):
        """Store result in Redis"""
        try:
            key = f"{self.RESULT_PREFIX}:{task_id}"
            self.redis.setex(key, self.TTL_RESULTS, json.dumps(result))
        except Exception as e:
            logger.error("result_store_error", task_id=task_id, error=str(e))
    
    def get_task(self, task_json: str) -> dict:
        """Parse task JSON"""
        try:
            return json.loads(task_json)
        except:
            return None
    
    async def run_loop(self):
        """Main worker loop"""
        self._running = True
        self._should_restart = False
        self._draining = False
        
        logger.info("worker_loop_started", worker_id=self.worker_id, version=WORKER_VERSION)
        
        loop_counter = 0
        
        while self._running:
            try:
                # Send heartbeat every 5 seconds
                if loop_counter % 5 == 0:
                    self.send_heartbeat()
                
                # Check for updates and commands every 30 seconds
                loop_counter += 1
                if loop_counter % 30 == 0:
                    self.check_for_updates()
                    
                    # Handle update flag
                    update_flag = f"{self.app_dir}/.worker_needs_update"
                    if os.path.exists(update_flag):
                        logger.info("update_detected_flag")
                        self._should_restart = True
                
                # Handle restart command
                if self._should_restart:
                    logger.info("restarting_for_update", version=WORKER_VERSION)
                    break
                
                # Handle drain mode
                if self._draining:
                    if self._tasks == self._completed_after_drain:
                        logger.info("drain_complete_stopping")
                        self._running = False
                    await asyncio.sleep(1)
                    continue
                
                # Atomic pop to processing queue
                task_json = self.brpoplpush(timeout=1)
                
                if not task_json:
                    continue
                
                task = self.get_task(task_json)
                if not task:
                    self.lrem_processing(task_json)
                    continue
                
                task_id = task.get("task_id")
                self._tasks += 1
                
                logger.info("task_started", task_id=task_id, worker_id=self.worker_id)
                
                # Process task
                result = await self.process_task(task)
                
                # Store result
                self.store_result(task_id, result)
                
                # Remove from processing (ACK)
                self.lrem_processing(task_json)
                
                # Update metrics
                self._update_metrics()
                
                success = result.get("success", False)
                logger.info(
                    "task_completed",
                    task_id=task_id,
                    worker_id=self.worker_id,
                    success=success
                )
                
            except Exception as e:
                self._errors += 1
                logger.error("worker_loop_error", error=str(e), worker_id=self.worker_id)
                await asyncio.sleep(0.5)
    
    def _update_metrics(self):
        """Update worker metrics in Redis"""
        try:
            uptime = time.time() - self._start_time
            metrics = {
                "worker_id": self.worker_id,
                "tasks_completed": self._tasks,
                "errors": self._errors,
                "uptime_seconds": uptime,
                "error_rate": self._errors / max(self._tasks, 1),
                "last_update": time.time()
            }
            self.redis.hset(self.METRICS_KEY, self.worker_id, json.dumps(metrics))
            self.redis.expire(self.METRICS_KEY, 3600)  # 1 hour
        except Exception:
            pass
    
    def stop(self):
        """Stop worker gracefully"""
        self._running = False
        logger.info("worker_stopped", worker_id=self.worker_id, tasks=self._tasks)
    
    def get_stats(self) -> dict:
        """Get worker statistics"""
        return {
            "worker_id": self.worker_id,
            "tasks_completed": self._tasks,
            "errors": self._errors,
            "uptime_seconds": time.time() - self._start_time,
            "error_rate": self._errors / max(self._tasks, 1)
        }


async def main():
    parser = argparse.ArgumentParser(description="LLM Worker Service")
    parser.add_argument("--redis-host", default=os.getenv("REDIS_HOST", "localhost"))
    parser.add_argument("--redis-port", type=int, default=int(os.getenv("REDIS_PORT", "6379")))
    parser.add_argument("--max-concurrency", type=int, default=int(os.getenv("MAX_CONCURRENCY", "3")))
    parser.add_argument("--worker-id", default=os.getenv("WORKER_ID", None))
    args = parser.parse_args()
    
    worker = LLMWorker(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        max_concurrency=args.max_concurrency,
        worker_id=args.worker_id
    )
    
    # Handle signals for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("shutdown_signal_received")
        worker.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("worker_starting", args=args.__dict__)
    
    try:
        await worker.run_loop()
    except KeyboardInterrupt:
        logger.info("worker_interrupted")
    finally:
        stats = worker.get_stats()
        logger.info("worker_final_stats", **stats)


if __name__ == "__main__":
    asyncio.run(main())