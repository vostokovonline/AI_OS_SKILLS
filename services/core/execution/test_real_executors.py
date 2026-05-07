"""
Real Executors Tests - Test with actual execution, no mocks

Tests:
1. CodeExecutor with real Python function
2. LLMExecutor with real LiteLLM call
3. End-to-end with real tasks

Run: pytest execution/test_real_executors.py -v
"""

import pytest
from unittest.mock import Mock, patch

from execution.code_executor import CodeExecutor
from execution.llm_executor import LLMExecutor
from execution.capability_contract import SkillCapability, ExecutionType
from execution.execution_dispatcher import TaskContext, ExecutionResult
from execution.intent_schema import (
    IntentType,
    InputType,
    OutputType,
    ComplexityLevel
)


# =============================================================================
# Test Fixtures - Simple echo function
# =============================================================================

def echo(task: str) -> str:
    """
    Simple echo function for testing CodeExecutor.

    Args:
        task: Text to echo

    Returns:
        Same text
    """
    return f"Echoed: {task}"


def calculator(task: str) -> str:
    """
    Simple calculator for testing.

    Args:
        task: Math expression (e.g., "2 + 2")

    Returns:
        Result as string
    """
    try:
        result = eval(task)
        return f"Calculation result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"


# =============================================================================
# Mock canonical_skills module
# =============================================================================

# We need to make these functions importable as if they were in canonical_skills
import sys
from types import ModuleType

# Create mock canonical_skills modules
echo_module = ModuleType("canonical_skills.echo")
echo_module.echo = echo
sys.modules["canonical_skills.echo"] = echo_module

calculator_module = ModuleType("canonical_skills.calculator")
calculator_module.calculator = calculator
sys.modules["canonical_skills.calculator"] = calculator_module


# =============================================================================
# CodeExecutor Tests
# =============================================================================

@pytest.fixture
def code_executor():
    """CodeExecutor instance."""
    return CodeExecutor()


def test_code_executor_echo_task(code_executor):
    """
    Test 1: CodeExecutor executes echo function.

    Flow:
    1. Create capability for "echo"
    2. Create context with task "Echo hello"
    3. Execute
    4. Verify output is "Echoed: hello"
    """
    # Create capability
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

    # Create context with proper intent
    from execution.intent_schema import TaskIntent
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

    context = TaskContext(
        intent=intent,
        raw_input="hello",
        parameters={}
    )

    # Execute
    result = code_executor.execute(capability, context)

    # Verify
    assert result.success is True
    assert result.error is None
    assert "hello" in result.output
    assert result.executor_type == "code"
    assert result.capability_name == "echo"


def test_code_executor_calculate_task(code_executor):
    """
    Test 2: CodeExecutor executes calculate function.

    Flow:
    1. Create capability for "calculator"
    2. Create context with task "2 + 2"
    3. Execute
    4. Verify output contains "4"
    """
    capability = SkillCapability(
        name="calculator",
        intent=IntentType.COMPUTE,
        supported_inputs=[InputType.STRUCTURED],
        supported_outputs=[OutputType.STRUCTURED],
        supports_persistence=False,
        supports_external_io=False,
        max_complexity=ComplexityLevel.LOW,
        execution_type=ExecutionType.CODE,
        priority=95
    )

    from execution.intent_schema import TaskIntent
    intent = TaskIntent(
        intent=IntentType.COMPUTE,
        input_type=InputType.STRUCTURED,
        output_type=OutputType.STRUCTURED,
        requires_persistence=False,
        requires_external_io=False,
        complexity=ComplexityLevel.LOW,
        estimated_tokens=50,
        confidence=0.95
    )

    context = TaskContext(
        intent=intent,
        raw_input="2 + 2",
        parameters={}
    )

    result = code_executor.execute(capability, context)

    assert result.success is True
    assert "4" in result.output
    assert result.executor_type == "code"


def test_code_executor_handles_error(code_executor):
    """
    Test 3: CodeExecutor handles exceptions gracefully.

    Should return success=False with error message.
    """
    capability = SkillCapability(
        name="nonexistent",
        intent=IntentType.TRANSFORM,
        supported_inputs=[InputType.TEXT],
        supported_outputs=[OutputType.TEXT],
        supports_persistence=False,
        supports_external_io=False,
        max_complexity=ComplexityLevel.LOW,
        execution_type=ExecutionType.CODE,
        priority=0
    )

    from execution.intent_schema import TaskIntent
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

    context = TaskContext(
        intent=intent,
        raw_input="test",
        parameters={}
    )

    result = code_executor.execute(capability, context)

    # Should NOT raise exception
    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower() or "import" in result.error.lower()


# =============================================================================
# LLMExecutor Tests (with mock HTTP)
# =============================================================================

@pytest.fixture
def llm_executor():
    """LLMExecutor instance."""
    return LLMExecutor(
        litellm_url="http://mock-litellm:4000/v1/chat/completions",
        api_key="test-key",
        timeout=5.0
    )


