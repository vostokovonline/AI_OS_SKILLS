"""
Idempotency Tests - Verify retry/fallback safety

These tests verify CRITICAL safety guarantees:
- Non-idempotent skills do NOT retry
- LLM executor CAN retry (no side effects)
- Fallback does NOT create duplicate side effects

Run: pytest execution/test_idempotency.py -v
"""

import pytest
from unittest.mock import Mock
from uuid import uuid4

import httpx

from execution.retry_orchestrator import (
    RetryOrchestrator,
    RetryPolicy,
    FallbackConfig,
    ExecutionContext,
    EscalationStatus
)
from execution.task_analyzer import TaskAnalyzer
from execution.capability_router import CapabilityRouter, NoCapabilityFound
from execution.execution_dispatcher import (
    ExecutionDispatcher,
    BaseExecutor,
    TaskContext,
    ExecutionResult
)
from execution.capability_contract import (
    SkillCapability,
    ExecutionType
)
from execution.intent_schema import (
    TaskIntent,
    IntentType,
    InputType,
    OutputType,
    ComplexityLevel
)
from execution.idempotency import IdempotencyLevel


# =============================================================================
# Mock Executors
# =============================================================================

class MockLLMExecutor(BaseExecutor):
    """Mock LLM executor that can simulate failures."""

    def __init__(self, fail_times: int = 0, exception: Exception = None):
        self.fail_times = fail_times
        self.exception = exception
        self.call_count = 0

    def execute(self, capability, context):
        self.call_count += 1

        if self.call_count <= self.fail_times:
            # Fail before any side effect (LLM has no side effects anyway)
            raise self.exception

        return ExecutionResult(
            success=True,
            side_effect_committed=False,  # LLM has no external side effects
            output=f"[LLM] Success after {self.call_count} attempts",
            error=None,
            executor_type=ExecutionType.LLM,
            capability_name=capability.name,
            metadata={"executor": "mock_llm", "tokens_used": 100}
        )


class MockNonIdempotentExecutor(BaseExecutor):
    """
    Mock executor for non-idempotent skill (e.g., write_file).

    Tracks call count to detect duplicate executions.
    """

    def __init__(self):
        self.call_count = 0
        self.side_effects = []  # Track created resources

    def execute(self, capability, context):
        self.call_count += 1

        # Simulate side effect (e.g., creating file)
        resource_id = f"resource_{self.call_count}_{uuid4()}"
        self.side_effects.append(resource_id)

        if self.call_count == 1:
            # First call succeeds - side effect WAS committed
            return ExecutionResult(
                success=True,
                side_effect_committed=True,  # File was created
                output=f"Created {resource_id}",
                error=None,
                executor_type=ExecutionType.CODE,
                capability_name=capability.name,
                metadata={"resource_id": resource_id}
            )

        # Subsequent calls would create duplicates
        raise RuntimeError(f"Duplicate execution would create {resource_id}")


class FailingNonIdempotentExecutor(BaseExecutor):
    """
    Mock executor that fails with timeout (retryable error).

    Used to test that non-idempotent skills don't retry even on retryable errors.

    Fails AFTER side effect tracking (resource_id added to side_effects).
    """

    def __init__(self):
        self.call_count = 0
        self.side_effects = []  # Track created resources

    def execute(self, capability, context):
        self.call_count += 1

        # Simulate side effect (e.g., creating file)
        resource_id = f"resource_{self.call_count}_{uuid4()}"
        self.side_effects.append(resource_id)

        # Fail with timeout AFTER side effect tracking
        # Fail closed: Consider side effect as committed (might have been created)
        raise httpx.TimeoutException("Write timeout", request=Mock())


class MockSafeExecutor(BaseExecutor):
    """Mock executor for SAFE skill (no side effects)."""

    def __init__(self):
        self.call_count = 0

    def execute(self, capability, context):
        self.call_count += 1
        return ExecutionResult(
            success=True,
            side_effect_committed=False,  # No side effects
            output=f"[SAFE] Result {self.call_count}",
            error=None,
            executor_type=ExecutionType.CODE,
            capability_name=capability.name,
            metadata={"executor": "mock_safe"}
        )


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_client():
    client = Mock()

    def mock_generate(prompt, temperature, model):
        task = prompt.split('"')[1] if '"' in prompt else prompt
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
    return TaskAnalyzer(llm_client=mock_llm_client, model="gpt-4o-mini")


@pytest.fixture
def router():
    capabilities = [
        SkillCapability(
            name="safe_skill",
            intent=IntentType.TRANSFORM,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=100,
            idempotency=IdempotencyLevel.SAFE
        ),
        SkillCapability(
            name="non_idempotent_skill",
            intent=IntentType.STORE,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.FILE],
            supports_persistence=True,
            supports_external_io=True,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=90,
            idempotency=IdempotencyLevel.NON_IDEMPOTENT
        ),
    ]
    return CapabilityRouter(capabilities=capabilities)


