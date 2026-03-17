"""
Intelligent Model Rotator - Load Balancing for LLMs
======================================================

Problem: First 2-4 requests to same LLM are fast, then latency grows
Solution: Rotate through all available models to distribute load

Features:
- Round-robin rotation through 7 models
- Cloud models preferred (no local PC load)
- Local model used sparingly (only when needed)
- Cold start avoidance
- Health-aware selection

Author: AI-OS Load Balancing
Date: 2026-03-10
"""

import time
import random
from collections import deque, defaultdict
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ModelStats:
    """Performance statistics for a model"""
    name: str
    is_local: bool = False

    # Usage tracking
    total_requests: int = 0
    requests_last_minute: int = 0
    last_used: Optional[datetime] = None

    # Performance tracking
    avg_latency_ms: float = 0.0
    last_latency_ms: float = 0.0
    success_count: int = 0
    error_count: int = 0

    # Cold start tracking
    is_cold: bool = True  # First few requests are faster (cold start)
    cold_request_count: int = 0
    cold_threshold: int = 4  # After 4 requests, model warms up

    # Rate limiting
    current_rpm: int = 0
    max_rpm: int = 60

    def can_use(self, allow_local: bool = False) -> bool:
        """
        Check if model can be used.

        Args:
            allow_local: If True, local models are allowed (fallback mode)
        """
        # Don't exceed RPM
        if self.current_rpm >= self.max_rpm:
            return False

        # Prefer cloud models
        if self.is_local and not allow_local:
            # Only use local if explicitly allowed (fallback mode)
            return False

        return True

    def record_request(self, latency_ms: float, success: bool):
        """Record a request"""
        self.total_requests += 1
        self.last_used = datetime.now()
        self.last_latency_ms = latency_ms

        # Update moving average
        if self.avg_latency_ms == 0:
            self.avg_latency_ms = latency_ms
        else:
            # Exponential moving average
            alpha = 0.3
            self.avg_latency_ms = alpha * latency_ms + (1 - alpha) * self.avg_latency_ms

        if success:
            self.success_count += 1
        else:
            self.error_count += 1

        # Track cold start
        self.cold_request_count += 1
        if self.cold_request_count >= self.cold_threshold:
            self.is_cold = False

    def get_score(self) -> float:
        """
        Calculate model score for selection.
        Lower score = better (for min-heap selection)
        """
        score = 0.0

        # Prefer cold models (faster)
        if self.is_cold:
            score -= 10.0

        # Prefer less recently used
        if self.last_used:
            seconds_since_use = (datetime.now() - self.last_used).total_seconds()
            score -= (seconds_since_use / 60.0)  # -1 point per minute

        # Prefer lower latency
        score += (self.avg_latency_ms / 1000.0)  # +1 point per second

        # Prefer higher success rate
        if self.total_requests > 0:
            success_rate = self.success_count / self.total_requests
            score -= (success_rate * 5.0)  # -5 points for 100% success

        # Penalize errors
        if self.total_requests > 0:
            error_rate = self.error_count / self.total_requests
            score += (error_rate * 10.0)  # +10 points for 100% errors

        return score


