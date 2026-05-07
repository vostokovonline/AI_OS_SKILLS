"""
Contract tests for CapabilityRouter

These are NOT unit tests.
These verify ARCHITECTURAL GUARANTEES.

If Router fails these tests - the layer is broken.
Run: pytest test_capability_router.py -v
"""

import pytest
from execution.capability_router import (
    CapabilityRouter,
    NoCapabilityFound,
    SelectionResult,
    RejectedCapability,
    RejectionReason
)
from execution.capability_contract import SkillCapability, ExecutionType
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
def simple_capabilities():
    """Minimal set of capabilities for testing."""
    return [
        SkillCapability(
            name="echo_low",
            intent=IntentType.TRANSFORM,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=50
        ),
        SkillCapability(
            name="echo_high",
            intent=IntentType.TRANSFORM,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.HIGH,
            execution_type=ExecutionType.CODE,
            priority=100  # Higher priority
        ),
        SkillCapability(
            name="summarize",
            intent=IntentType.SUMMARIZE,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.HIGH,
            execution_type=ExecutionType.LLM,
            priority=50
        ),
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
    ]


@pytest.fixture
def router(simple_capabilities):
    """Router initialized with test capabilities."""
    return CapabilityRouter(simple_capabilities)


# =============================================================================
# Contract Test 1: No Capability → Exception
# =============================================================================

def test_no_capability_raises_exception(router):
    """
    CONTRACT: If no capability matches → NoCapabilityFound exception.

    NOT: silent fallback
    NOT: return None
    NOT: try "best effort"
    """
    # Intent that nobody supports
    intent = TaskIntent(
        intent=IntentType.RETRIEVE,
        input_type=InputType.TEXT,
        output_type=OutputType.TEXT,
        requires_persistence=False,
        requires_external_io=False,
        complexity=ComplexityLevel.LOW,
        estimated_tokens=100,
        confidence=0.9
    )

    with pytest.raises(NoCapabilityFound) as exc_info:
        router.route(intent)

    # Exception contains intent and reason
    assert "retrieve" in str(exc_info.value).lower()
    assert exc_info.value.intent == "retrieve"


# =============================================================================
# Contract Test 2: Multiple candidates → Highest priority wins
# =============================================================================

def test_multiple_candidates_selects_highest_priority(router):
    """
    CONTRACT: If multiple capabilities match → highest priority wins.

    NOT: random selection
    NOT: first in list
    NOT: based on execution_type
    """
    # Both echo_low and echo_high support TRANSFORM
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

    result = router.route(intent)

    # echo_high has priority=100, echo_low has priority=50
    assert result.selected.name == "echo_high"
    assert result.selected.priority == 100


# =============================================================================
# Contract Test 3: Complexity mismatch → Rejected with reason
# =============================================================================

def test_complexity_mismatch_rejected(router):
    """
    CONTRACT: If task complexity exceeds capability → rejected with COMPLEXITY_TOO_HIGH.

    NOT: silent rejection
    NOT: ignored
    """
    # echo_low only supports LOW complexity
    intent = TaskIntent(
        intent=IntentType.TRANSFORM,
        input_type=InputType.TEXT,
        output_type=OutputType.TEXT,
        requires_persistence=False,
        requires_external_io=False,
        complexity=ComplexityLevel.HIGH,  # Too high for echo_low
        estimated_tokens=100,
        confidence=0.9
    )

    result = router.route(intent)

    # Should select echo_high (supports HIGH complexity)
    assert result.selected.name == "echo_high"

    # echo_low should be rejected
    echo_low_rejections = [
        r for r in result.rejected
        if r.capability.name == "echo_low"
    ]
    assert len(echo_low_rejections) == 1
    assert echo_low_rejections[0].reason == RejectionReason.COMPLEXITY_TOO_HIGH


# =============================================================================
# Contract Test 4: Different execution_type → Router ignores it
# =============================================================================

def test_execution_type_ignored_in_selection(router):
    """
    CONTRACT: Router ignores execution_type when matching.

    Router works with declarations ONLY.
    execution_type is for Dispatcher, not Router.
    """
    # SUMMARIZE is LLM, TRANSFORM is CODE
    # Router should NOT prefer based on execution_type

    llm_intent = TaskIntent(
        intent=IntentType.SUMMARIZE,
        input_type=InputType.TEXT,
        output_type=OutputType.TEXT,
        requires_persistence=False,
        requires_external_io=False,
        complexity=ComplexityLevel.HIGH,
        estimated_tokens=1000,
        confidence=0.9
    )

    result = router.route(llm_intent)

    # Should select summarize (only match)
    assert result.selected.name == "summarize"
    assert result.selected.execution_type == ExecutionType.LLM


