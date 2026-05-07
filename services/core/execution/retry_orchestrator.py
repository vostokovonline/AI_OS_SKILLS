"""
Retry Orchestrator - Thin retry/fallback/escalation layer

Provides resilience without adding business logic.
Executors remain "dumb" - this layer handles failures.

Author: AI-OS Architecture v3.1
Date: 2026-03-03
"""

import hashlib
import time
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Type, Optional, Dict, Any
from enum import Enum
from uuid import uuid4

import httpx

from execution.task_analyzer import TaskAnalyzer, LowConfidenceException
from execution.capability_router import CapabilityRouter, NoCapabilityFound
from execution.execution_dispatcher import ExecutionDispatcher, TaskContext, ExecutionResult


# =============================================================================
# Escalation Status
# =============================================================================

class EscalationStatus(str, Enum):
    """Structured escalation reasons."""
    TIMEOUT_EXHAUSTED = "timeout_exhausted"          # All retries exhausted
    DEADLINE_EXCEEDED = "deadline_exceeded"          # Overall SLA breached
    NO_FALLBACK = "no_fallback"                      # No fallback available
    STRUCTURAL_ERROR = "structural_error"            # Non-retryable error


# =============================================================================
# Retry Policy
# =============================================================================

@dataclass
class RetryPolicy:
    """
    Deterministic retry configuration.

    Only retry TEMPORARY errors:
    - Network timeouts
    - HTTP 5xx errors

    DO NOT retry STRUCTURAL errors:
    - LowConfidence (deterministic, won't change)
    - NoCapabilityFound (capability missing)
    - InvalidLLMOutput (contract violation)
    """
    max_attempts: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 10000
    backoff_multiplier: float = 2.0
    jitter: bool = True  # Add +/- 10% randomness to prevent thundering herd

    # Temporary errors - safe to retry
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        httpx.TimeoutException,
        httpx.HTTPStatusError,
    )

    # Structural errors - do NOT retry
    non_retryable: Tuple[Type[Exception], ...] = (
        LowConfidenceException,
        NoCapabilityFound,
        ValueError,
    )

    def is_retryable(self, error: Exception) -> bool:
        """
        Check if error is retryable.

        Args:
            error: Exception to check

        Returns:
            True if error is temporary and retry is safe
        """
        return isinstance(error, self.retryable_exceptions)

    def is_non_retryable(self, error: Exception) -> bool:
        """
        Check if error is structural (should escalate immediately).

        Args:
            error: Exception to check

        Returns:
            True if error is structural and escalation is required
        """
        return isinstance(error, self.non_retryable)

    def calculate_backoff(self, attempt: int) -> int:
        """
        Calculate exponential backoff with jitter.

        Formula: min(base_delay * multiplier^attempt, max_delay)
        With jitter: +/- 10% randomness

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in milliseconds
        """
        # Exponential backoff
        delay = self.base_delay_ms * (self.backoff_multiplier ** attempt)

        # Cap at max
        delay = min(delay, self.max_delay_ms)

        # Add jitter to prevent thundering herd
        if self.jitter:
            jitter_range = delay * 0.1  # +/- 10%
            delay += random.uniform(-jitter_range, jitter_range)

        return int(max(0, delay))


# =============================================================================
# Fallback Configuration
# =============================================================================

@dataclass
class FallbackConfig:
    """
    Fallback strategy configuration.

    Transparency is critical - fallback MUST be observable.
    """
    # LLM model fallback chain
    llm_models: List[str] = field(default_factory=lambda: [
        "gpt-4o-mini",      # Primary
        "ollama/qwen2.5",   # Fallback
    ])

    # Capability fallback (when no capability matches intent)
    fallback_capability: Optional[str] = None  # e.g., "echo"

    # Prevent silent degradation
    require_explicit_fallback: bool = True

    def can_fallback_capability(self) -> bool:
        """
        Check if capability fallback is configured.

        Returns:
            True if fallback capability is explicitly set
        """
        return self.fallback_capability is not None

    def get_fallback_model(self, failed_model: str) -> Optional[str]:
        """
        Get next LLM model in fallback chain.

        Args:
            failed_model: Model that just failed

        Returns:
            Next model in chain, or None if exhausted
        """
        try:
            idx = self.llm_models.index(failed_model)
            if idx + 1 < len(self.llm_models):
                return self.llm_models[idx + 1]
        except ValueError:
            pass
        return None