class ModelRotator:
    """
    Intelligent model rotation system.

    Distributes load across 7 models:
    1. minimax-m2:cloud (lightweight, fast)
    2. glm-4.6:cloud
    3. gpt-oss:120b-cloud (large model)
    4. qwen3-coder:480b-cloud (code specialist)
    5. qwen3-vl:235b-cloud (vision)
    6. qwen2.5-coder:latest (LOCAL - use sparingly!)
    7. deepseek-v3.1:671b-cloud (reasoning)
    """

    def __init__(self):
        # Model pool configuration - USE ONLY WORKING MODELS
        self.models = {
            # Only use local-coder which works
            "local-coder": ModelStats(name="local-coder", is_local=True, max_rpm=1000),
        }

        # Only configured model
        self.model_queue = deque(["local-coder"])

        # Request tracking per model (per minute)
        self.request_history = defaultdict(deque)
        self.rpm_window = 60  # 1 minute window

    def select_model(self, role: str = "DEFAULT") -> str:
        """
        Select best model for request.

        Strategy:
        1. Try round-robin through cloud models
        2. Skip models at RPM limit
        3. Skip models with recent errors
        4. Fall back to local only if all cloud unavailable
        """
        logger.debug("selecting_model", role=role, available_models=len(self.model_queue))

        # Clean old request history
        self._clean_request_history()

        # Try each model in queue
        attempts = 0
        max_attempts = len(self.model_queue)

        while attempts < max_attempts:
            # Get next model from queue
            model_key = self.model_queue[0]

            # Rotate queue (round-robin)
            self.model_queue.rotate(-1)

            # Get model stats
            model_stats = self.models[model_key]

            # Check if model can be used
            if not model_stats.can_use():
                logger.debug(
                    "model_skipped",
                    model=model_stats.name,
                    reason="cannot_use",
                    rpm=f"{model_stats.current_rpm}/{model_stats.max_rpm}"
                )
                attempts += 1
                continue

            # Check RPM limit
            recent_requests = self._get_recent_requests(model_key)
            if len(recent_requests) >= model_stats.max_rpm:
                logger.debug(
                    "model_at_rpm_limit",
                    model=model_stats.name,
                    requests=len(recent_requests),
                    limit=model_stats.max_rpm
                )
                attempts += 1
                continue

            # Check recent errors
            if model_stats.error_count > 0 and model_stats.total_requests > 0:
                error_rate = model_stats.error_count / model_stats.total_requests
                if error_rate > 0.3:  # 30% error rate threshold
                    logger.debug(
                        "model_high_error_rate",
                        model=model_stats.name,
                        error_rate=f"{error_rate:.2%}"
                    )
                    attempts += 1
                    continue

            # Found usable model
            logger.info(
                "model_selected",
                model=model_stats.name,
                role=role,
                is_cold=model_stats.is_cold,
                avg_latency_ms=model_stats.avg_latency_ms,
                requests_this_minute=len(recent_requests)
            )

            return model_stats.name

        # All cloud models unavailable - fall back to local
        local_model = self.models["local-coder"]

        # Check if local model is at RPM limit
        recent_local = self._get_recent_requests("local-coder")
        if len(recent_local) >= local_model.max_rpm:
            logger.error(
                "all_models_unavailable",
                cloud_models="all_at_limit_or_failed",
                local_model="at_rpm_limit",
                local_rpm=f"{len(recent_local)}/{local_model.max_rpm}"
            )
            # Still return local model as last resort (system will handle timeout)
        else:
            logger.warning(
                "falling_back_to_local_model",
                local_model=local_model.name,
                local_rpm=f"{len(recent_local)}/{local_model.max_rpm}",
                reason="all_cloud_models_unavailable"
            )

        return local_model.name

    def record_result(
        self,
        model_name: str,
        latency_ms: float,
        success: bool
    ):
        """
        Record request result for model.

        Args:
            model_name: Model that was used
            latency_ms: Request latency
            success: Did request succeed?
        """
        # Find model stats
        model_stats = None
        for stats in self.models.values():
            if stats.name == model_name:
                model_stats = stats
                break

        if not model_stats:
            logger.warning("model_not_found_in_stats", model=model_name)
            return

        # Record request
        model_stats.record_request(latency_ms, success)

        # Add to history
        model_key = self._get_model_key(model_name)
        if model_key:
            self.request_history[model_key].append(time.time())

        logger.debug(
            "request_recorded",
            model=model_name,
            latency_ms=latency_ms,
            success=success,
            total_requests=model_stats.total_requests
        )

    def _get_model_key(self, model_name: str) -> Optional[str]:
        """Get model key from model name"""
        for key, stats in self.models.items():
            if stats.name == model_name:
                return key
        return None

    def _clean_request_history(self):
        """Remove old request history (older than 1 minute)"""
        cutoff = time.time() - self.rpm_window

        for model_key in list(self.request_history.keys()):
            queue = self.request_history[model_key]

            # Remove old entries
            while queue and queue[0] < cutoff:
                queue.popleft()

            # Update RPM counter
            for stats in self.models.values():
                if self._get_model_key(stats.name) == model_key:
                    stats.current_rpm = len(queue)
                    break

    def _get_recent_requests(self, model_key: str) -> deque:
        """Get recent requests for a model"""
        return self.request_history.get(model_key, deque())

    def get_stats(self) -> Dict[str, Dict]:
        """Get statistics for all models"""
        stats = {}
        for key, model_stats in self.models.items():
            stats[key] = {
                "name": model_stats.name,
                "is_local": model_stats.is_local,
                "total_requests": model_stats.total_requests,
                "requests_last_minute": model_stats.current_rpm,
                "avg_latency_ms": round(model_stats.avg_latency_ms, 2),
                "success_rate": (
                    model_stats.success_count / model_stats.total_requests
                    if model_stats.total_requests > 0 else 0
                ),
                "is_cold": model_stats.is_cold,
                "last_used": model_stats.last_used.isoformat() if model_stats.last_used else None
            }
        return stats

    def get_recommendation(self) -> Dict[str, str]:
        """Get recommendation for model usage"""
        # Find best performing model
        best_model = None
        best_score = float('inf')

        for key, model_stats in self.models.items():
            if model_stats.total_requests < 5:  # Need more data
                continue

            score = model_stats.get_score()
            if score < best_score:
                best_score = score
                best_model = model_stats

        if best_model:
            return {
                "best_model": best_model.name,
                "avg_latency_ms": round(best_model.avg_latency_ms, 2),
                "success_rate": f"{(best_model.success_count / best_model.total_requests * 100):.1f}%"
            }

        return {"best_model": "insufficient_data"}


# Global instance
model_rotator = ModelRotator()
