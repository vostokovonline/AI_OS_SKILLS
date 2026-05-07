"""
Analytics API Endpoints - Unified analytics for both dashboards.

Provides:
- LLM model usage metrics
- System health status
- Performance metrics
"""
from fastapi import APIRouter
from typing import List, Dict, Any
from datetime import datetime, timedelta
import time
from sqlalchemy import text, select, func
from database import AsyncSessionLocal
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def get_db():
    """Database session dependency."""
    async with AsyncSessionLocal() as session:
        yield session


@router.get("/llm-overview")
async def get_llm_analytics_overview():
    """
    Unified LLM metrics for both dashboards.

    Returns aggregated statistics from model_usage table.
    """
    async with AsyncSessionLocal() as session:
        # Check if model_usage table exists
        check_query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'model_usage'
            )
        """)
        table_exists = (await session.execute(check_query)).scalar()

        if not table_exists:
            return {
                "models": {},
                "usage_24h": {
                    "total_calls": 0,
                    "success_rate": 0.0,
                    "error_count": 0,
                },
                "latency": {
                    "avg_ms": 0.0,
                    "p50_ms": 0.0,
                    "p95_ms": 0.0,
                    "p99_ms": 0.0,
                },
                "tokens": {
                    "total_tokens": 0,
                    "avg_tokens_per_call": 0,
                }
            }

        # Get 24h stats
        since_24h = datetime.utcnow() - timedelta(hours=24)

        # Total calls and success rate
        stats_query = text("""
            SELECT
                COUNT(*) as total_calls,
                COUNT(*) FILTER (WHERE status = 'success') as success_count,
                COUNT(*) FILTER (WHERE status = 'error') as error_count,
                AVG(duration_ms) as avg_duration,
                AVG(tokens_used) as avg_tokens
            FROM model_usage
            WHERE created_at >= :since
        """)
        result = await session.execute(stats_query, {"since": since_24h})
        row = result.fetchone()

        total_calls = row.total_calls if row.total_calls else 0
        success_count = row.success_count if row.success_count else 0
        error_count = row.error_count if row.error_count else 0
        avg_duration = float(row.avg_duration) if row.avg_duration else 0.0
        avg_tokens = float(row.avg_tokens) if row.avg_tokens else 0

        success_rate = (success_count / total_calls * 100) if total_calls > 0 else 0.0

        # Percentiles for latency
        percentiles_query = text("""
            SELECT
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) as p50,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99
            FROM model_usage
            WHERE created_at >= :since AND duration_ms IS NOT NULL
        """)
        pct_result = await session.execute(percentiles_query, {"since": since_24h})
        pct_row = pct_result.fetchone()

        # By-model breakdown
        by_model_query = text("""
            SELECT
                model_name,
                COUNT(*) as calls,
                COUNT(*) FILTER (WHERE status = 'success') as success,
                AVG(duration_ms) as avg_duration,
                SUM(tokens_used) as total_tokens
            FROM model_usage
            WHERE created_at >= :since
            GROUP BY model_name
            ORDER BY calls DESC
        """)
        model_result = await session.execute(by_model_query, {"since": since_24h})
        model_rows = model_result.fetchall()

        models = {}
        for mrow in model_rows:
            models[mrow.model_name] = {
                "calls": mrow.calls,
                "success": mrow.success,
                "error_rate": ((mrow.calls - mrow.success) / mrow.calls * 100) if mrow.calls > 0 else 0,
                "avg_duration_ms": float(mrow.avg_duration) if mrow.avg_duration else 0,
                "total_tokens": mrow.total_tokens if mrow.total_tokens else 0,
            }

        # Token stats
        tokens_query = text("""
            SELECT
                SUM(tokens_used) as total_tokens,
                AVG(tokens_used) as avg_tokens
            FROM model_usage
            WHERE created_at >= :since AND tokens_used IS NOT NULL
        """)
        tokens_result = await session.execute(tokens_query, {"since": since_24h})
        tokens_row = tokens_result.fetchone()

        total_tokens = tokens_row.total_tokens if tokens_row.total_tokens else 0

        return {
            "models": models,
            "usage_24h": {
                "total_calls": total_calls,
                "success_rate": round(success_rate, 2),
                "error_count": error_count,
            },
            "latency": {
                "avg_ms": round(avg_duration, 2),
                "p50_ms": round(float(pct_row.p50), 2) if pct_row.p50 else 0,
                "p95_ms": round(float(pct_row.p95), 2) if pct_row.p95 else 0,
                "p99_ms": round(float(pct_row.p99), 2) if pct_row.p99 else 0,
            },
            "tokens": {
                "total_tokens": total_tokens,
                "avg_tokens_per_call": round(avg_tokens, 2),
            }
        }


@router.get("/llm-history")
async def get_llm_usage_history(hours: int = 24, points: int = 24):
    """
    Time-series data for LLM usage charts.

    Args:
        hours: How many hours back to query
        points: Number of data points (resamples)
    """
    async with AsyncSessionLocal() as session:
        # Check if model_usage table exists
        check_query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'model_usage'
            )
        """)
        table_exists = (await session.execute(check_query)).scalar()

        if not table_exists:
            return {"history": []}

        since = datetime.utcnow() - timedelta(hours=hours)

        # Get time-series data grouped by time bucket
        interval_minutes = max(1, (hours * 60) // points)

        query = text(f"""
            SELECT
                date_trunc('minute', created_at)
                    - INTERVAL '1 second' * (EXTRACT(MINUTE FROM date_trunc('minute', created_at))::int % {interval_minutes})
                    as time_bucket,
                COUNT(*) as calls,
                COUNT(*) FILTER (WHERE status = 'success') as success,
                AVG(duration_ms) as avg_duration,
                SUM(tokens_used) as total_tokens
            FROM model_usage
            WHERE created_at >= :since
            GROUP BY time_bucket
            ORDER BY time_bucket
        """)
        result = await session.execute(query, {"since": since})
        rows = result.fetchall()

        history = []
        for row in rows:
            history.append({
                "timestamp": row.time_bucket.isoformat(),
                "calls": row.calls,
                "success": row.success,
                "errors": row.calls - row.success,
                "avg_duration_ms": float(row.avg_duration) if row.avg_duration else 0,
                "total_tokens": row.total_tokens if row.total_tokens else 0,
            })

        return {"history": history}


@router.get("/system-health")
async def get_system_health():
    """
    Health status of all services.

    Returns: Status of PostgreSQL, Redis, Neo4j, Milvus, LiteLLM
    """
    import redis

    health = {}

    # PostgreSQL
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        health["postgres"] = {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        health["postgres"] = {"status": "unhealthy", "error": str(e)}

    # Redis
    try:
        r = redis.from_url("redis://ns_redis:6379/0")
        start = time.time()
        r.ping()
        latency = (time.time() - start) * 1000
        health["redis"] = {"status": "healthy", "latency_ms": round(latency, 2)}
    except Exception as e:
        health["redis"] = {"status": "unhealthy", "error": str(e)}

    # Neo4j
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            "bolt://ns_neo4j:7687",
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
        )
        start = time.time()
        driver.verify_connectivity()
        latency = (time.time() - start) * 1000
        driver.close()
        health["neo4j"] = {"status": "healthy", "latency_ms": round(latency, 2)}
    except Exception as e:
        health["neo4j"] = {"status": "unhealthy", "error": str(e)}

    # Milvus
    try:
        from pymilvus import connections
        connections.connect("default", host="ns_milvus", port="19530")
        start = time.time()
        from pymilvus import utility
        utility.list_collections()
        latency = (time.time() - start) * 1000
        connections.disconnect("default")
        health["milvus"] = {"status": "healthy", "latency_ms": round(latency, 2)}
    except Exception as e:
        health["milvus"] = {"status": "unhealthy", "error": str(e)}

    # LiteLLM
    try:
        import httpx
        start = time.time()
        async with httpx.AsyncClient() as client:
            # Health check slow - use longer timeout (models startup)
            response = await client.get("http://ns_litellm:4000/health", timeout=30.0)
            latency = (time.time() - start) * 1000
            if response.status_code < 500:
                health["litellm"] = {"status": "healthy", "latency_ms": round(latency, 2)}
            else:
                health["litellm"] = {"status": "degraded", "latency_ms": round(latency, 2)}
    except Exception as e:
        health["litellm"] = {"status": "unhealthy", "error": str(e)}

    # Core API (self-check)
    health["core_api"] = {"status": "healthy", "latency_ms": 0}

    # Overall status
    all_healthy = all(h["status"] == "healthy" for h in health.values())
    health["overall"] = "healthy" if all_healthy else "degraded"

    return health


@router.get("/performance-metrics")
async def get_performance_metrics(hours: int = 1):
    """
    Performance metrics: latency, throughput, queue lengths.

    Args:
        hours: How many hours back to query
    """
    import redis
    import docker

    metrics = {}

    # Redis queue length
    try:
        r = redis.from_url("redis://ns_redis:6379/0")
        queue_length = r.llen("default")
        metrics["queue"] = {
            "length": queue_length,
            "status": "ok" if queue_length < 100 else "backlog"
        }
    except Exception as e:
        metrics["queue"] = {"status": "error", "error": str(e)}

    # Docker container stats
    try:
        client = docker.from_env()
        containers = {c.name: c for c in client.containers.list() if 'ns_' in c.name}

        container_stats = {}
        for name, container in containers.items():
            try:
                stats = container.stats(stream=False)
                cpu_percent = stats["cpu_stats"]["cpu_usage"]["total_usage"] / stats["cpu_stats"]["system_cpu_usage"]["total_usage"] * 100 if stats["cpu_stats"].get("system_cpu_usage") else 0
                memory_mb = stats["memory_stats"].get("usage", 0) / 1024 / 1024

                container_stats[name] = {
                    "status": "running",
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_mb": round(memory_mb, 2),
                }
            except Exception as e:
                container_stats[name] = {"status": "error", "error": str(e)}

        metrics["containers"] = container_stats
    except Exception as e:
        metrics["containers"] = {"status": "error", "error": str(e)}

    # Goal execution metrics from database
    async with AsyncSessionLocal() as session:
        since = datetime.utcnow() - timedelta(hours=hours)

        # Goal completion rate
        goal_stats_query = text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'done') as completed,
                COUNT(*) FILTER (WHERE status = 'active') as active,
                COUNT(*) as total
            FROM goals
            WHERE created_at >= :since
        """)
        goal_result = await session.execute(goal_stats_query, {"since": since})
        goal_row = goal_result.fetchone()

        metrics["goals"] = {
            "completed": goal_row.completed if goal_row.completed else 0,
            "active": goal_row.active if goal_row.active else 0,
            "total": goal_row.total if goal_row.total else 0,
            "completion_rate": (goal_row.completed / goal_row.total * 100) if goal_row.total and goal_row.total > 0 else 0,
        }

    return metrics


@router.get("/model-limits")
async def get_model_limits():
    """Current model limits and usage."""
    async with AsyncSessionLocal() as session:
        # Use llm_model_catalog from v3 telemetry
        check_query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'llm_model_catalog'
            )
        """)
        table_exists = (await session.execute(check_query)).scalar()

        if not table_exists:
            return {"limits": []}

        query = text("""
            SELECT
                model_name,
                provider,
                rpm_limit,
                tpm_limit,
                baseline_p50_latency_ms,
                baseline_success_rate
            FROM llm_model_catalog
            ORDER BY model_name
        """)
        result = await session.execute(query)
        rows = result.fetchall()

        limits = []
        for row in rows:
            # Calculate current RPM from hourly metrics (last hour)
            rpm_query = text("""
                SELECT SUM(total_calls) / 60.0 as rpm
                FROM llm_metrics_hourly
                WHERE
                    model_name = :model_name
                    AND bucket >= date_trunc('hour', NOW() - INTERVAL '1 hour')
            """)
            rpm_result = await session.execute(rpm_query, {"model_name": row.model_name})
            rpm_row = rpm_result.fetchone()
            current_rpm = round(rpm_row.rpm or 0, 2) if rpm_row else 0

            rpm_limit = row.rpm_limit or 0
            usage_pct = (current_rpm / rpm_limit * 100) if rpm_limit > 0 else 0

            limits.append({
                "model_name": row.model_name,
                "provider": row.provider,
                "rpm_limit": rpm_limit,
                "current_rpm": current_rpm,
                "usage_percent": round(usage_pct, 2),
                "status": "ok" if usage_pct < 80 else "warning" if usage_pct < 95 else "critical",
                "baseline_p50_latency_ms": row.baseline_p50_latency_ms,
            })

        return {"limits": limits}