@pytest.fixture
def dispatcher():
    return ExecutionDispatcher({
        ExecutionType.CODE: MockSafeExecutor(),
        ExecutionType.LLM: MockLLMExecutor()
    })


@pytest.fixture
def orchestrator(analyzer, router, dispatcher):
    return RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher,
        retry_policy=RetryPolicy(max_attempts=3)
    )


# =============================================================================
# Test 1: Non-idempotent does NOT retry
# =============================================================================

def test_non_idempotent_no_retry():
    """
    CRITICAL TEST: Non-idempotent skills do NOT retry.

    Given: write_file capability (NON_IDEMPOTENT)
    And: Executor throws timeout on first attempt
    When: Orchestrator considers retry
    Then: Escalates immediately WITHOUT retry

    This prevents duplicate file creation, duplicate API calls, etc.
    """
    # Setup: non-idempotent executor that fails with timeout
    non_idempotent_executor = FailingNonIdempotentExecutor()

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: non_idempotent_executor,
        ExecutionType.LLM: MockLLMExecutor()
    })

    # Router with NON_IDEMPOTENT capability
    router = CapabilityRouter(capabilities=[
        SkillCapability(
            name="write_file",
            intent=IntentType.STORE,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.FILE],
            supports_persistence=True,
            supports_external_io=True,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=90,
            idempotency=IdempotencyLevel.NON_IDEMPOTENT
        ),
    ])

    # Create proper TaskIntent (not Mock)
    analyzer = Mock()
    analysis = Mock()
    analysis.intent = TaskIntent(
        intent=IntentType.STORE,
        input_type=InputType.TEXT,
        output_type=OutputType.FILE,
        requires_persistence=True,
        requires_external_io=True,
        complexity=ComplexityLevel.LOW,
        estimated_tokens=100,
        confidence=0.95
    )

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher,
        retry_policy=RetryPolicy(max_attempts=3)
    )

    # Mock analyzer and routing
    analyzer.analyze = Mock(return_value=analysis)
    router.route = Mock(return_value=Mock(selected=router.capabilities[0]))

    # Execute
    result = orchestrator.execute("Write file content")

    # Verify: Only 1 attempt made (NO retry)
    assert non_idempotent_executor.call_count == 1
    assert result.success is False
    assert result.metadata["escalation_status"] == EscalationStatus.STRUCTURAL_ERROR.value
    assert result.metadata["total_attempts"] == 1

    # Verify: Only 1 side effect (no duplicates)
    assert len(non_idempotent_executor.side_effects) == 1


# =============================================================================
# Test 2: LLM executor CAN retry (logically SAFE)
# =============================================================================

def test_llm_executor_retries():
    """
    CRITICAL TEST: LLM executor CAN retry.

    Given: LLM capability (SAFE - no external side effects)
    And: LLM times out on first attempt
    When: Orchestrator retries
    Then: Second attempt succeeds

    LLM generation has no external side effects, so retry is safe.
    """
    llm_executor = MockLLMExecutor(
        fail_times=1,
        exception=httpx.TimeoutException("Request timeout", request=Mock())
    )

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockSafeExecutor(),
        ExecutionType.LLM: llm_executor
    })

    router = CapabilityRouter(capabilities=[
        SkillCapability(
            name="summarize_text",
            intent=IntentType.SUMMARIZE,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.HIGH,
            execution_type=ExecutionType.LLM,
            priority=50,
            idempotency=IdempotencyLevel.SAFE  # LLM is SAFE
        ),
    ])

    # Create proper TaskIntent (not Mock)
    analyzer = Mock()
    analysis = Mock()
    analysis.intent = TaskIntent(
        intent=IntentType.SUMMARIZE,
        input_type=InputType.TEXT,
        output_type=OutputType.TEXT,
        requires_persistence=False,
        requires_external_io=False,
        complexity=ComplexityLevel.HIGH,
        estimated_tokens=100,
        confidence=0.95
    )

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher,
        retry_policy=RetryPolicy(max_attempts=3)
    )

    analyzer.analyze = Mock(return_value=analysis)
    router.route = Mock(return_value=Mock(selected=router.capabilities[0]))

    # Execute
    result = orchestrator.execute("Summarize document")

    # Verify: Retry happened
    assert result.success is True
    assert llm_executor.call_count == 2  # Failed once, succeeded on retry
    assert result.metadata["total_attempts"] == 2


# =============================================================================
# Test 3: Fallback does NOT create duplicates
# =============================================================================

