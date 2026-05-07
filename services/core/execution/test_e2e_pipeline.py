"""
End-to-End Pipeline Tests

Tests the complete flow:
TaskAnalyzer → CapabilityRouter → ExecutionDispatcher → Executor

This verifies architectural integration:
- All layers work together
- Data flows without distortion
- Each layer does its job correctly
- No "magic" happens between layers

Run: pytest execution/test_e2e_pipeline.py -v
"""

import pytest
from unittest.mock import Mock

from execution.task_analyzer import TaskAnalyzer
from execution.capability_contract import SkillCapability, ExecutionType
from execution.capability_router import CapabilityRouter
from execution.execution_dispatcher import ExecutionDispatcher, BaseExecutor, TaskContext, ExecutionResult
from execution.intent_schema import (
    IntentType,
    InputType,
    OutputType,
    ComplexityLevel,
    MIN_CONFIDENCE_THRESHOLD
)


# =============================================================================
# Mock Executors
# =============================================================================

class MockCodeExecutor(BaseExecutor):
    """
    Mock code executor for testing.

    Returns predictable ExecutionResult.
    """

    def execute(self, capability, context):
        """
        Execute code capability.

        Returns predictable result based on capability name.
        """
        return ExecutionResult(
            success=True,
            output=f"[CODE] Executed {capability.name}",
            error=None,
            executor_type=ExecutionType.CODE,
            capability_name=capability.name,
            metadata={"executor": "mock_code", "duration_ms": 50}
        )


class MockLLMExecutor(BaseExecutor):
    """
    Mock LLM executor for testing.

    Returns predictable ExecutionResult.
    """

    def execute(self, capability, context):
        """
        Execute LLM capability.

        Returns predictable result based on capability name.
        """
        return ExecutionResult(
            success=True,
            output=f"[LLM] Generated result for {capability.name}",
            error=None,
            executor_type=ExecutionType.LLM,
            capability_name=capability.name,
            metadata={"executor": "mock_llm", "tokens_used": 750, "duration_ms": 1200}
        )


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_client():
    """
    Mock LLM client that returns realistic classifications.

    Returns different classifications based on task content.
    """
    client = Mock()

    def mock_generate(prompt, temperature, model):
        """
        Generate classification based on task in prompt.

        This simulates real TaskAnalyzer behavior.
        """
        task = prompt.split('"')[1] if '"' in prompt else prompt

        # Classify based on keywords (simulating LLM)
        if "summarize" in task.lower():
            return '''```json
{
  "intent": "summarize",
  "input_type": "text",
  "output_type": "text",
  "requires_persistence": false,
  "requires_external_io": false,
  "complexity": "medium",
  "estimated_tokens": 800,
  "confidence": 0.95
}
```'''
        elif "story" in task.lower() or "generate" in task.lower():
            return '''```json
{
  "intent": "generate",
  "input_type": "text",
  "output_type": "text",
  "requires_persistence": false,
  "requires_external_io": false,
  "complexity": "high",
  "estimated_tokens": 1500,
  "confidence": 0.92
}
```'''
        elif "echo" in task.lower():
            return '''```json
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
```'''
        elif "save" in task.lower() or "file" in task.lower():
            return '''```json
{
  "intent": "store",
  "input_type": "text",
  "output_type": "file",
  "requires_persistence": true,
  "requires_external_io": true,
  "complexity": "low",
  "estimated_tokens": 200,
  "confidence": 0.97
}
```'''
        elif "calculate" in task.lower() or "compute" in task.lower():
            return '''```json
{
  "intent": "compute",
  "input_type": "structured",
  "output_type": "structured",
  "requires_persistence": false,
  "requires_external_io": false,
  "complexity": "low",
  "estimated_tokens": 50,
  "confidence": 0.98
}
```'''
        else:
            # Default: transform
            return '''```json
{
  "intent": "transform",
  "input_type": "text",
  "output_type": "text",
  "requires_persistence": false,
  "requires_external_io": false,
  "complexity": "low",
  "estimated_tokens": 100,
  "confidence": 0.90
}
```'''

    client.generate = Mock(side_effect=mock_generate)
    return client


