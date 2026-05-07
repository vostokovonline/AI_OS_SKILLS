"""
Reward Decomposition
=====================

Proper reward model for bandit learning:

reward = 
    success_reward (1.0)
    - latency_penalty (time cost)
    - retry_penalty (multiple attempts cost)
    - tool_cost_penalty (resource usage)
    - hallucination_penalty (invalid outputs)
    + artifact_quality (output quality bonus)

This ensures Gaussian learns CAPABILITY, not just survivability.
"""

from dataclasses import dataclass
from typing import Optional


# Reward component weights
SUCCESS_REWARD = 1.0
LATENCY_PENALTY_PER_SEC = 0.05  # 50ms penalty per second
RETRY_PENALTY = 0.15  # 0.15 per failed attempt before success
TOOL_COST_PER_CALL = 0.01  # 0.01 per tool call
HALLUCINATION_PENALTY = 0.3  # Penalty for hallucinated content
ARTIFACT_QUALITY_BONUS = 0.2  # Bonus for high-quality artifacts


@dataclass
class RewardComponents:
    """Breakdown of reward calculation"""
    success: bool
    latency_ms: float
    attempt_num: int
    tool_calls: int
    hallucination_score: float  # 0-1, how likely hallucinated
    artifact_quality: float     # 0-1, quality of output
    
    # Computed
    success_component: float = 0.0
    latency_component: float = 0.0
    retry_component: float = 0.0
    tool_cost_component: float = 0.0
    hallucination_component: float = 0.0
    artifact_quality_component: float = 0.0
    
    total: float = 0.0


def compute_reward(
    success: bool,
    latency_ms: float,
    attempt_num: int = 1,
    tool_calls: int = 0,
    hallucination_score: float = 0.0,
    artifact_quality: float = 0.0,
    include_components: bool = False
) -> float | RewardComponents:
    """
    Compute decomposed reward.
    
    Args:
        success: Whether attempt succeeded
        latency_ms: Execution time in milliseconds
        attempt_num: Which attempt (1 = first, >1 = retry)
        tool_calls: Number of tool calls made
        hallucination_score: 0-1, likelihood of hallucination
        artifact_quality: 0-1, quality of output artifacts
        include_components: Return full breakdown if True
    
    Returns:
        float total reward, or RewardComponents if include_components=True
    """
    
    # 1. Success component
    success_component = SUCCESS_REWARD if success else 0.0
    
    # 2. Latency penalty (normalized to seconds)
    latency_seconds = latency_ms / 1000.0
    latency_component = -LATENCY_PENALTY_PER_SEC * latency_seconds
    
    # 3. Retry penalty (only for attempts > 1)
    retry_component = -RETRY_PENALTY * (attempt_num - 1) if attempt_num > 1 else 0.0
    
    # 4. Tool cost penalty
    tool_cost_component = -TOOL_COST_PER_CALL * tool_calls
    
    # 5. Hallucination penalty (only if failed and suspicious)
    hallucination_component = 0.0
    if not success and hallucination_score > 0.5:
        hallucination_component = -HALLUCINATION_PENALTY * hallucination_score
    
    # 6. Artifact quality bonus (only if success)
    artifact_quality_component = 0.0
    if success:
        artifact_quality_component = ARTIFACT_QUALITY_BONUS * artifact_quality
    
    # Total
    total = (
        success_component
        + latency_component
        + retry_component
        + tool_cost_component
        + hallucination_component
        + artifact_quality_component
    )
    
    if include_components:
        return RewardComponents(
            success=success,
            latency_ms=latency_ms,
            attempt_num=attempt_num,
            tool_calls=tool_calls,
            hallucination_score=hallucination_score,
            artifact_quality=artifact_quality,
            success_component=success_component,
            latency_component=latency_component,
            retry_component=retry_component,
            tool_cost_component=tool_cost_component,
            hallucination_component=hallucination_component,
            artifact_quality_component=artifact_quality_component,
            total=total
        )
    
    return total


def normalize_for_gaussian(raw_reward: float) -> float:
    """
    Normalize reward for Gaussian TS using tanh.
    
    This bounds rewards to [-1, 1] while preserving order.
    """
    import math
    SCALE = 3.0  # Beyond this, rewards are saturated
    return math.tanh(raw_reward / SCALE)


# Example usage and tests
if __name__ == "__main__":
    print("=== Reward Decomposition Tests ===\n")
    
    # Test 1: First attempt success, fast
    r1 = compute_reward(success=True, latency_ms=500, attempt_num=1)
    print(f"Fast success: {r1:+.3f}")
    
    # Test 2: First attempt success, slow
    r2 = compute_reward(success=True, latency_ms=5000, attempt_num=1)
    print(f"Slow success: {r2:+.3f}")
    
    # Test 3: Retry then success
    r3 = compute_reward(success=True, latency_ms=500, attempt_num=2)
    print(f"Retry success: {r3:+.3f}")
    
    # Test 4: Failed attempt
    r4 = compute_reward(success=False, latency_ms=1000, attempt_num=1)
    print(f"Failed attempt: {r4:+.3f}")
    
    # Test 5: Many retries, slow
    r5 = compute_reward(success=True, latency_ms=3000, attempt_num=3)
    print(f"Many retries: {r5:+.3f}")
    
    # Test 6: With tool cost
    r6 = compute_reward(success=True, latency_ms=1000, attempt_num=1, tool_calls=50)
    print(f"Many tool calls: {r6:+.3f}")
    
    print("\n=== Component Breakdown ===")
    comp = compute_reward(
        success=True,
        latency_ms=1500,
        attempt_num=2,
        tool_calls=30,
        hallucination_score=0.0,
        artifact_quality=0.8,
        include_components=True
    )
    print(f"Success:    {comp.success_component:+.3f}")
    print(f"Latency:    {comp.latency_component:+.3f}")
    print(f"Retry:      {comp.retry_component:+.3f}")
    print(f"Tool Cost:  {comp.tool_cost_component:+.3f}")
    print(f"Artifact:   {comp.artifact_quality_component:+.3f}")
    print(f"TOTAL:      {comp.total:+.3f}")
    
    print("\n=== Normalization ===")
    for raw in [-3.0, -1.0, 0.0, 1.0, 3.0]:
        norm = normalize_for_gaussian(raw)
        print(f"raw {raw:+.1f} -> normalized {norm:+.3f}")