# =============================================================================
# Execution Context
# =============================================================================

@dataclass
class ExecutionContext:
    """
    Track execution for observability and SLA.
    """
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    attempt_number: int = 1
    completed_attempts: int = 0  # Actual number of execution attempts made
    error_chain: List[str] = field(default_factory=list)

    # SLA metrics
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    deadline: Optional[float] = None  # Absolute timestamp

    def record_error(self, error: Exception):
        """
        Record error in chain.

        Note: completed_attempts is incremented BEFORE execution attempt,
        so it already reflects the current attempt number.

        Args:
            error: Exception that occurred
        """
        self.error_chain.append(
            f"Attempt {self.completed_attempts}: {type(error).__name__}: {str(error)}"
        )
        self.attempt_number += 1  # Next attempt would be this number

    @property
    def total_duration_ms(self) -> Optional[int]:
        """Total execution time in milliseconds."""
        if self.end_time:
            return int((self.end_time - self.start_time) * 1000)
        return None

    @property
    def elapsed_ms(self) -> int:
        """Elapsed time so far (for in-flight checks)."""
        return int((time.time() - self.start_time) * 1000)

    @property
    def is_deadline_exceeded(self) -> bool:
        """Check if overall deadline has been exceeded."""
        if self.deadline:
            return time.time() > self.deadline
        return False

    def mark_complete(self):
        """Mark execution as complete."""
        self.end_time = time.time()


# =============================================================================
# Retry Orchestrator
# =============================================================================