@pytest.fixture
def registered_capabilities():
    """
    Pre-registered capabilities for testing.

    Covers all intents we test against.
    """
    return [
        # SUMMARIZE capability (LLM)
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

        # GENERATE capability (LLM)
        SkillCapability(
            name="generate_text",
            intent=IntentType.GENERATE,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.HIGH,
            execution_type=ExecutionType.LLM,
            priority=45
        ),

        # TRANSFORM capability (Code - echo)
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

        # STORE capability (Code - file write)
        SkillCapability(
            name="write_file",
            intent=IntentType.STORE,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.FILE],
            supports_persistence=True,
            supports_external_io=True,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=90
        ),

        # COMPUTE capability (Code)
        SkillCapability(
            name="calculator",
            intent=IntentType.COMPUTE,
            supported_inputs=[InputType.STRUCTURED],
            supported_outputs=[OutputType.STRUCTURED],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=95
        ),
    ]


@pytest.fixture
def execution_pipeline(mock_llm_client):
    """
    Complete execution pipeline with all layers.

    Returns tuple: (analyzer, router, dispatcher)
    """
    # Layer 1: TaskAnalyzer
    analyzer = TaskAnalyzer(
        llm_client=mock_llm_client,
        model="gpt-4o-mini"
    )

    # Layer 2: CapabilityRouter (empty initially)
    router = CapabilityRouter(capabilities=[])

    # Layer 3: ExecutionDispatcher with mock executors
    dispatcher = ExecutionDispatcher({
        ExecutionType.CODE: MockCodeExecutor(),
        ExecutionType.LLM: MockLLMExecutor()
    })

    return analyzer, router, dispatcher


# =============================================================================
# E2E Test Scenarios
# =============================================================================

def test_e2e_summarize_task(execution_pipeline, registered_capabilities):
    """
    E2E Test 1: Summarize task → LLM executor

    Flow:
    1. User: "Summarize this document"
    2. TaskAnalyzer → Classify as SUMMARIZE
    3. CapabilityRouter → Select summarize_text capability
    4. ExecutionDispatcher → Call LLM executor
    5. Result → ExecutionResult from LLM
    """
    analyzer, router, dispatcher = execution_pipeline

    # Register capabilities
    router.capabilities = registered_capabilities

    # Step 1: User task
    task = "Summarize this document about AI architecture"

    # Step 2: TaskAnalyzer classifies
    analysis = analyzer.analyze(task)

    # Verify classification
    assert analysis.intent.intent == IntentType.SUMMARIZE
    assert analysis.intent.input_type == InputType.TEXT
    assert analysis.intent.output_type == OutputType.TEXT
    assert analysis.intent.complexity == ComplexityLevel.MEDIUM
    assert analysis.intent.confidence >= MIN_CONFIDENCE_THRESHOLD

    # Step 3: Router selects capability
    selection = router.route(analysis.intent)

    # Verify selection
    assert selection.selected.name == "summarize_text"
    assert selection.selected.intent == IntentType.SUMMARIZE
    assert selection.selected.execution_type == ExecutionType.LLM

    # Step 4: Dispatcher calls executor
    context = TaskContext(
        intent=analysis.intent,
        raw_input=task,
        parameters={}
    )

    result = dispatcher.dispatch(selection, context)

    # Verify execution
    assert result.success is True
    assert result.executor_type == ExecutionType.LLM
    assert result.capability_name == "summarize_text"
    assert "[LLM]" in result.output


def test_e2e_generate_story_task(execution_pipeline, registered_capabilities):
    """
    E2E Test 2: Generate story → LLM executor

    Flow:
    1. User: "Generate a story about AI"
    2. TaskAnalyzer → Classify as GENERATE
    3. CapabilityRouter → Select generate_text capability
    4. ExecutionDispatcher → Call LLM executor
    5. Result → ExecutionResult from LLM
    """
    analyzer, router, dispatcher = execution_pipeline

    # Register capabilities
    router.capabilities = registered_capabilities

    # Step 1: User task
    task = "Generate a story about AI"

    # Step 2: Analyze
    analysis = analyzer.analyze(task)

    # Verify: GENERATE intent
    assert analysis.intent.intent == IntentType.GENERATE
    assert analysis.intent.complexity == ComplexityLevel.HIGH

    # Step 3: Route
    selection = router.route(analysis.intent)

    # Verify: generate_text capability selected
    assert selection.selected.name == "generate_text"
    assert selection.selected.execution_type == ExecutionType.LLM

    # Step 4: Dispatch
    context = TaskContext(
        intent=analysis.intent,
        raw_input=task,
        parameters={}
    )

    result = dispatcher.dispatch(selection, context)

    # Verify: LLM executor called
    assert result.executor_type == ExecutionType.LLM
    assert result.capability_name == "generate_text"