def test_fallback_no_duplicates():
    """
    CRITICAL TEST: Fallback does NOT create duplicate side effects.

    Given: Primary capability is write_file (NON_IDEMPOTENT)
    And: Primary fails with timeout DURING execution
    When: Orchestrator considers fallback
    Then: NO fallback (prevents duplicate files)

    Fallback is only safe if:
    - Primary was NOT executed (error before executor)
    - OR primary is retry_safe/idempotent
    """
    # Primary executor that times out
    class WriteFileExecutor(BaseExecutor):
        def __init__(self):
            self.call_count = 0

        def execute(self, capability, context):
            self.call_count += 1
            # Simulate timeout during file creation
            raise httpx.TimeoutException("Write timeout", request=Mock())

    primary_executor = WriteFileExecutor()

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: primary_executor,
        ExecutionType.LLM: MockLLMExecutor()
    })

    # Non-idempotent primary capability
    router = CapabilityRouter(capabilities=[
        SkillCapability(
            name="write_file",
            intent=IntentType.STORE,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.FILE],
            supports_persistence=True,
            supports_external_io=True,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=90,
            idempotency=IdempotencyLevel.NON_IDEMPOTENT
        ),
    ])

    # Create proper TaskIntent (not Mock)
    analyzer = Mock()
    analysis = Mock()
    analysis.intent = TaskIntent(
        intent=IntentType.STORE,
        input_type=InputType.TEXT,
        output_type=OutputType.FILE,
        requires_persistence=True,
        requires_external_io=True,
        complexity=ComplexityLevel.LOW,
        estimated_tokens=100,
        confidence=0.95
    )

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher,
        fallback_config=FallbackConfig(fallback_capability="safe_fallback"),
        retry_policy=RetryPolicy(max_attempts=3)
    )

    analyzer.analyze = Mock(return_value=analysis)
    router.route = Mock(return_value=Mock(selected=router.capabilities[0]))

    # Execute
    result = orchestrator.execute("Write file content")

    # Verify: Primary was attempted
    assert primary_executor.call_count == 1

    # Verify: Fallback was NOT attempted (prevents duplicates)
    assert result.success is False
    assert result.metadata.get("fallback_used") is not True  # No fallback happened
    assert result.metadata["escalation_status"] == EscalationStatus.STRUCTURAL_ERROR.value
    assert result.metadata["total_attempts"] == 1


# =============================================================================
# Test 4: First attempt ALWAYS executes
# =============================================================================

def test_first_attempt_always_executes():
    """
    Verify: First attempt ALWAYS executes, regardless of idempotency.

    Given: Non-idempotent capability
    When: First execution attempt
    Then: Executor is called

    Only RETRY is blocked by idempotency, not first attempt.
    """
    non_idempotent_executor = MockNonIdempotentExecutor()

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: non_idempotent_executor,
        ExecutionType.LLM: MockLLMExecutor()
    })

    router = CapabilityRouter(capabilities=[
        SkillCapability(
            name="write_file",
            intent=IntentType.STORE,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.FILE],
            supports_persistence=True,
            supports_external_io=True,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=90,
            idempotency=IdempotencyLevel.NON_IDEMPOTENT
        ),
    ])

    # Create proper TaskIntent (not Mock)
    analyzer = Mock()
    analysis = Mock()
    analysis.intent = TaskIntent(
        intent=IntentType.STORE,
        input_type=InputType.TEXT,
        output_type=OutputType.FILE,
        requires_persistence=True,
        requires_external_io=True,
        complexity=ComplexityLevel.LOW,
        estimated_tokens=100,
        confidence=0.95
    )

    orchestrator = RetryOrchestrator(
        analyzer=analyzer,
        router=router,
        dispatcher=dispatcher,
        retry_policy=RetryPolicy(max_attempts=3)
    )

    analyzer.analyze = Mock(return_value=analysis)
    router.route = Mock(return_value=Mock(selected=router.capabilities[0]))

    # Execute (first attempt succeeds)
    result = orchestrator.execute("Write file content")

    # Verify: First attempt executed
    assert result.success is True
    assert non_idempotent_executor.call_count == 1
    assert len(non_idempotent_executor.side_effects) == 1


# =============================================================================
# Run Instructions
# =============================================================================

"""
To run these tests:

    cd /home/onor/ai_os_final/services/core
    pytest execution/test_idempotency.py -v

Expected output: 4 passed

These tests verify CRITICAL safety:
1. Non-idempotent skills do NOT retry
2. LLM executor CAN retry (logically SAFE)
3. Fallback prevents duplicate side effects
4. First attempt ALWAYS executes

If any test fails → IDEMPOTENCY CONTRACT BROKEN
DO NOT integrate with goal system.
"""