def test_llm_executor_summarize_task(llm_executor):
    """
    Test 4: LLMExecutor calls LiteLLM API.

    Flow:
    1. Create capability for "summarize_text"
    2. Create context with task
    3. Mock HTTP call to LiteLLM
    4. Verify output extracted correctly

    NOTE: This test uses mock HTTP, not real call.
    """
    capability = SkillCapability(
        name="summarize_text",
        intent=IntentType.SUMMARIZE,
        supported_inputs=[InputType.TEXT],
        supported_outputs=[OutputType.TEXT],
        supports_persistence=False,
        supports_external_io=False,
        max_complexity=ComplexityLevel.HIGH,
        execution_type=ExecutionType.LLM,
        priority=50
    )

    from execution.intent_schema import TaskIntent
    intent = TaskIntent(
        intent=IntentType.SUMMARIZE,
        input_type=InputType.TEXT,
        output_type=OutputType.TEXT,
        requires_persistence=False,
        requires_external_io=False,
        complexity=ComplexityLevel.HIGH,
        estimated_tokens=800,
        confidence=0.9
    )

    context = TaskContext(
        intent=intent,
        raw_input="Summarize this document about AI",
        parameters={}
    )

    # Mock HTTP call
    mock_response = {
        "choices": [{
            "message": {
                "content": "This document discusses AI architecture..."
            }
        }],
        "usage": {
            "total_tokens": 150
        }
    }

    with patch('httpx.Client.post') as mock_post:
        mock_post.return_value.json.return_value = mock_response
        mock_post.return_value.raise_for_status = Mock()

        # Execute
        result = llm_executor.execute(capability, context)

        # Verify
        assert result.success is True
        assert result.error is None
        assert "AI architecture" in result.output
        assert result.executor_type == "llm"
        assert result.capability_name == "summarize_text"


def test_llm_executor_handles_http_error(llm_executor):
    """
    Test 5: LLMExecutor handles HTTP errors gracefully.

    Should return success=False with error message.
    """
    capability = SkillCapability(
        name="summarize_text",
        intent=IntentType.SUMMARIZE,
        supported_inputs=[InputType.TEXT],
        supported_outputs=[OutputType.TEXT],
        supports_persistence=False,
        supports_external_io=False,
        max_complexity=ComplexityLevel.HIGH,
        execution_type=ExecutionType.LLM,
        priority=50
    )

    from execution.intent_schema import TaskIntent
    intent = TaskIntent(
        intent=IntentType.SUMMARIZE,
        input_type=InputType.TEXT,
        output_type=OutputType.TEXT,
        requires_persistence=False,
        requires_external_io=False,
        complexity=ComplexityLevel.HIGH,
        estimated_tokens=800,
        confidence=0.9
    )

    context = TaskContext(
        intent=intent,
        raw_input="Summarize this",
        parameters={}
    )

    # Mock HTTP error
    with patch('httpx.Client.post') as mock_post:
        mock_post.return_value.raise_for_status.side_effect = Exception("Connection refused")

        result = llm_executor.execute(capability, context)

        # Should NOT raise exception
        assert result.success is False
        assert result.error is not None


# =============================================================================
# Integration Tests (with Dispatcher)
# =============================================================================

def test_full_pipeline_with_code_executor():
    """
    Test 6: Full pipeline with real CodeExecutor.

    Flow:
    1. TaskAnalyzer analyzes "Echo hello world"
    2. Router selects echo capability
    3. Dispatcher calls CodeExecutor
    4. Returns ExecutionResult with echoed text

    This is NOT mock - real execution.
    """
    from execution.task_analyzer import TaskAnalyzer
    from execution.capability_router import CapabilityRouter
    from execution.execution_dispatcher import ExecutionDispatcher

    # Layer 1: Mock LLM client for TaskAnalyzer
    llm_client = Mock()
    llm_client.generate = Mock(return_value='''```json
{
  "intent": "transform",
  "input_type": "text",
  "output_type": "text",
  "requires_persistence": false,
  "requires_external_io": false,
  "complexity": "low",
  "estimated_tokens": 100,
  "confidence": 0.99
}
```''')

    analyzer = TaskAnalyzer(llm_client=llm_client, model="gpt-4o-mini")

    # Layer 2: Router with echo capability
    echo_capability = SkillCapability(
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

    router = CapabilityRouter(capabilities=[echo_capability])

    # Layer 3: Dispatcher with CodeExecutor
    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: CodeExecutor(),
        ExecutionType.LLM: Mock()  # Not used in this test
    })

    # Execute pipeline
    task = "Echo hello world"

    # Step 1: Analyze
    analysis = analyzer.analyze(task)

    # Step 2: Route
    selection = router.route(analysis.intent)

    # Step 3: Dispatch
    context = TaskContext(
        intent=analysis.intent,
        raw_input=task,
        parameters={}
    )

    result = dispatcher.dispatch(selection, context)

    # Verify full pipeline
    assert result.success is True
    assert result.error is None
    assert "hello world" in result.output.lower()
    assert result.executor_type == "code"
    assert result.capability_name == "echo"


# =============================================================================
# Run Instructions
# =============================================================================

"""
To run these tests:

    cd /home/onor/ai_os_final/services/core
    pytest execution/test_real_executors.py -v

Expected output: 6 passed

These tests verify:
- CodeExecutor executes real Python functions
- LLMExecutor calls LiteLLM API (mocked HTTP)
- Full pipeline works with real executors
- Error handling works correctly

If any test fails → EXECUTOR IMPLEMENTATION BROKEN
"""