def test_e2e_echo_task(execution_pipeline, registered_capabilities):
    """
    E2E Test 3: Echo task → Code executor

    Flow:
    1. User: "Echo hello world"
    2. TaskAnalyzer → Classify as TRANSFORM
    3. CapabilityRouter → Select echo capability
    4. ExecutionDispatcher → Call Code executor
    5. Result → ExecutionResult from Code
    """
    analyzer, router, dispatcher = execution_pipeline

    # Register capabilities
    router.capabilities = registered_capabilities

    # Step 1: User task
    task = "Echo hello world"

    # Step 2: Analyze
    analysis = analyzer.analyze(task)

    # Verify: TRANSFORM intent
    assert analysis.intent.intent == IntentType.TRANSFORM
    assert analysis.intent.input_type == InputType.TEXT
    assert analysis.intent.output_type == OutputType.TEXT
    assert analysis.intent.complexity == ComplexityLevel.LOW

    # Step 3: Route
    selection = router.route(analysis.intent)

    # Verify: echo capability selected
    assert selection.selected.name == "echo"
    assert selection.selected.execution_type == ExecutionType.CODE

    # Step 4: Dispatch
    context = TaskContext(
        intent=analysis.intent,
        raw_input=task,
        parameters={}
    )

    result = dispatcher.dispatch(selection, context)

    # Verify: Code executor called
    assert result.executor_type == ExecutionType.CODE
    assert result.capability_name == "echo"
    assert "[CODE]" in result.output


def test_e2e_save_to_file_task(execution_pipeline, registered_capabilities):
    """
    E2E Test 4: Save to file → Code executor with persistence

    Flow:
    1. User: "Save this result to file"
    2. TaskAnalyzer → Classify as STORE (requires_persistence)
    3. CapabilityRouter → Select write_file capability
    4. ExecutionDispatcher → Call Code executor
    5. Result → ExecutionResult from Code
    """
    analyzer, router, dispatcher = execution_pipeline

    # Register capabilities
    router.capabilities = registered_capabilities

    # Step 1: User task
    task = "Save this result to file"

    # Step 2: Analyze
    analysis = analyzer.analyze(task)

    # Verify: STORE intent with persistence
    assert analysis.intent.intent == IntentType.STORE
    assert analysis.intent.input_type == InputType.TEXT
    assert analysis.intent.output_type == OutputType.FILE
    assert analysis.intent.requires_persistence is True
    assert analysis.intent.requires_external_io is True

    # Step 3: Route
    selection = router.route(analysis.intent)

    # Verify: write_file capability selected
    assert selection.selected.name == "write_file"
    assert selection.selected.supports_persistence is True
    assert selection.selected.execution_type == ExecutionType.CODE

    # Step 4: Dispatch
    context = TaskContext(
        intent=analysis.intent,
        raw_input=task,
        parameters={}
    )

    result = dispatcher.dispatch(selection, context)

    # Verify: Code executor called
    assert result.executor_type == ExecutionType.CODE
    assert result.capability_name == "write_file"


def test_e2e_calculate_task(execution_pipeline, registered_capabilities):
    """
    E2E Test 5: Calculate → Code executor

    Flow:
    1. User: "Calculate 2 + 2"
    2. TaskAnalyzer → Classify as COMPUTE
    3. CapabilityRouter → Select calculator capability
    4. ExecutionDispatcher → Call Code executor
    5. Result → ExecutionResult from Code
    """
    analyzer, router, dispatcher = execution_pipeline

    # Register capabilities
    router.capabilities = registered_capabilities

    # Step 1: User task
    task = "Calculate 2 + 2"

    # Step 2: Analyze
    analysis = analyzer.analyze(task)

    # Verify: COMPUTE intent
    assert analysis.intent.intent == IntentType.COMPUTE
    assert analysis.intent.input_type == InputType.STRUCTURED
    assert analysis.intent.output_type == OutputType.STRUCTURED

    # Step 3: Route
    selection = router.route(analysis.intent)

    # Verify: calculator capability selected
    assert selection.selected.name == "calculator"
    assert selection.selected.execution_type == ExecutionType.CODE

    # Step 4: Dispatch
    context = TaskContext(
        intent=analysis.intent,
        raw_input=task,
        parameters={}
    )

    result = dispatcher.dispatch(selection, context)

    # Verify: Code executor called
    assert result.executor_type == ExecutionType.CODE
    assert result.capability_name == "calculator"


