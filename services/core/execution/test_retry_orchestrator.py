"""
Retry Orchestrator Tests - Production-Grade Scenarios

Tests:
1. LLM timeout → retry → success
2. LLM timeout → retry → retry → fail
3. LowConfidence → escalate immediately (NO retry)
4. NoCapabilityFound → fallback → success
5. NoCapabilityFound → escalate (no fallback configured)
6. Executor exception → bubbles correctly
7. Backoff calculation (exponential + jitter)
8. Deadline exceeded
9. Fallback transparency (metadata verification)
10. SLA metrics (execution_id, duration, error_chain)

Run: pytest execution/test_retry_orchestrator.py -v
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

import httpx

from execution.retry_orchestrator import (
    RetryOrchestrator,
    RetryPolicy,
    FallbackConfig,
    ExecutionContext,
    EscalationStatus
)
from execution.task_analyzer import TaskAnalyzer, LowConfidenceException
from execution.capability_router import CapabilityRouter, NoCapabilityFound
from execution.execution_dispatcher import (
    ExecutionDispatcher,
    BaseExecutor,
    TaskContext,
    ExecutionResult
)
from execution.capability_contract import SkillCapability, ExecutionType
from execution.intent_schema import (
    TaskIntent,
    IntentType,
    InputType,
    OutputType,
    ComplexityLevel
)


# =============================================================================
# Mock Executors
# =============================================================================

class MockLLMExecutor(BaseExecutor):
    """Mock LLM executor that can simulate failures."""

    def __init__(self, fail_times: int = 0, exception: Exception = None):
        """
        Initialize mock executor.

        Args:
            fail_times: Number of times to fail before succeeding
            exception: Exception to raise when failing
        """
        self.fail_times = fail_times
        self.exception = exception
        self.call_count = 0

    def execute(self, capability, context):
        """
        Execute capability.

        Fails for first fail_times calls, then succeeds.
        """
        self.call_count += 1

        if self.call_count <= self.fail_times:
            raise self.exception

        return ExecutionResult(
            success=True,
            output=f"[LLM] Success after {self.call_count} attempts",
            error=None,
            executor_type=ExecutionType.LLM,
            capability_name=capability.name,
            metadata={"executor": "mock_llm", "tokens_used": 100}
        )


class MockCodeExecutor(BaseExecutor):
    """Mock code executor for fallback testing."""

    def execute(self, capability, context):
        """Execute capability (always succeeds)."""
        return ExecutionResult(
            success=True,
            output=f"[CODE] Executed {capability.name}",
            error=None,
            executor_type=ExecutionType.CODE,
            capability_name=capability.name,
            metadata={"executor": "mock_code", "function": capability.name}
        )


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_client():
    """Mock LLM client with realistic classification."""
    client = Mock()

    def mock_generate(prompt, temperature, model):
        # Check task type from prompt
        task = prompt.split('"')[1] if '"' in prompt else prompt

        if "summarize" in task.lower():
            # SUMMARIZE intent (will route to LLM executor)
            return '''```json
{
  "intent": "summarize",
  "input_type": "text",
  "output_type": "text",
  "requires_persistence": false,
  "requires_external_io": false,
  "complexity": "high",
  "estimated_tokens": 800,
  "confidence": 0.95
}
```'''
        else:
            # Default: TRANSFORM intent (will route to CODE executor)
            return '''```json
{
  "intent": "transform",
  "input_type": "text",
  "output_type": "text",
  "requires_persistence": false,
  "requires_external_io": false,
  "complexity": "low",
  "estimated_tokens": 100,
  "confidence": 0.95
}
```'''

    client.generate = Mock(side_effect=mock_generate)
    return client


@pytest.fixture
def analyzer(mock_llm_client):
    """TaskAnalyzer with mock LLM."""
    return TaskAnalyzer(llm_client=mock_llm_client, model="gpt-4o-mini")


@pytest.fixture
def router():
    """CapabilityRouter with CODE and LLM capabilities."""
    capabilities = [
        SkillCapability(
            name="echo",
            intent=IntentType.TRANSFORM,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=100
        ),
        SkillCapability(
            name="summarize_text",
            intent=IntentType.SUMMARIZE,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.HIGH,
            execution_type=ExecutionType.LLM,
            priority=50
        ),
    ]
    return CapabilityRouter(capabilities=capabilities)


@pytest.fixture
def dispatcher():
    """ExecutionDispatcher with mock executors."""
    return ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: MockLLMExecutor(fail_times=0)
    })


@pytest.fixture
def orchestrator(analyzer, router, dispatcher):
    """RetryOrchestrator with default configuration."""
    return RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher
    )


# =============================================================================
# Scenario 1: LLM timeout → retry → success
# =============================================================================

def test_llm_timeout_retry_success(analyzer, router):
    """
    Scenario 1: LLM timeout → retry → success

    Given: LLM times out on first attempt
    When: Orchestrator retries
    Then: Second attempt succeeds
    """
    # Setup: LLM executor fails once, then succeeds
    llm_executor = MockLLMExecutor(
        fail_times=1,
        exception=httpx.TimeoutException("Request timeout", request=Mock())
    )

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: llm_executor
    })

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher,
        retry_policy=RetryPolicy(max_attempts=3)
    )

    # Execute with SUMMARIZE task (routes to LLM executor)
    result = orchestrator.execute("Summarize this document")

    # Verify
    assert result.success is True
    assert llm_executor.call_count == 2  # Failed once, succeeded on retry
    assert result.metadata["total_attempts"] == 2
    assert "execution_id" in result.metadata
    assert result.metadata["total_duration_ms"] >= 0


# =============================================================================
# Scenario 2: LLM timeout → retry → retry → fail
# =============================================================================

def test_llm_timeout_retry_exhausted(analyzer, router):
    """
    Scenario 2: LLM timeout → retry → retry → fail

    Given: LLM times out on ALL attempts
    When: Orchestrator exhausts retries
    Then: Escalates with TIMEOUT_EXHAUSTED
    """
    # Setup: LLM executor always fails
    llm_executor = MockLLMExecutor(
        fail_times=999,  # Always fail
        exception=httpx.TimeoutException("Request timeout", request=Mock())
    )

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: llm_executor
    })

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher,
        retry_policy=RetryPolicy(max_attempts=3)
    )

    # Execute with SUMMARIZE task (routes to LLM executor)
    result = orchestrator.execute("Summarize this report")

    # Verify escalation
    assert result.success is False
    assert result.executor_type is None  # Escalated = no executor
    assert result.metadata["escalation_status"] == EscalationStatus.TIMEOUT_EXHAUSTED.value
    assert llm_executor.call_count == 3  # All attempts exhausted
    assert result.metadata["total_attempts"] == 3
    assert len(result.metadata["error_chain"]) == 3


# =============================================================================
# Scenario 3: LowConfidence → escalate immediately (NO retry)
# =============================================================================

def test_low_confidence_no_retry(analyzer, router):
    """
    Scenario 3: LowConfidence → escalate immediately

    Given: Analyzer returns low confidence (< 0.6)
    When: Orchestrator catches LowConfidenceException
    Then: Escalates immediately WITHOUT retry
    """
    # Setup: Mock analyzer raises LowConfidenceException
    low_confidence_analyzer = Mock(spec=TaskAnalyzer)
    low_confidence_analyzer.analyze = Mock(
        side_effect=LowConfidenceException(
            confidence=0.4,
            threshold=0.6
        )
    )

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: MockLLMExecutor()
    })

    orchestrator = RetryOrchestrator(
        analyzer=low_confidence_analyzer,
        router=router,
        dispatcher=dispatcher,
        retry_policy=RetryPolicy(max_attempts=3)
    )

    # Execute
    result = orchestrator.execute("Summarize report")

    # Verify IMMEDIATE escalation (no retry)
    assert result.success is False
    assert result.metadata["escalation_status"] == EscalationStatus.STRUCTURAL_ERROR.value
    assert result.metadata["total_attempts"] == 1  # Only 1 attempt, no retries
    assert len(result.metadata["error_chain"]) == 1
    assert "LowConfidenceException" in result.metadata["error_chain"][0]

    # Verify analyzer was called only ONCE
    assert low_confidence_analyzer.analyze.call_count == 1


# =============================================================================
# Scenario 4: NoCapabilityFound → fallback → success
# =============================================================================

def test_no_capability_fallback_success(analyzer):
    """
    Scenario 4: NoCapabilityFound → fallback → success

    Given: No capability matches intent
    When: Orchestrator tries fallback capability
    Then: Fallback executes successfully
    """
    # Setup: Empty router (no capabilities)
    empty_router = CapabilityRouter(capabilities=[])

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: MockLLMExecutor()
    })

    # Configure fallback
    fallback_config = FallbackConfig(
        fallback_capability="echo",
        require_explicit_fallback=True
    )

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=empty_router,
        dispatcher=dispatcher,
        fallback_config=fallback_config
    )

    # Execute
    result = orchestrator.execute("Unknown task")

    # Verify fallback
    assert result.success is True
    assert result.metadata["fallback_used"] is True
    assert result.capability_name == "echo"
    assert "fallback_reason" in result.metadata
    assert "execution_id" in result.metadata


# =============================================================================
# Scenario 5: NoCapabilityFound → escalate (no fallback configured)
# =============================================================================

def test_no_capability_no_fallback(analyzer):
    """
    Scenario 5: NoCapabilityFound → escalate

    Given: No capability matches intent
    And: No fallback configured
    When: Orchestrator cannot fallback
    Then: Escalates with NO_FALLBACK
    """
    # Setup: Empty router
    empty_router = CapabilityRouter(capabilities=[])

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: MockLLMExecutor()
    })

    # No fallback configured
    fallback_config = FallbackConfig(
        fallback_capability=None,  # No fallback
        require_explicit_fallback=True
    )

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=empty_router,
        dispatcher=dispatcher,
        fallback_config=fallback_config
    )

    # Execute
    result = orchestrator.execute("Unknown task")

    # Verify escalation
    assert result.success is False
    assert result.metadata["escalation_status"] == EscalationStatus.NO_FALLBACK.value
    assert result.metadata["total_attempts"] == 1
    assert "NoCapabilityFound" in result.metadata["error_chain"][0]


# =============================================================================
# Scenario 6: Executor exception → bubbles correctly
# =============================================================================

def test_executor_exception_bubbles(analyzer, router):
    """
    Scenario 6: Executor exception → bubbles correctly

    Given: Executor raises unexpected exception
    When: Orchestrator catches it
    Then: Escalates with STRUCTURAL_ERROR
    """
    # Setup: Code executor raises ValueError
    class BrokenCodeExecutor(BaseExecutor):
        def execute(self, capability, context):
            raise ValueError("Invalid input format")

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: BrokenCodeExecutor(),
        ExecutionType.LLM: MockLLMExecutor()
    })

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher
    )

    # Execute
    result = orchestrator.execute("Echo hello")

    # Verify escalation
    assert result.success is False
    assert result.metadata["escalation_status"] == EscalationStatus.STRUCTURAL_ERROR.value
    assert "ValueError" in result.metadata["error_chain"][0]
    assert "Invalid input format" in result.metadata["error_chain"][0]


# =============================================================================
# Scenario 7: Backoff calculation (exponential + jitter)
# =============================================================================

def test_exponential_backoff_with_jitter():
    """
    Scenario 7: Backoff calculation

    Given: base_delay=1000ms, multiplier=2, jitter=True
    When: Calculating delays for attempts 0, 1, 2, 3
    Then: [~1000, ~2000, ~4000, ~8000] (with +/- 10% jitter, capped at max)
    """
    policy = RetryPolicy(
        base_delay_ms=1000,
        max_delay_ms=10000,
        backoff_multiplier=2.0,
        jitter=True
    )

    delays = [policy.calculate_backoff(i) for i in range(4)]

    # Verify exponential growth
    assert delays[0] == pytest.approx(1000, rel=0.1)  # 1000 +/- 10%
    assert delays[1] == pytest.approx(2000, rel=0.1)  # 2000 +/- 10%
    assert delays[2] == pytest.approx(4000, rel=0.1)  # 4000 +/- 10%
    assert delays[3] == pytest.approx(8000, rel=0.1)  # 8000 +/- 10%


def test_exponential_backoff_capped():
    """
    Scenario 7b: Backoff capped at max_delay_ms

    Given: base_delay=5000ms, max_delay=7000ms, multiplier=2
    When: Calculating delay for attempt 2 (should be 20000ms)
    Then: Capped at 7000ms
    """
    policy = RetryPolicy(
        base_delay_ms=5000,
        max_delay_ms=7000,
        backoff_multiplier=2.0,
        jitter=False  # No jitter for predictable test
    )

    # Attempt 2: 5000 * 2^2 = 20000, but capped at 7000
    delay = policy.calculate_backoff(2)

    assert delay == 7000  # Capped


def test_backoff_without_jitter():
    """
    Scenario 7c: Backoff without jitter (deterministic)

    Given: jitter=False
    When: Calculating delays
    Then: Exact exponential values
    """
    policy = RetryPolicy(
        base_delay_ms=1000,
        max_delay_ms=10000,
        backoff_multiplier=2.0,
        jitter=False
    )

    delays = [policy.calculate_backoff(i) for i in range(4)]

    # Verify exact values (no jitter)
    assert delays == [1000, 2000, 4000, 8000]


# =============================================================================
# Scenario 8: Deadline exceeded
# =============================================================================

def test_deadline_exceeded(analyzer, router):
    """
    Scenario 8: Deadline exceeded

    Given: max_duration_seconds=0.1 (100ms)
    And: First attempt takes 200ms
    When: Orchestrator checks deadline before second attempt
    Then: Escalates with DEADLINE_EXCEEDED
    """
    # Setup: LLM executor that takes time
    class SlowLLMExecutor(BaseExecutor):
        def __init__(self):
            self.call_count = 0

        def execute(self, capability, context):
            self.call_count += 1
            if self.call_count == 1:
                time.sleep(0.15)  # First call takes 150ms
            raise httpx.TimeoutException("Timeout", request=Mock())

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: SlowLLMExecutor()
    })

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher,
        max_duration_seconds=0.1  # 100ms deadline
    )

    # Execute with SUMMARIZE task (routes to LLM executor)
    result = orchestrator.execute("Summarize long document")

    # Verify deadline escalation
    assert result.success is False
    assert result.metadata["escalation_status"] == EscalationStatus.DEADLINE_EXCEEDED.value
    assert result.metadata["total_duration_ms"] >= 100  # At least 100ms elapsed


# =============================================================================
# Scenario 9: Fallback transparency (metadata verification)
# =============================================================================

def test_fallback_transparency(analyzer):
    """
    Scenario 9: Fallback transparency

    Given: Primary capability fails
    And: Fallback capability succeeds
    When: Orchestrator uses fallback
    Then: Metadata clearly indicates fallback was used
    """
    empty_router = CapabilityRouter(capabilities=[])

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: MockLLMExecutor()
    })

    fallback_config = FallbackConfig(
        fallback_capability="echo",
        require_explicit_fallback=True
    )

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=empty_router,
        dispatcher=dispatcher,
        fallback_config=fallback_config
    )

    # Execute
    result = orchestrator.execute("Unknown task")

    # Verify fallback metadata
    assert result.success is True
    assert result.metadata.get("fallback_used") is True
    assert "fallback_reason" in result.metadata
    assert "NoCapabilityFound" in result.metadata["fallback_reason"]
    assert "execution_id" in result.metadata
    assert "total_attempts" in result.metadata
    assert "total_duration_ms" in result.metadata


# =============================================================================
# Scenario 10: SLA metrics (execution_id, duration, error_chain)
# =============================================================================

def test_sla_metrics(analyzer, router):
    """
    Scenario 10: SLA metrics

    Given: Successful execution with 1 retry
    When: Orchestrator completes execution
    Then: Metadata includes all SLA metrics
    """
    llm_executor = MockLLMExecutor(
        fail_times=1,
        exception=httpx.TimeoutException("Timeout", request=Mock())
    )

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: llm_executor
    })

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher,
        max_duration_seconds=60.0
    )

    # Execute with SUMMARIZE task (routes to LLM executor)
    result = orchestrator.execute("Summarize document")

    # Verify SLA metrics
    assert "execution_id" in result.metadata
    assert isinstance(result.metadata["execution_id"], str)

    assert "total_attempts" in result.metadata
    assert result.metadata["total_attempts"] == 2

    assert "total_duration_ms" in result.metadata
    assert isinstance(result.metadata["total_duration_ms"], int)
    assert result.metadata["total_duration_ms"] >= 0

    # Verify error chain
    assert "error_chain" not in result.metadata  # Success = no error chain in result


def test_sla_metrics_on_escalation(analyzer, router):
    """
    Scenario 10b: SLA metrics on escalation

    Given: Execution escalates after retries
    When: Orchestrator returns escalated result
    Then: Metadata includes error_chain and escalation details
    """
    llm_executor = MockLLMExecutor(
        fail_times=999,
        exception=httpx.TimeoutException("Timeout", request=Mock())
    )

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: llm_executor
    })

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher,
        retry_policy=RetryPolicy(max_attempts=2)
    )

    # Execute with SUMMARIZE task (routes to LLM executor)
    result = orchestrator.execute("Summarize report")

    # Verify escalation SLA metrics
    assert result.success is False

    assert "execution_id" in result.metadata
    assert "total_attempts" in result.metadata
    assert result.metadata["total_attempts"] == 2

    assert "total_duration_ms" in result.metadata

    assert "error_chain" in result.metadata
    assert isinstance(result.metadata["error_chain"], list)
    assert len(result.metadata["error_chain"]) == 2

    assert "escalation_status" in result.metadata
    assert result.metadata["escalation_status"] == EscalationStatus.TIMEOUT_EXHAUSTED.value


# =============================================================================
# Scenario 11: ExecutionContext properties
# =============================================================================

def test_execution_context_properties():
    """
    Scenario 11: ExecutionContext properties

    Given: ExecutionContext with deadline
    When: Checking properties during execution
    Then: Properties return correct values
    """
    deadline = time.time() + 60.0
    ctx = ExecutionContext(deadline=deadline)

    # Initial state
    assert ctx.execution_id is not None
    assert ctx.attempt_number == 1
    assert ctx.completed_attempts == 0  # No attempts yet
    assert len(ctx.error_chain) == 0
    assert ctx.is_deadline_exceeded is False
    assert ctx.elapsed_ms >= 0

    # Simulate attempt execution (completed_attempts incremented BEFORE attempt)
    ctx.completed_attempts += 1

    # Record error (after attempt was made)
    error = ValueError("Test error")
    ctx.record_error(error)

    assert ctx.completed_attempts == 1  # Still 1 (record_error doesn't increment anymore)
    assert ctx.attempt_number == 2  # Next would be attempt 2
    assert len(ctx.error_chain) == 1
    assert "ValueError" in ctx.error_chain[0]
    assert "Attempt 1" in ctx.error_chain[0]  # Error shows attempt number

    # Mark complete
    ctx.mark_complete()

    assert ctx.end_time is not None
    assert ctx.total_duration_ms is not None
    assert ctx.total_duration_ms >= 0


def test_execution_context_deadline_exceeded():
    """
    Scenario 11b: ExecutionContext deadline exceeded
    """
    # Set deadline in the past
    deadline = time.time() - 1.0
    ctx = ExecutionContext(deadline=deadline)

    assert ctx.is_deadline_exceeded is True


# =============================================================================
# Run Instructions
# =============================================================================

"""
To run these tests:

    cd /home/onor/ai_os_final/services/core
    pytest execution/test_retry_orchestrator.py -v

Expected output: 14 passed

These tests verify:
1. Retry behavior for temporary errors
2. Escalation for structural errors
3. Fallback transparency
4. Backoff calculation (exponential + jitter + cap)
5. SLA metrics (execution_id, duration, error_chain)
6. Deadline enforcement

If any test fails → ORCHESTRATOR BROKEN
Do NOT proceed to integration.
"""