# =============================================================================
# Contract Test 5: Determinism - Same input = Same output
# =============================================================================

def test_determinism_same_intent_same_result(router):
    """
    CONTRACT: Router is deterministic.
    Same intent → always same SelectionResult.
    """
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

    result1 = router.route(intent)
    result2 = router.route(intent)

    # Exact same selection
    assert result1.selected.name == result2.selected.name
    assert result1.total_candidates == result2.total_candidates
    assert len(result1.rejected) == len(result2.rejected)


# =============================================================================
# Contract Test 6: Add new capability → Old results don't break
# =============================================================================

def test_adding_capability_doesnt_break_existing(router):
    """
    CONTRACT: Adding new capability doesn't change existing selections.

    Router is pure function - no state mutation.
    """
    # Initial selection
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

    result1 = router.route(intent)
    original_selection = result1.selected.name

    # Add new capability with lower priority
    new_caps = router.capabilities + [
        SkillCapability(
            name="echo_new",
            intent=IntentType.TRANSFORM,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=False,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            priority=10  # Lower than existing
        )
    ]

    new_router = CapabilityRouter(new_caps)
    result2 = new_router.route(intent)

    # Original selection still wins (higher priority)
    assert result2.selected.name == original_selection


# =============================================================================
# Contract Test 7: Persistence requirement mismatch
# =============================================================================

def test_persistence_requirement_mismatch(router):
    """
    CONTRACT: If task requires persistence but capability doesn't support → rejected.
    """
    intent = TaskIntent(
        intent=IntentType.TRANSFORM,
        input_type=InputType.TEXT,
        output_type=OutputType.TEXT,
        requires_persistence=True,  # Requires persistence
        requires_external_io=False,
        complexity=ComplexityLevel.LOW,
        estimated_tokens=100,
        confidence=0.9
    )

    # TRANSFORM capabilities don't support persistence
    # Should raise NoCapabilityFound
    with pytest.raises(NoCapabilityFound):
        router.route(intent)


# =============================================================================
# Contract Test 8: External I/O requirement mismatch
# =============================================================================

def test_external_io_requirement_mismatch(router):
    """
    CONTRACT: If task requires external I/O but capability doesn't support → rejected.
    """
    intent = TaskIntent(
        intent=IntentType.TRANSFORM,
        input_type=InputType.TEXT,
        output_type=OutputType.TEXT,
        requires_persistence=False,
        requires_external_io=True,  # Requires external I/O
        complexity=ComplexityLevel.LOW,
        estimated_tokens=100,
        confidence=0.9
    )

    # TRANSFORM capabilities don't support external I/O
    # Should raise NoCapabilityFound
    with pytest.raises(NoCapabilityFound):
        router.route(intent)


# =============================================================================
# Contract Test 9: Input type mismatch
# =============================================================================

def test_input_type_mismatch(router):
    """
    CONTRACT: If task input type not supported → rejected.
    """
    intent = TaskIntent(
        intent=IntentType.TRANSFORM,
        input_type=InputType.FILE,  # TRANSFORM capabilities only support TEXT
        output_type=OutputType.TEXT,
        requires_persistence=False,
        requires_external_io=False,
        complexity=ComplexityLevel.LOW,
        estimated_tokens=100,
        confidence=0.9
    )

    # Should raise NoCapabilityFound
    with pytest.raises(NoCapabilityFound):
        router.route(intent)


# =============================================================================
# Contract Test 10: Output type mismatch
# =============================================================================

def test_output_type_mismatch(router):
    """
    CONTRACT: If task output type not supported → rejected.
    """
    intent = TaskIntent(
        intent=IntentType.STORE,
        input_type=InputType.TEXT,
        output_type=OutputType.TEXT,  # STORE capability outputs FILE
        requires_persistence=False,
        requires_external_io=False,
        complexity=ComplexityLevel.LOW,
        estimated_tokens=100,
        confidence=0.9
    )

    # Should raise NoCapabilityFound
    with pytest.raises(NoCapabilityFound):
        router.route(intent)


# =============================================================================
# Run Instructions
# =============================================================================

"""
To run these tests:

    cd /home/onor/ai_os_final/services/core
    pytest execution/test_capability_router.py -v

Expected output: 10 passed

If any test fails → ARCHITECTURAL BUG IN ROUTER
Do not proceed to next layer.
"""
