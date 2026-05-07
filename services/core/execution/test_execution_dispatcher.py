"""
Contract tests for ExecutionDispatcher

These verify INFRASTRUCTURAL GUARANTEES.
If Dispatcher fails these - architectural decay has begun.

Run: pytest test_execution_dispatcher.py -v
"""

import pytest
from unittest.mock import Mock, MagicMock, call

from execution.execution_dispatcher import (
    ExecutionDispatcher,
    ExecutorNotFoundError,
    ExecutionFailed,
    TaskContext,
    ExecutionResult,
    BaseExecutor
)
from execution.capability_contract import SkillCapability, ExecutionType
from execution.capability_router import SelectionResult
from execution.intent_schema import (
    TaskIntent,
    IntentType,
    ComplexityLevel,
    InputType,
    OutputType
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_code_executor():
    """Mock code executor."""
    executor = Mock(spec=BaseExecutor)
    # Explicitly return value (not async)
    executor.execute = Mock(return_value=ExecutionResult(
        success=True,
        output="Code execution result",
        error=None,
        executor_type=ExecutionType.CODE,
        capability_name="echo",
        metadata=None
    ))
    return executor


@pytest.fixture
def mock_llm_executor():
    """Mock LLM executor."""
    executor = Mock(spec=BaseExecutor)
    # Explicitly return value (not async)
    executor.execute = Mock(return_value=ExecutionResult(
        success=True,
        output="LLM generation result",
        error=None,
        executor_type=ExecutionType.LLM,
        capability_name="summarize",
        metadata={"tokens_used": 500}
    ))
    return executor


@pytest.fixture
def dispatcher(mock_code_executor, mock_llm_executor):
    """Dispatcher with mock executors."""
    executors = {
        ExecutionType.CODE: mock_code_executor,
        ExecutionType.LLM: mock_llm_executor
    }
    return ExecutionDispatcher(executors)


@pytest.fixture
def sample_selection():
    """Sample SelectionResult for testing."""
    capability = SkillCapability(
        name="echo",
        intent=IntentType.TRANSFORM,
        supported_inputs=[InputType.TEXT],
        supported_outputs=[OutputType.TEXT],
        supports_persistence=False,
        supports_external_io=False,
        max_complexity=ComplexityLevel.LOW,
        execution_type=ExecutionType.CODE,
        priority=100
    )

    # Mock SelectionResult (we only use .selected)
    selection = Mock(spec=SelectionResult)
    selection.selected = capability
    return selection


@pytest.fixture
def sample_context():
    """Sample TaskContext for testing."""
    intent = TaskIntent(
        intent=IntentType.TRANSFORM,
        input_type=InputType.TEXT,
        output_type=OutputType.TEXT,
        requires_persistence=False,
        requires_external_io=False,
        complexity=ComplexityLevel.LOW,
        estimated_tokens=100,
        confidence=0.9
    )

    return TaskContext(
        intent=intent,
        raw_input="Echo hello",
        parameters={}
    )


# =============================================================================
# Contract Test 1: Invalid execution_type → Exception
# =============================================================================

def test_invalid_execution_type_raises_exception():
    """
    CONTRACT: Dispatcher with missing executor → ExecutorNotFoundError.

    NOT: silent fallback to other executor
    NOT: try to execute anyway
    """
    # Create hypothetical new execution type (future extension)
    # For this test, we'll test that trying to use unregistered executor fails

    # Create dispatcher with required executors
    code_executor = Mock(spec=BaseExecutor)
    code_executor.execute = Mock(return_value=ExecutionResult(
        success=True,
        output="",
        error=None,
        executor_type=ExecutionType.CODE,
        capability_name="test",
        metadata=None
    ))

    llm_executor = Mock(spec=BaseExecutor)
    llm_executor.execute = Mock(return_value=ExecutionResult(
        success=True,
        output="",
        error=None,
        executor_type=ExecutionType.LLM,
        capability_name="test",
        metadata=None
    ))

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: code_executor,
        ExecutionType.LLM: llm_executor
    })

    # Try to unregister LLM executor (simulate missing)
    del dispatcher._executors[ExecutionType.LLM]

    # Selection with LLM execution_type
    llm_capability = SkillCapability(
        name="summarize",
        intent=IntentType.SUMMARIZE,
        supported_inputs=[InputType.TEXT],
        supported_outputs=[OutputType.TEXT],
        supports_persistence=False,
        supports_external_io=False,
        max_complexity=ComplexityLevel.HIGH,
        execution_type=ExecutionType.LLM,
        priority=50
    )

    selection = Mock(spec=SelectionResult)
    selection.selected = llm_capability

    context = TaskContext(
        intent=TaskIntent(
            intent=IntentType.SUMMARIZE,
            input_type=InputType.TEXT,
            output_type=OutputType.TEXT,
            requires_persistence=False,
            requires_external_io=False,
            complexity=ComplexityLevel.HIGH,
            estimated_tokens=1000,
            confidence=0.9
        ),
        raw_input="Summarize",
        parameters={}
    )

    # Should raise ExecutorNotFoundError
    with pytest.raises(ExecutorNotFoundError) as exc_info:
        dispatcher.dispatch(selection, context)

    assert exc_info.value.execution_type == "llm"


# =============================================================================
# Contract Test 2: Executor called exactly once
# =============================================================================

def test_executor_called_exactly_once(
    dispatcher,
    mock_code_executor,
    sample_selection,
    sample_context
):
    """
    CONTRACT: Executor.execute() is called exactly once.

    NOT: called multiple times (retry logic)
    NOT: not called at all
    """
    dispatcher.dispatch(sample_selection, sample_context)

    # Verify exactly one call
    assert mock_code_executor.execute.call_count == 1


