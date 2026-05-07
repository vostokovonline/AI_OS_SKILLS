"""
System Control API for Distributed Workers

Provides endpoints to:
- Get system version
- Set new version (triggers update)
- Send commands to workers (restart, drain)
- Get worker status
"""
import os
import time
import json
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/llm/system", tags=["llm-system"])

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

SYSTEM_VERSION_KEY = "system:version"
SYSTEM_COMMANDS_KEY = "system:commands"
METRICS_KEY = "llm:worker:metrics"


def get_redis():
    import redis
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)


class SetVersionRequest(BaseModel):
    version: str


class CommandRequest(BaseModel):
    command: str  # restart, drain


@router.get("/version")
async def get_version():
    """Get current system version"""
    try:
        r = get_redis()
        version = r.get(SYSTEM_VERSION_KEY)
        
        # Get worker versions
        worker_versions = r.hgetall(f"{METRICS_KEY}:versions") or {}
        
        workers = []
        for worker_id, data in worker_versions.items():
            try:
                w = json.loads(data)
                workers.append({
                    "worker_id": worker_id,
                    "version": w.get("version"),
                    "hostname": w.get("hostname"),
                    "registered_at": w.get("registered_at")
                })
            except:
                pass
        
        return {
            "system_version": version,
            "workers": workers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/version")
async def set_version(req: SetVersionRequest):
    """Set new system version (triggers update on all workers)"""
    try:
        r = get_redis()
        old_version = r.get(SYSTEM_VERSION_KEY)
        
        r.set(SYSTEM_VERSION_KEY, req.version)
        
        return {
            "status": "updated",
            "old_version": old_version,
            "new_version": req.version
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/command/{worker_id}")
async def send_command(worker_id: str, req: CommandRequest):
    """Send command to specific worker"""
    try:
        r = get_redis()
        
        if req.command not in ["restart", "drain"]:
            raise HTTPException(status_code=400, detail="Invalid command")
        
        r.hset(SYSTEM_COMMANDS_KEY, worker_id, req.command)
        
        return {
            "status": "sent",
            "worker_id": worker_id,
            "command": req.command
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/broadcast")
async def broadcast_command(req: CommandRequest):
    """Send command to all workers"""
    try:
        r = get_redis()
        
        if req.command not in ["restart", "drain"]:
            raise HTTPException(status_code=400, detail="Invalid command")
        
        # Get all workers
        worker_metrics = r.hgetall(METRICS_KEY) or {}
        workers = list(worker_metrics.keys())
        
        for worker_id in workers:
            r.hset(SYSTEM_COMMANDS_KEY, worker_id, req.command)
        
        return {
            "status": "broadcast",
            "command": req.command,
            "workers_count": len(workers)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workers")
async def get_workers():
    """Get all worker status"""
    try:
        r = get_redis()
        
        # Get worker metrics
        worker_metrics = r.hgetall(METRICS_KEY) or {}
        
        workers = []
        for worker_id, metrics_json in worker_metrics.items():
            try:
                m = json.loads(metrics_json)
                workers.append({
                    "worker_id": worker_id,
                    "tasks_completed": m.get("tasks_completed", 0),
                    "errors": m.get("errors", 0),
                    "uptime_seconds": m.get("uptime_seconds", 0),
                    "error_rate": m.get("error_rate", 0),
                    "last_update": m.get("last_update", 0)
                })
            except:
                pass
        
        # Get versions
        versions = r.hgetall(f"{METRICS_KEY}:versions") or {}
        
        for w in workers:
            worker_id = w["worker_id"]
            if worker_id in versions:
                try:
                    v = json.loads(versions[worker_id])
                    w["version"] = v.get("version")
                    w["hostname"] = v.get("hostname")
                except:
                    pass
        
        return {
            "workers": workers,
            "total_workers": len(workers)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class VersionRequest(BaseModel):
    version: str


class VersionResponse(BaseModel):
    current_version: str
    updated: bool


@router.post("/version", response_model=VersionResponse)
async def set_version(req: VersionRequest):
    """Set system version for workers to detect and auto-update"""
    try:
        r = get_redis()
        r.set(SYSTEM_VERSION_KEY, req.version)
        
        return VersionResponse(
            current_version=req.version,
            updated=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version", response_model=VersionResponse)
async def get_version():
    """Get current system version"""
    try:
        r = get_redis()
        version = r.get(SYSTEM_VERSION_KEY) or "1.0.0"
        
        return VersionResponse(
            current_version=version,
            updated=False
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))