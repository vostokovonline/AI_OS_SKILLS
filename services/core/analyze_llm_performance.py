#!/usr/bin/env python3
"""
LLM Performance Analysis Script
=================================

Analyzes LLM usage patterns, costs, and efficiency.
"""

import asyncio
import json
from datetime import datetime, timedelta
from database import AsyncSessionLocal
from models import ModelUsage, Goal
from sqlalchemy import select, func


async def analyze_llm_performance():
    """Comprehensive LLM performance analysis"""

    print("=" * 80)
    print("LLM PERFORMANCE ANALYSIS")
    print("=" * 80)

    async with AsyncSessionLocal() as session:
        # 1. Overall Usage Statistics
        print("\n📊 OVERALL USAGE STATISTICS")
        print("-" * 80)

        result = await session.execute(
            select(
                ModelUsage.model_name,
                func.count(ModelUsage.id).label('count'),
                func.sum(ModelUsage.tokens_used).label('total_tokens'),
                func.sum(ModelUsage.cost_usd).label('total_cost'),
                func.avg(ModelUsage.duration_ms).label('avg_duration'),
                func.avg(ModelUsage.tokens_used).label('avg_tokens')
            )
            .group_by(ModelUsage.model_name)
            .order_by(func.count(ModelUsage.id).desc())
        )

        models = result.all()

        if not models:
            print("⚠️  No LLM usage data found in database")
            return

        total_requests = sum(m.count for m in models)
        total_tokens = sum(m.total_tokens or 0 for m in models)
        total_cost = sum(m.total_cost or 0 for m in models)

        print(f"\nTotal Requests: {total_requests}")
        print(f"Total Tokens: {total_tokens:,}")
        print(f"Total Cost: ${total_cost:.4f}")
        print(f"\nPer-Model Breakdown:")
        print(f"{'Model':<40} {'Requests':>10} {'Tokens':>12} {'Cost':>10} {'Avg Duration':>12} {'Avg Tokens':>12}")
        print("-" * 100)

        for m in models:
            model_short = m.model_name[:40]
            print(f"{model_short:<40} {m.count:>10} {m.total_tokens or 0:>12,} ${m.total_cost or 0:>9.4f} {m.avg_duration or 0:>11.1f}ms {m.avg_tokens or 0:>11.1f}")

        # 2. Success Rate Analysis
        print("\n\n✅ SUCCESS RATE ANALYSIS")
        print("-" * 80)

        result = await session.execute(
            select(
                ModelUsage.model_name,
                ModelUsage.status,
                func.count(ModelUsage.id).label('count')
            )
            .group_by(ModelUsage.model_name, ModelUsage.status)
            .order_by(ModelUsage.model_name, ModelUsage.status)
        )

        status_data = result.all()

        # Organize by model
        model_stats = {}
        for model, status, count in status_data:
            if model not in model_stats:
                model_stats[model] = {}
            model_stats[model][status] = count

        print(f"\n{'Model':<40} {'Success':>10} {'Rate Limited':>12} {'Error':>10} {'Success Rate':>12}")
        print("-" * 90)

        for model, stats in model_stats.items():
            success = stats.get('success', 0)
            rate_limited = stats.get('rate_limited', 0)
            error = stats.get('error', 0)
            total = success + rate_limited + error

            if total > 0:
                success_rate = (success / total) * 100
                model_short = model[:40]
                print(f"{model_short:<40} {success:>10} {rate_limited:>12} {error:>10} {success_rate:>11.1f}%")

        # 3. Performance Metrics
        print("\n\n⚡ PERFORMANCE METRICS")
        print("-" * 80)

        # Token efficiency (tokens per request)
        result = await session.execute(
            select(
                ModelUsage.model_name,
                func.avg(ModelUsage.tokens_used).label('avg_tokens'),
                func.max(ModelUsage.tokens_used).label('max_tokens'),
                func.min(ModelUsage.tokens_used).label('min_tokens')
            )
            .group_by(ModelUsage.model_name)
        )

        token_stats = result.all()

        print(f"\n{'Model':<40} {'Avg Tokens':>12} {'Min Tokens':>12} {'Max Tokens':>12}")
        print("-" * 80)

        for model, avg_t, min_t, max_t in token_stats:
            model_short = model[:40]
            print(f"{model_short:<40} {avg_t or 0:>12.1f} {min_t or 0:>12.1f} {max_t or 0:>12.1f}")

        # 4. Cost Analysis
        print("\n\n💰 COST ANALYSIS")
        print("-" * 80)

        # Calculate cost per 1K tokens
        print(f"\n{'Model':<40} {'Cost/1K Tokens':>15} {'Cost Efficiency':>18}")
        print("-" * 80)

        for model, _, total_tokens, total_cost, _, _ in models:
            if total_tokens and total_cost and total_tokens > 0:
                cost_per_1k = (total_cost / total_tokens) * 1000
                # Lower is better
                model_short = model[:40]
                efficiency = "Excellent" if cost_per_1k < 0.001 else "Good" if cost_per_1k < 0.01 else "Fair"
                print(f"{model_short:<40} ${cost_per_1k:>14.6f} {efficiency:>18}")

        # 5. Latency Analysis
        print("\n\n⏱️  LATENCY ANALYSIS")
        print("-" * 80)

        result = await session.execute(
            select(
                ModelUsage.model_name,
                func.avg(ModelUsage.duration_ms).label('avg_ms'),
                func.min(ModelUsage.duration_ms).label('min_ms'),
                func.max(ModelUsage.duration_ms).label('max_ms'),
                func.count(ModelUsage.id).label('count')
            )
            .group_by(ModelUsage.model_name)
            .having(func.count(ModelUsage.id) > 5)  # Only models with sufficient data
        )

        latency_data = result.all()

        print(f"\n{'Model':<40} {'Avg':>10} {'Min':>10} {'Max':>10} {'Requests':>10} {'Rating':>15}")
        print("-" * 100)

        for model, avg_ms, min_ms, max_ms, count in latency_data:
            model_short = model[:40]
            # Rating based on latency
            if avg_ms < 2000:
                rating = "⚡ Excellent"
            elif avg_ms < 5000:
                rating = "✓ Good"
            elif avg_ms < 10000:
                rating = "~ Fair"
            else:
                rating = "✗ Slow"

            print(f"{model_short:<40} {avg_ms:>9.1f}ms {min_ms:>9.1f}ms {max_ms:>9.1f}ms {count:>10} {rating:>15}")

        # 6. Recommendations
        print("\n\n💡 RECOMMENDATIONS")
        print("-" * 80)

        # Find best overall model
        best_model = None
        best_score = 0

        for model, count, total_tokens, total_cost, avg_duration, _ in models:
            if count < 5:  # Skip if insufficient data
                continue

            # Calculate composite score
            # Lower cost = better
            # Lower latency = better
            # Higher usage = indicates preference

            cost_score = 1.0
            if total_cost and total_tokens:
                cost_per_1k = (total_cost / total_tokens) * 1000
                cost_score = max(0, 1.0 - (cost_per_1k * 100))  # Normalize

            latency_score = max(0, 1.0 - (avg_duration / 10000))  # Normalize to 10s

            usage_score = min(1.0, count / total_requests)  # Usage share

            composite_score = (cost_score * 0.4 + latency_score * 0.4 + usage_score * 0.2)

            if composite_score > best_score:
                best_score = composite_score
                best_model = model

        if best_model:
            print(f"\n✅ Best Overall Model: {best_model}")
            print(f"   Composite Score: {best_score:.3f}")
            print(f"   Recommendation: Use as default for most tasks")

        # Find fastest model
        fastest = min(latency_data, key=lambda x: x[1]) if latency_data else None
        if fastest:
            print(f"\n⚡ Fastest Model: {fastest[0]}")
            print(f"   Average Latency: {fastest[1]:.1f}ms")
            print(f"   Recommendation: Use for real-time interactions")

        # Find most cost-effective
        cost_effective = None
        best_cost_per_1k = float('inf')

        for model, _, total_tokens, total_cost, _, _ in models:
            if total_tokens and total_cost and total_tokens > 0:
                cost_per_1k = (total_cost / total_tokens) * 1000
                if cost_per_1k < best_cost_per_1k:
                    best_cost_per_1k = cost_per_1k
                    cost_effective = model

        if cost_effective:
            print(f"\n💰 Most Cost-Effective: {cost_effective}")
            print(f"   Cost per 1K tokens: ${best_cost_per_1k:.6f}")
            print(f"   Recommendation: Use for batch processing")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(analyze_llm_performance())