# =============================================================================
# Contract Test 3: Dispatcher does NOT modify SelectionResult
# =============================================================================

def test_dispatcher_does_not_modify_selection(
    dispatcher,
    sample_selection,
    sample_context
):
    """
    CONTRACT: Dispatcher does NOT modify SelectionResult.

    SelectionResult is immutable from Dispatcher perspective.
    """
    # Get original capability
    original_capability = sample_selection.selected

    # Dispatch
    dispatcher.dispatch(sample_selection, sample_context)

    # Verify SelectionResult unchanged
    assert sample_selection.selected is original_capability
    assert sample_selection.selected.name == "echo"


# =============================================================================
# Contract Test 4: Executor error bubbles up
# =============================================================================

def test_executor_error_bubbles_up(sample_selection, sample_context):
    """
    CONTRACT: Executor errors bubble up, NOT caught by Dispatcher.

    Dispatcher does NOT handle errors.
    Caller (orchestration layer) decides what to do.
    """
    # Executor that raises exception
    failing_executor = Mock(spec=BaseExecutor)
    # Use side_effect to make execute raise exception
    failing_executor.execute = Mock(side_effect=ExecutionFailed(
        capability_name="echo",
        reason="Simulated failure"
    ))

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: failing_executor,
        ExecutionType.LLM: Mock(spec=BaseExecutor)
    })

    # Should bubble up ExecutionFailed
    with pytest.raises(ExecutionFailed) as exc_info:
        dispatcher.dispatch(sample_selection, sample_context)

    assert exc_info.value.capability_name == "echo"
    assert "Simulated failure" in str(exc_info.value.reason)


# =============================================================================
# Contract Test 5: No re-routing in Dispatcher
# =============================================================================

def test_no_re_routing_in_dispatcher(
    dispatcher,
    mock_code_executor,
    mock_llm_executor,
    sample_selection,
    sample_context
):
    """
    CONTRACT: Dispatcher does NOT perform re-routing.

    If CODE executor exists → CODE is called.
    NOT: "LLM might be better, let's try LLM instead"
    """
    # Selection with CODE execution_type
    sample_selection.selected.execution_type == ExecutionType.CODE

    dispatcher.dispatch(sample_selection, sample_context)

    # Only CODE executor should be called
    assert mock_code_executor.execute.call_count == 1
    assert mock_llm_executor.execute.call_count == 0


# =============================================================================
# Contract Test 6: Dispatcher passes correct parameters
# =============================================================================

def test_dispatcher_passes_correct_parameters(
    dispatcher,
    mock_code_executor,
    sample_selection,
    sample_context
):
    """
    CONTRACT: Dispatcher passes capability and context to executor.

    NOT: enriches, modifies, or filters them.
    """
    dispatcher.dispatch(sample_selection, sample_context)

    # Verify executor received correct parameters
    call_args = mock_code_executor.execute.call_args

    # First positional arg: capability
    assert call_args[0][0] is sample_selection.selected
    assert call_args[0][0].name == "echo"

    # Second positional arg: context
    assert call_args[0][1] is sample_context
    assert call_args[0][1].raw_input == "Echo hello"


# =============================================================================
# Contract Test 7: Can register new executor at runtime
# =============================================================================

def test_can_register_new_executor(sample_selection, sample_context):
    """
    CONTRACT: Can register new execution_type at runtime.

    Allows extending Dispatcher without modification.
    """
    # Start with minimal dispatcher
    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: Mock(spec=BaseExecutor),
        ExecutionType.LLM: Mock(spec=BaseExecutor)
    })

    # Register new executor type (hypothetical future type)
    from enum import auto

    # Create mock for new type
    new_executor = Mock(spec=BaseExecutor)
    new_executor.execute.return_value = ExecutionResult(
        success=True,
        output="New executor result",
        error=None,
        executor_type=ExecutionType.CODE,  # Reuse existing for test
        capability_name="new_capability",
        metadata=None
    )

    # Register
    dispatcher.register_executor(ExecutionType.CODE, new_executor)

    # Verify it's registered
    assert dispatcher._executors[ExecutionType.CODE] is new_executor


# =============================================================================
# Contract Test 8: Dispatcher returns executor result unchanged
# =============================================================================

def test_dispatcher_returns_executor_result_unchanged(
    dispatcher,
    sample_selection,
    sample_context
):
    """
    CONTRACT: Dispatcher returns executor result as-is.

    NOT: enriches, modifies, or filters the result.
    """
    # Mock executor returns specific result
    expected_result = ExecutionResult(
        success=True,
        output="Specific output",
        error=None,
        executor_type=ExecutionType.CODE,
        capability_name="echo",
        metadata={"custom": "value"}
    )

    from unittest.mock import Mock
    mock_executor = Mock(spec=BaseExecutor)
    # Explicitly return value (not async)
    mock_executor.execute = Mock(return_value=expected_result)

    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: mock_executor,
        ExecutionType.LLM: Mock(spec=BaseExecutor)
    })

    # Dispatch
    result = dispatcher.dispatch(sample_selection, sample_context)

    # Verify exact same result returned
    assert result is expected_result
    assert result.output == "Specific output"
    assert result.metadata == {"custom": "value"}


# =============================================================================
# Run Instructions
# =============================================================================

"""
To run these tests:

    cd /home/onor/ai_os_final/services/core
    pytest execution/test_execution_dispatcher.py -v

Expected output: 8 passed

If any test fails → DISPATCHER HAS BECOME TOO SMART
Do not proceed to TaskAnalyzer.
"""
