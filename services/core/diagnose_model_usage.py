#!/usr/bin/env python3
"""
Diagnostics for model_usage table before aggregation.
Run inside ns_core container.
"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text, select, func
from database import AsyncSessionLocal
from models import ModelUsage
from logging_config import get_logger

logger = get_logger(__name__)


async def diagnose_model_usage():
    """Analyze model_usage table state."""
    async with AsyncSessionLocal() as session:
        print("=" * 60)
        print("MODEL_USAGE TABLE DIAGNOSTICS")
        print("=" * 60)

        # 1. Table size and row count
        print("\n[1] Table Size and Row Count")
        print("-" * 60)

        size_query = text("""
            SELECT
                pg_size_pretty(pg_total_relation_size('model_usage')) as total_size,
                pg_size_pretty(pg_relation_size('model_usage')) as table_size
        """)
        result = await session.execute(size_query)
        row = result.fetchone()
        print(f"Total Size: {row[0]}")
        print(f"Table Size: {row[1]}")
        print(f"Indexes Size: {row[2]}")

        count_query = text("""
            SELECT
                (SELECT COUNT(*) FROM model_usage) as total_rows,
                (SELECT COUNT(*) FROM model_usage WHERE created_at >= NOW() - INTERVAL '24 hours') as rows_24h,
                (SELECT COUNT(*) FROM model_usage WHERE created_at >= NOW() - INTERVAL '1 hour') as rows_1h
        """)
        result = await session.execute(count_query)
        row = result.fetchone()
        print(f"Total Rows: {row[0]:,}")
        print(f"Last 24h: {row[1]:,}")
        print(f"Last 1h: {row[2]:,}")

        # 2. Row distribution by model
        print("\n[2] Row Distribution by Model (All Time)")
        print("-" * 60)

        dist_query = text("""
            SELECT
                model_name,
                COUNT(*) as rows,
                ROUND(COUNT(*)::numeric / (SELECT COUNT(*) FROM model_usage) * 100, 2) as percentage
            FROM model_usage
            GROUP BY model_name
            ORDER BY rows DESC
        """)
        result = await session.execute(dist_query)
        for row in result.fetchall():
            print(f"{row[0]:30s} {row[1]:>10,} rows ({row[2]:>6}%)")

        # 3. Existing indexes
        print("\n[3] Existing Indexes")
        print("-" * 60)

        index_query = text("""
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE tablename = 'model_usage'
            ORDER BY indexname
        """)
        result = await session.execute(index_query)
        for row in result.fetchall():
            print(f"Index: {row[0]}")
            print(f"  {row[1]}")
            print()

        # 4. EXPLAIN ANALYZE for hourly aggregation
        print("\n[4] EXPLAIN ANALYZE - Hourly Aggregation Pattern")
        print("-" * 60)

        explain_query = text("""
            EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
            SELECT
                model_name,
                COUNT(*) as calls,
                AVG(duration_ms) as avg_latency
            FROM model_usage
            WHERE created_at >= NOW() - INTERVAL '1 hour'
            GROUP BY model_name
        """)
        result = await session.execute(explain_query)
        for row in result.fetchall():
            print(row[0])

        # 5. Estimate aggregation load
        print("\n[5] Aggregation Load Estimate")
        print("-" * 60)

        load_query = text("""
            WITH hourly_counts AS (
                SELECT
                    DATE_TRUNC('hour', created_at) as hour,
                    COUNT(*) as rows
                FROM model_usage
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY DATE_TRUNC('hour', created_at)
            )
            SELECT
                hour,
                rows,
                PERCENT_RANK() OVER (ORDER BY rows) as percentile_rank
            FROM hourly_counts
            ORDER BY hour DESC
            LIMIT 24
        """)
        result = await session.execute(load_query)
        print("Last 24 hours by row count:")
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]:>6,} rows (pct: {row[2]:.2f})")


if __name__ == "__main__":
    asyncio.run(diagnose_model_usage())
