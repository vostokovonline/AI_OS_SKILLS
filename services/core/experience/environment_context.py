"""
Environment-Driven Failure Injection
======================================

Replaces synthetic chaos with realistic failure modes:

- file_size > threshold → write_file becomes unreliable
- web_research rate limit → degraded reliability
- network latency spikes → skill timeout
- disk full → file operations fail
- etc.

This creates NON-STATIONARY environment - key for bandit learning.
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime, timedelta


@dataclass
class EnvCondition:
    """Current environment condition affecting skill reliability"""
    condition_name: str
    severity: float  # 0-1, affects failure probability
    expires_at: Optional[datetime] = None


class EnvironmentContext:
    """
    Tracks environment conditions that affect skill reliability.
    
    Failure rates are computed from:
    - Base skill reliability (from historical data)
    - Environment conditions (current system state)
    - Context factors (task complexity, file sizes, etc.)
    """
    
    # Environment condition tracking
    _conditions: Dict[str, EnvCondition] = {}
    _last_update: datetime = datetime.utcnow()
    
    @classmethod
    def update_condition(cls, name: str, severity: float, duration_minutes: int = 60):
        """Set an environment condition"""
        expires = datetime.utcnow() + timedelta(minutes=duration_minutes)
        cls._conditions[name] = EnvCondition(
            condition_name=name,
            severity=severity,
            expires_at=expires
        )
        cls._last_update = datetime.utcnow()
    
    @classmethod
    def clear_condition(cls, name: str):
        """Clear an environment condition"""
        cls._conditions.pop(name, None)
    
    @classmethod
    def get_active_conditions(cls) -> Dict[str, float]:
        """Get all active conditions and their severity"""
        now = datetime.utcnow()
        active = {}
        for name, cond in cls._conditions.items():
            if cond.expires_at and now > cond.expires_at:
                continue
            active[name] = cond.severity
        return active
    
    @classmethod
    def compute_failure_rate(cls, skill_id: str, base_reliability: float, context: Dict) -> float:
        """
        Compute actual failure rate based on environment.
        
        Args:
            skill_id: Which skill
            base_reliability: Historical reliability (0-1)
            context: Execution context (file_size, task_complexity, etc.)
        
        Returns:
            Computed failure rate (0-1)
        """
        # Start with base reliability
        reliability = base_reliability
        
        # Apply environment conditions
        active = cls.get_active_conditions()
        
        # File size affects write_file
        if skill_id == "write_file" or "write" in skill_id:
            file_size = context.get("file_size", 0)
            if file_size > 1_000_000:  # 1MB
                reliability *= 0.7  # 30% degradation
            elif file_size > 100_000:  # 100KB
                reliability *= 0.9
        
        # Rate limit affects web skills
        if "web" in skill_id or "search" in skill_id:
            if "rate_limit" in active:
                reliability *= (1.0 - active["rate_limit"])
            # Time of day (web APIs slower at peak)
            hour = datetime.utcnow().hour
            if 9 <= hour <= 11 or 14 <= hour <= 16:
                reliability *= 0.95
        
        # Network latency affects all remote skills
        if "network" in active:
            latency_penalty = active["network"] * 0.3
            reliability *= (1.0 - latency_penalty)
        
        # Complexity affects all skills
        complexity = context.get("task_complexity", 0.5)
        if complexity > 0.8:
            reliability *= 0.85
        
        # Convert to failure rate
        failure_rate = 1.0 - max(0.1, min(1.0, reliability))
        
        return failure_rate
    
    @classmethod
    def should_fail(cls, skill_id: str, base_reliability: float, context: Dict) -> bool:
        """
        Determine if skill should fail based on environment.
        
        Uses failure rate to probabilistically determine outcome.
        """
        failure_rate = cls.compute_failure_rate(skill_id, base_reliability, context)
        import random
        return random.random() < failure_rate
    
    @classmethod
    def compute_realistic_failure(cls, skill_id: str, task_context: Dict) -> float:
        """
        Compute failure rate from task characteristics (NOT synthetic).
        
        This is the TRUE environment-driven failure - depends on:
        - Task complexity
        - Resource requirements
        - System load
        - Historical patterns
        
        Args:
            skill_id: Which skill
            task_context: {
                "complexity": 0-1,
                "input_size": bytes,
                "requires_network": bool,
                "requires_filesystem": bool,
                "estimated_duration_ms": int
            }
        
        Returns:
            Realistic failure rate based on task + environment
        """
        complexity = task_context.get("complexity", 0.5)
        input_size = task_context.get("input_size", 0)
        requires_network = task_context.get("requires_network", False)
        requires_fs = task_context.get("requires_filesystem", False)
        
        # Base failure increases with complexity
        base_failure = 0.1 + 0.3 * complexity
        
        # Large inputs stress write_file
        if "write" in skill_id and input_size > 100_000:
            base_failure += 0.15
        
        # Network-dependent skills fail during rate limits
        if requires_network:
            active = cls.get_active_conditions()
            if "rate_limit" in active:
                base_failure += active["rate_limit"] * 0.4
            if "network" in active:
                base_failure += active["network"] * 0.2
        
        # Filesystem skills fail under disk pressure
        if requires_fs:
            active = cls.get_active_conditions()
            if "disk_full" in active:
                base_failure += active["disk_full"] * 0.5
        
        # Time-based patterns (API throttling at peak hours)
        hour = datetime.utcnow().hour
        if 9 <= hour <= 11 or 14 <= hour <= 16:  # Peak hours
            if requires_network:
                base_failure += 0.1
        
        return min(0.95, max(0.05, base_failure))


# Convenience functions for condition management
def inject_rate_limit(minutes: int = 30, severity: float = 0.5):
    """Inject rate limit condition"""
    EnvironmentContext.update_condition("rate_limit", severity, minutes)


def inject_network_issue(minutes: int = 30, severity: float = 0.4):
    """Inject network issue"""
    EnvironmentContext.update_condition("network", severity, minutes)


def inject_disk_pressure(minutes: int = 60, severity: float = 0.3):
    """Inject disk space pressure"""
    EnvironmentContext.update_condition("disk_full", severity, minutes)


def clear_all_conditions():
    """Clear all environment conditions"""
    EnvironmentContext._conditions.clear()


# For testing - simulate realistic conditions
def simulate_workday_conditions():
    """Simulate typical workday environment variations"""
    hour = datetime.utcnow().hour
    
    # Morning peak
    if 9 <= hour <= 11:
        inject_network_issue(minutes=15, severity=0.2)
    
    # Afternoon peak
    if 14 <= hour <= 16:
        inject_rate_limit(minutes=30, severity=0.15)


if __name__ == "__main__":
    print("=== Environment Context Demo ===\n")
    
    # Test base reliability
    base = 0.9  # 90% reliable skill
    ctx = {"file_size": 500_000, "task_complexity": 0.6}
    
    rate = EnvironmentContext.compute_failure_rate("write_file", base, ctx)
    print(f"write_file failure rate (large file): {rate:.1%}")
    
    rate = EnvironmentContext.compute_failure_rate("web_research", base, ctx)
    print(f"web_research failure rate (base): {rate:.1%}")
    
    # Add rate limit
    inject_rate_limit(minutes=60, severity=0.5)
    rate = EnvironmentContext.compute_failure_rate("web_research", base, ctx)
    print(f"web_research failure rate (with rate limit): {rate:.1%}")
    
    print(f"\nActive conditions: {EnvironmentContext.get_active_conditions()}")