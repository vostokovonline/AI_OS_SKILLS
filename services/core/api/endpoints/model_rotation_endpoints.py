"""
Model Rotation Monitoring API
=============================

Endpoints for monitoring LLM model rotation and load balancing.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime

from model_rotator import model_rotator
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/rotation/stats")
async def get_rotation_stats() -> Dict[str, Any]:
    """
    Get statistics for all models in rotation.

    Returns:
        Per-model statistics including:
        - Total requests
        - Requests last minute
        - Average latency
        - Success rate
        - Cold start status
    """
    try:
        stats = model_rotator.get_stats()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_models": len(stats),
            "models": stats
        }
    except Exception as e:
        logger.error("failed_to_get_rotation_stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rotation/recommendation")
async def get_rotation_recommendation() -> Dict[str, Any]:
    """
    Get recommendation for model usage based on performance.

    Returns:
        Best performing model and stats
    """
    try:
        recommendation = model_rotator.get_recommendation()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "recommendation": recommendation
        }
    except Exception as e:
        logger.error("failed_to_get_recommendation", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rotation/queue")
async def get_rotation_queue() -> Dict[str, Any]:
    """
    Get current rotation queue order.

    Returns:
        Current order of models in round-robin queue
    """
    try:
        # Get queue order
        queue_order = list(model_rotator.model_queue)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "queue_length": len(queue_order),
            "queue_order": queue_order,
            "next_up": queue_order[0] if queue_order else None
        }
    except Exception as e:
        logger.error("failed_to_get_queue", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rotation/test")
async def test_rotation(num_requests: int = 10) -> Dict[str, Any]:
    """
    Test model rotation by simulating requests.

    Args:
        num_requests: Number of requests to simulate

    Returns:
        Distribution of selected models
    """
    try:
        selection_counts = {}

        for i in range(num_requests):
            model_name = model_rotator.select_model("TEST")

            if model_name not in selection_counts:
                selection_counts[model_name] = 0
            selection_counts[model_name] += 1

            # Simulate random latency
            import random
            latency = random.uniform(1000, 5000)
            success = random.random() > 0.1  # 90% success rate

            # Record result
            model_rotator.record_result(model_name, latency, success)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_simulated": num_requests,
            "distribution": selection_counts,
            "final_stats": model_rotator.get_stats()
        }
    except Exception as e:
        logger.error("failed_to_test_rotation", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rotation/test-fallback")
async def test_fallback() -> Dict[str, Any]:
    """
    Test fallback to local model by simulating cloud model failure.

    Simulates all cloud models hitting RPM limit to force fallback.
    """
    try:
        from model_rotator import model_rotator

        # Simulate all cloud models hitting RPM limit
        for key in ["minimax-cloud", "glm-cloud", "qwen3-coder-cloud",
                    "deepseek-cloud", "gpt-oss-cloud", "qwen3-vl-cloud"]:
            model = model_rotator.models[key]
            model.current_rpm = model.max_rpm  # Set to max

        # Now try to select a model - should fall back to local
        fallback_model = model_rotator.select_model("TEST_FALLBACK")

        # Reset RPM limits
        for key in ["minimax-cloud", "glm-cloud", "qwen3-coder-cloud",
                    "deepseek-cloud", "gpt-oss-cloud", "qwen3-vl-cloud"]:
            model = model_rotator.models[key]
            model.current_rpm = 0

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "test": "fallback_to_local",
            "fallback_model": fallback_model,
            "expected": "ollama/qwen2.5-coder:latest",
            "success": fallback_model == "ollama/qwen2.5-coder:latest"
        }
    except Exception as e:
        logger.error("failed_to_test_fallback", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