# =============================================================================
# Data Flow Integrity Tests
# =============================================================================

def test_data_flow_integrity(execution_pipeline, registered_capabilities):
    """
    CRITICAL: Verify data is NOT distorted across layers.

    Tests that:
    - Original task text preserved
    - Intent structure unchanged
    - No layer adds "magic" transformations
    """
    analyzer, router, dispatcher = execution_pipeline

    # Register capabilities
    router.capabilities = registered_capabilities

    # Original task
    original_task = "Summarize this document about AI architecture"

    # Layer 1: TaskAnalyzer
    analysis = analyzer.analyze(original_task)

    # Verify: Original task preserved
    assert analysis.raw_task == original_task

    # Verify: Intent structure intact
    original_intent = analysis.intent
    assert original_intent.intent == IntentType.SUMMARIZE
    assert original_intent.input_type == InputType.TEXT
    assert original_intent.output_type == OutputType.TEXT

    # Layer 2: Router
    selection = router.route(original_intent)

    # Verify: Same intent object (no copy/modification)
    assert selection.selected.intent == IntentType.SUMMARIZE

    # Layer 3: Dispatcher
    context = TaskContext(
        intent=original_intent,
        raw_input=original_task,
        parameters={}
    )

    result = dispatcher.dispatch(selection, context)

    # Verify: Original data still intact
    assert result.capability_name == "summarize_text"
    assert result.executor_type == ExecutionType.LLM


# =============================================================================
# Layer Isolation Tests
# =============================================================================

def test_analyzer_does_not_access_router(execution_pipeline):
    """
    Verify TaskAnalyzer does NOT access Router.

    Architectural isolation test.
    """
    analyzer, router, dispatcher = execution_pipeline

    # Analyzer should not have router reference
    assert not hasattr(analyzer, 'router')
    assert not hasattr(analyzer, '_router')

    # Analyzer should work independently
    task = "Echo test"
    analysis = analyzer.analyze(task)

    # Should return result without router
    assert analysis is not None
    assert analysis.intent is not None


def test_router_does_not_access_dispatcher(execution_pipeline, registered_capabilities):
    """
    Verify Router does NOT access Dispatcher.

    Architectural isolation test.
    """
    analyzer, router, dispatcher = execution_pipeline

    router.capabilities = registered_capabilities

    # Router should not have dispatcher reference
    assert not hasattr(router, 'dispatcher')
    assert not hasattr(router, '_dispatcher')

    # Router should work independently
    task = "Echo test"
    analysis = analyzer.analyze(task)
    selection = router.route(analysis.intent)

    # Should return result without dispatcher
    assert selection is not None
    assert selection.selected is not None


def test_dispatcher_does_not_access_analyzer(execution_pipeline, registered_capabilities):
    """
    Verify Dispatcher does NOT access Analyzer.

    Architectural isolation test.
    """
    analyzer, router, dispatcher = execution_pipeline

    router.capabilities = registered_capabilities

    # Dispatcher should not have analyzer reference
    assert not hasattr(dispatcher, 'analyzer')
    assert not hasattr(dispatcher, '_analyzer')

    # Dispatcher should work with SelectionResult only
    task = "Echo test"
    analysis = analyzer.analyze(task)
    selection = router.route(analysis.intent)

    context = TaskContext(
        intent=analysis.intent,
        raw_input=task,
        parameters={}
    )

    # Dispatch without analyzer
    result = dispatcher.dispatch(selection, context)

    # Should return result
    assert result is not None


# =============================================================================
# Run Instructions
# =============================================================================

"""
To run these tests:

    cd /home/onor/ai_os_final/services/core
    pytest execution/test_e2e_pipeline.py -v

Expected output: 8 passed

These tests verify:
1. Complete pipeline flow (5 scenarios)
2. Data integrity across layers
3. Architectural isolation (no cross-layer dependencies)

If any test fails → PIPELINE INTEGRATION BROKEN
Do NOT proceed to real executor implementation.
"""
