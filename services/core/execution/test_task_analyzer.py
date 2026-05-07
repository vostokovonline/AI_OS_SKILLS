"""
Contract tests for TaskAnalyzer

These verify PURE CLASSIFIER behavior.
If Analyzer fails these - it has become "too smart".

Run: pytest test_task_analyzer.py -v
"""

import pytest
from unittest.mock import Mock

from execution.task_analyzer import (
    TaskAnalyzer,
    InvalidLLMOutputException,
    LowConfidenceException
)
from execution.intent_schema import (
    TaskIntent,
    TaskAnalysisResult,
    IntentType,
    InputType,
    OutputType,
    ComplexityLevel,
    MIN_CONFIDENCE_THRESHOLD
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_client():
    """Mock LLM client with generate() method."""
    client = Mock()
    client.generate = Mock(return_value='''```json
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
```''')
    return client


@pytest.fixture
def analyzer(mock_llm_client):
    """TaskAnalyzer with mock LLM."""
    return TaskAnalyzer(
        llm_client=mock_llm_client,
        model="gpt-4o-mini"
    )


# =============================================================================
# Contract Test 1: Determinism - same input = same output
# =============================================================================

def test_determinism_same_input_same_output(analyzer):
    """
    CONTRACT: Same input → identical output (temperature=0).

    NOT: random variation
    NOT: different results on multiple calls
    """
    task = "Summarize this document"

    result1 = analyzer.analyze(task)
    result2 = analyzer.analyze(task)

    # Verify exact same results
    assert result1.intent.intent == result2.intent.intent
    assert result1.intent.input_type == result2.intent.input_type
    assert result1.intent.output_type == result2.intent.output_type
    assert result1.intent.complexity == result2.intent.complexity
    assert result1.intent.confidence == result2.intent.confidence
    assert result1.intent.estimated_tokens == result2.intent.estimated_tokens


# =============================================================================
# Contract Test 2: Temperature = 0
# =============================================================================

def test_temperature_is_zero(mock_llm_client):
    """
    CONTRACT: Temperature is always 0 (deterministic).

    NOT: temperature > 0 (creative/probabilistic)
    """
    analyzer = TaskAnalyzer(
        llm_client=mock_llm_client,
        model="gpt-4o-mini"
    )

    # Verify temperature is 0
    assert analyzer.temperature == 0

    # Verify LLM call uses temperature=0
    analyzer.analyze("test task")

    # Check that generate was called with temperature=0
    call_kwargs = mock_llm_client.generate.call_args[1]
    assert call_kwargs['temperature'] == 0


# =============================================================================
# Contract Test 3: Invalid JSON → Exception
# =============================================================================

def test_invalid_json_raises_exception(mock_llm_client):
    """
    CONTRACT: Invalid JSON → InvalidLLMOutputException.

    NOT: silent fallback
    NOT: attempt to fix JSON
    """
    # Mock returns invalid JSON
    mock_llm_client.generate.return_value = "This is not JSON"

    analyzer = TaskAnalyzer(llm_client=mock_llm_client)

    with pytest.raises(InvalidLLMOutputException) as exc_info:
        analyzer.analyze("test task")

    assert "Invalid JSON" in str(exc_info.value.reason)


# =============================================================================
# Contract Test 4: Low confidence → Exception
# =============================================================================

def test_low_confidence_raises_exception(mock_llm_client):
    """
    CONTRACT: Confidence < threshold → LowConfidenceException.

    NOT: continue anyway
    NOT: automatically retry inside Analyzer
    """
    # Mock returns low confidence
    mock_llm_client.generate.return_value = '''```json
{
  "intent": "summarize",
  "input_type": "text",
  "output_type": "text",
  "requires_persistence": false,
  "requires_external_io": false,
  "complexity": "medium",
  "estimated_tokens": 800,
  "confidence": 0.4
}
```'''

    analyzer = TaskAnalyzer(llm_client=mock_llm_client)

    with pytest.raises(LowConfidenceException) as exc_info:
        analyzer.analyze("test task")

    assert exc_info.value.confidence == 0.4
    assert exc_info.value.threshold == MIN_CONFIDENCE_THRESHOLD


# =============================================================================
# Contract Test 5: No retry logic inside Analyzer
# =============================================================================

def test_no_retry_logic(mock_llm_client):
    """
    CONTRACT: Analyzer does NOT retry internally.

    LLM client is called exactly once.
    Retry is orchestration layer's responsibility.
    """
    analyzer = TaskAnalyzer(llm_client=mock_llm_client)

    analyzer.analyze("test task")

    # Verify exactly ONE call to LLM
    assert mock_llm_client.generate.call_count == 1


# =============================================================================
# Contract Test 6: Schema validation
# =============================================================================

def test_schema_validation_missing_fields(mock_llm_client):
    """
    CONTRACT: Missing required fields → InvalidLLMOutputException.

    All 8 fields must be present.
    """
    # Mock returns incomplete JSON
    mock_llm_client.generate.return_value = '''```json
{
  "intent": "summarize",
  "input_type": "text"
}
```'''

    analyzer = TaskAnalyzer(llm_client=mock_llm_client)

    with pytest.raises(InvalidLLMOutputException) as exc_info:
        analyzer.analyze("test task")

    assert "Missing required fields" in str(exc_info.value.reason)


# =============================================================================
# Contract Test 7: Returns correct structure
# =============================================================================

def test_returns_task_analysis_result(analyzer):
    """
    CONTRACT: Returns TaskAnalysisResult with correct structure.
    """
    result = analyzer.analyze("Summarize this document")

    # Verify type
    assert isinstance(result, TaskAnalysisResult)

    # Verify intent is TaskIntent
    assert isinstance(result.intent, TaskIntent)

    # Verify required fields
    assert result.raw_task == "Summarize this document"
    assert result.analyzer_model == "gpt-4o-mini"
    assert result.retry_count == 0


# =============================================================================
# Contract Test 8: No access to Router/Dispatcher/Registry
# =============================================================================

def test_no_magic_access(analyzer):
    """
    CONTRACT: Analyzer does NOT access Router, Dispatcher, or Registry.

    Analyzer only depends on:
    - LLM client
    - Intent schema

    This test verifies architectural isolation.
    """
    # Analyzer should only have llm_client and model
    assert hasattr(analyzer, 'llm')
    assert hasattr(analyzer, 'model')
    assert hasattr(analyzer, 'temperature')

    # Should NOT have references to routing/dispatching
    assert not hasattr(analyzer, 'router')
    assert not hasattr(analyzer, 'dispatcher')
    assert not hasattr(analyzer, 'capability_registry')

    # Should NOT have retry logic
    assert not hasattr(analyzer, 'max_retries')
    assert not hasattr(analyzer, 'retry_policy')


# =============================================================================
# Contract Test 9: Handles markdown code blocks
# =============================================================================

def test_handles_markdown_code_blocks(mock_llm_client):
    """
    CONTRACT: Correctly extracts JSON from markdown code blocks.
    """
    # Mock returns markdown with ```json block
    mock_llm_client.generate.return_value = '''Here is the analysis:

```json
{
  "intent": "transform",
  "input_type": "text",
  "output_type": "text",
  "requires_persistence": false,
  "requires_external_io": false,
  "complexity": "low",
  "estimated_tokens": 100,
  "confidence": 0.98
}
```

This should be correct.'''

    analyzer = TaskAnalyzer(llm_client=mock_llm_client)

    result = analyzer.analyze("Echo hello")

    assert result.intent.intent == IntentType.TRANSFORM
    assert result.intent.confidence == 0.98


# =============================================================================
# Contract Test 10: Preserves raw_task
# =============================================================================

def test_preserves_raw_task(analyzer):
    """
    CONTRACT: Original task text is preserved in result.

    Critical for audit/trace.
    """
    original_task = "Summarize this document about AI architecture"

    result = analyzer.analyze(original_task)

    # Verify exact preservation
    assert result.raw_task == original_task


# =============================================================================
# Run Instructions
# =============================================================================

"""
To run these tests:

    cd /home/onor/ai_os_final/services/core
    pytest execution/test_task_analyzer.py -v

Expected output: 10 passed

If any test fails → ANALYZER HAS BECOME TOO SMART
Do NOT proceed to integration.
"""