class RetryOrchestrator:
    """
    Thin orchestration layer for retry/fallback/escalation.

    Design principles:
    - Only retry TEMPORARY errors (network, timeout)
    - Escalate STRUCTURAL errors immediately (LowConfidence, NoCapability)
    - Fallback transparency (always logged in metadata)
    - SLA awareness (deadline checking)

    Does NOT:
    - Make business decisions
    - Access Router/Dispatcher directly
    - Retry LowConfidence (deterministic, won't change)
    - Silent fallback
    """

    def __init__(
        self,
        analyzer: TaskAnalyzer,
        router: CapabilityRouter,
        dispatcher: ExecutionDispatcher,
        retry_policy: RetryPolicy = RetryPolicy(),
        fallback_config: FallbackConfig = FallbackConfig(),
        max_duration_seconds: float = 60.0
    ):
        """
        Initialize orchestrator.

        Args:
            analyzer: Task analyzer layer
            router: Capability router layer
            dispatcher: Execution dispatcher layer
            retry_policy: Retry configuration
            fallback_config: Fallback strategy
            max_duration_seconds: Overall SLA for task
        """
        self.analyzer = analyzer
        self.router = router
        self.dispatcher = dispatcher
        self.retry_policy = retry_policy
        self.fallback_config = fallback_config
        self.max_duration_seconds = max_duration_seconds

    def execute(self, task: str) -> ExecutionResult:
        """
        Execute task with retry/fallback/escalation.

        Flow:
        1. Try primary execution (with retry for temporary errors)
        2. Try fallback capability (if structural failure)
        3. Escalate to human (if everything fails)

        CRITICAL: First attempt ALWAYS executes.
        Retry only if capability.retry_safe == True.

        Args:
            task: User task text

        Returns:
            ExecutionResult with success/failure and metadata
        """
        ctx = ExecutionContext(
            deadline=time.time() + self.max_duration_seconds
        )

        # Step 1: Analyze and route (ONCE - before retry loop)
        try:
            analysis = self.analyzer.analyze(task)
            selection = self.router.route(analysis.intent)
        except Exception as e:
            # Analysis/routing failed - no capability selected yet
            ctx.record_error(e)
            return self._escalate(task, ctx, EscalationStatus.STRUCTURAL_ERROR)

        selected_capability = selection.selected

        # Step 2: Attempt 1-N: Primary execution with retry
        last_result = None  # Track last execution result for fallback safety

        for attempt in range(self.retry_policy.max_attempts):
            # Check deadline before each attempt
            if ctx.is_deadline_exceeded:
                return self._escalate(
                    task, ctx, EscalationStatus.DEADLINE_EXCEEDED
                )

            # Count this attempt
            ctx.completed_attempts += 1

            try:
                result = self._dispatch(selected_capability, analysis.intent, task, ctx)
                last_result = result  # Store for fallback decision

                # Add execution metadata
                result.metadata["execution_id"] = ctx.execution_id
                result.metadata["total_attempts"] = ctx.completed_attempts
                result.metadata["total_duration_ms"] = ctx.elapsed_ms
                ctx.mark_complete()
                return result

            except Exception as e:
                ctx.record_error(e)

                # Check if non-retryable (escalate immediately)
                if self.retry_policy.is_non_retryable(e):
                    # Fallback ONLY for NoCapabilityFound
                    if isinstance(e, NoCapabilityFound):
                        # Check deadline BEFORE fallback
                        if ctx.is_deadline_exceeded:
                            return self._escalate(
                                task, ctx, EscalationStatus.DEADLINE_EXCEEDED
                            )

                        if self.fallback_config.can_fallback_capability():
                            return self._try_fallback(
                                task, ctx,
                                last_result=last_result
                            )
                        else:
                            # No fallback configured
                            return self._escalate(
                                task, ctx, EscalationStatus.NO_FALLBACK
                            )
                    # All other non-retryable errors → escalate
                    return self._escalate(
                        task, ctx, EscalationStatus.STRUCTURAL_ERROR
                    )

                # Check if retryable
                if self.retry_policy.is_retryable(e):
                    # CRITICAL: Check capability retry_safe before retrying
                    if not selected_capability.retry_safe:
                        # Capability is not retry-safe - escalate immediately
                        return self._escalate(
                            task, ctx, EscalationStatus.STRUCTURAL_ERROR
                        )

                    # Check if we have more attempts
                    if attempt < self.retry_policy.max_attempts - 1:
                        delay_ms = self.retry_policy.calculate_backoff(attempt)
                        time.sleep(delay_ms / 1000)

                        # Check deadline AFTER backoff
                        if ctx.is_deadline_exceeded:
                            return self._escalate(
                                task, ctx, EscalationStatus.DEADLINE_EXCEEDED
                            )
                        continue
                    else:
                        # Retries exhausted
                        return self._escalate(
                            task, ctx, EscalationStatus.TIMEOUT_EXHAUSTED
                        )

                # Unknown error type - escalate
                return self._escalate(task, ctx, EscalationStatus.STRUCTURAL_ERROR)

        # Should not reach here, but handle gracefully
        return self._escalate(task, ctx, EscalationStatus.TIMEOUT_EXHAUSTED)

    def _dispatch(
        self,
        capability,
        intent,
        task: str,
        ctx: ExecutionContext
    ) -> ExecutionResult:
        """
        Dispatch capability to executor.

        Args:
            capability: Selected capability
            intent: Task intent from analyzer
            task: User task text
            ctx: Execution context

        Returns:
            ExecutionResult

        Raises:
            Exception from executor
        """
        context = TaskContext(
            intent=intent,
            raw_input=task,
            parameters={}
        )

        result = self.dispatcher.dispatch(
            type('SelectionResult', (object,), {'selected': capability}),
            context
        )

        # Check if execution itself failed
        if not result.success:
            raise RuntimeError(result.error)

        return result

    def _try_fallback(
        self,
        task: str,
        ctx: ExecutionContext,
        last_result: Optional[ExecutionResult] = None
    ) -> ExecutionResult:
        """
        Try fallback capability.

        CRITICAL: Fallback only safe if:
        - Primary was NOT executed (error before executor)
        - OR primary execution did NOT commit side effect

        Args:
            task: User task text
            ctx: Execution context
            last_result: Last execution result from primary attempt

        Returns:
            ExecutionResult with fallback metadata
        """
        # Check fallback safety based on side_effect_committed
        if last_result and last_result.side_effect_committed:
            # Primary committed a side effect - fallback is unsafe
            # This prevents duplicate side effects
            return self._escalate(
                task, ctx, EscalationStatus.STRUCTURAL_ERROR
            )

        # Use echo capability as fallback (simplest)
        # This is honest - user knows we fell back
        from execution.capability_contract import SkillCapability, ExecutionType
        from execution.intent_schema import (
            IntentType, InputType, OutputType, ComplexityLevel, TaskIntent
        )

        fallback_capability = SkillCapability(
            name=self.fallback_config.fallback_capability,
            intent=IntentType.TRANSFORM,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=0,
            idempotency=IdempotencyLevel.SAFE  # Fallback must be safe
        )

        # ✅ NEW: Check fallback capability safety BEFORE execution
        if not fallback_capability.retry_safe:
            # Fallback capability itself is not retry-safe → unsafe
            return self._escalate(
                task, ctx, EscalationStatus.STRUCTURAL_ERROR
            )

        try:
            # Count fallback as an attempt
            ctx.completed_attempts += 1

            # Create proper TaskIntent for fallback
            fallback_intent = TaskIntent(
                intent=IntentType.TRANSFORM,
                input_type=InputType.TEXT,
                output_type=OutputType.TEXT,
                requires_persistence=False,
                requires_external_io=False,
                complexity=ComplexityLevel.LOW,
                estimated_tokens=100,
                confidence=1.0  # Fallback always has high confidence
            )

            context = TaskContext(
                intent=fallback_intent,  # Proper TaskIntent, not IntentType
                raw_input=task,
                parameters={}
            )

            # Get executor for fallback capability
            executor = self.dispatcher._executors.get(fallback_capability.execution_type)
            if not executor:
                raise RuntimeError(f"No executor for {fallback_capability.execution_type}")

            result = executor.execute(fallback_capability, context)

            # ✅ REMOVED: Manual override of side_effect_committed
            # Let executor honestly report - fail closed is systemic principle
            # If fallback is SAFE (idempotency=SAFE), executor should report False

            # Mark as fallback in metadata
            result.metadata["fallback_used"] = True
            result.metadata["fallback_reason"] = ctx.error_chain[-1] if ctx.error_chain else "unknown"
            result.metadata["execution_id"] = ctx.execution_id
            result.metadata["total_attempts"] = ctx.completed_attempts
            result.metadata["total_duration_ms"] = ctx.elapsed_ms

            ctx.mark_complete()
            return result

        except Exception as e:
            ctx.record_error(e)
            return self._escalate(task, ctx, EscalationStatus.NO_FALLBACK)

    def _escalate(
        self,
        task: str,
        ctx: ExecutionContext,
        status: EscalationStatus
    ) -> ExecutionResult:
        """
        Escalate with structured result.

        Args:
            task: User task text
            ctx: Execution context
            status: Escalation status

        Returns:
            ExecutionResult with escalation metadata
        """
        ctx.mark_complete()

        return ExecutionResult(
            success=False,
            side_effect_committed=False,  # Escalation = no side effect committed
            output=None,
            error=f"Escalated: {status.value}",
            executor_type=None,  # Escalated = no executor
            capability_name=None,  # Escalated = no capability
            metadata={
                "escalation_status": status.value,
                "execution_id": ctx.execution_id,
                "total_attempts": ctx.completed_attempts,
                "total_duration_ms": ctx.total_duration_ms,
                "error_chain": ctx.error_chain,
                "raw_task": task
            }
        )
