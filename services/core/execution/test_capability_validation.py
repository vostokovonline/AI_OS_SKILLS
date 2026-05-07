"""
Capability Contract Validation Tests - Safety Perimeter

These tests verify that misconfigured capabilities CANNOT bypass safety guarantees.

Run: pytest execution/test_capability_validation.py -v
"""

import pytest
from execution.capability_contract import SkillCapability
from execution.intent_schema import IntentType, InputType, OutputType, ComplexityLevel
from execution.idempotency import IdempotencyLevel
from execution.capability_contract import ExecutionType


# =============================================================================
# Test 1: SAFE + Persistence = ERROR
# =============================================================================

def test_safe_with_persistence_raises_error():
    """
    CRITICAL TEST: SAFE capability with supports_persistence=True → ERROR.

    This prevents "safe write_file" scenario.
    """
    with pytest.raises(ValueError) as exc_info:
        SkillCapability(
            name="unsafe_safe",
            intent=IntentType.TRANSFORM,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=True,  # ❌ Contradicts SAFE
            supports_external_io=False,
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            idempotency=IdempotencyLevel.SAFE  # ❌ Cannot persist
        )

    error_msg = str(exc_info.value)
    assert "SAFE capability" in error_msg
    assert "supports_persistence=True" in error_msg
    assert "must NOT persist data" in error_msg


# =============================================================================
# Test 2: SAFE + External IO = ERROR
# =============================================================================

def test_safe_with_external_io_raises_error():
    """
    CRITICAL TEST: SAFE capability with supports_external_io=True → ERROR.

    This prevents "safe web_research" scenario.
    """
    with pytest.raises(ValueError) as exc_info:
        SkillCapability(
            name="unsafe_safe",
            intent=IntentType.TRANSFORM,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,
            supports_external_io=True,  # ❌ Contradicts SAFE
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            idempotency=IdempotencyLevel.SAFE  # ❌ Cannot do I/O
        )

    error_msg = str(exc_info.value)
    assert "SAFE capability" in error_msg
    assert "supports_external_io=True" in error_msg
    assert "must NOT do external I/O" in error_msg


# =============================================================================
# Test 3: NON_IDEMPOTENT + No Side Effects = ERROR
# =============================================================================

def test_non_idempotent_without_side_effects_raises_error():
    """
    CRITICAL TEST: NON_IDEMPOTENT capability with no side effects → ERROR.

    This catches misconfiguration (e.g., forgot to set supports_persistence).
    """
    with pytest.raises(ValueError) as exc_info:
        SkillCapability(
            name="misconfigured_non_idempotent",
            intent=IntentType.TRANSFORM,
            supported_inputs=[InputType.TEXT],
            supported_outputs=[OutputType.TEXT],
            supports_persistence=False,  # ❌ No side effects
            supports_external_io=False,  # ❌ No side effects
            max_complexity=ComplexityLevel.LOW,
            execution_type=ExecutionType.CODE,
            idempotency=IdempotencyLevel.NON_IDEMPOTENT  # ❌ Requires side effects
        )

    error_msg = str(exc_info.value)
    assert "NON_IDEMPOTENT capability" in error_msg
    assert "supports_persistence=False AND supports_external_io=False" in error_msg
    assert "requires side effects" in error_msg


# =============================================================================
# Test 4: Valid SAFE Capability
# =============================================================================

def test_valid_safe_capability():
    """
    Verify valid SAFE capability passes validation.
    """
    # Should NOT raise
    capability = SkillCapability(
        name="echo",
        intent=IntentType.TRANSFORM,
        supported_inputs=[InputType.TEXT],
        supported_outputs=[OutputType.TEXT],
        supports_persistence=False,  # ✅ No persistence
        supports_external_io=False,  # ✅ No external I/O
        max_complexity=ComplexityLevel.LOW,
        execution_type=ExecutionType.CODE,
        idempotency=IdempotencyLevel.SAFE
    )

    assert capability.idempotency == IdempotencyLevel.SAFE
    assert capability.retry_safe is True
    assert capability.fallback_safe is True


# =============================================================================
# Test 5: Valid NON_IDEMPOTENT Capability
# =============================================================================

def test_valid_non_idempotent_capability():
    """
    Verify valid NON_IDEMPOTENT capability passes validation.
    """
    # Should NOT raise
    capability = SkillCapability(
        name="write_file",
        intent=IntentType.STORE,
        supported_inputs=[InputType.TEXT],
        supported_outputs=[OutputType.FILE],
        supports_persistence=True,  # ✅ Has side effects
        supports_external_io=True,  # ✅ Has external I/O
        max_complexity=ComplexityLevel.LOW,
        execution_type=ExecutionType.CODE,
        idempotency=IdempotencyLevel.NON_IDEMPOTENT
    )

    assert capability.idempotency == IdempotencyLevel.NON_IDEMPOTENT
    assert capability.retry_safe is False
    assert capability.fallback_safe is False


# =============================================================================
# Test 6: Valid IDEMPOTENT Capability
# =============================================================================

def test_valid_idempotent_capability():
    """
    Verify valid IDEMPOTENT capability passes validation.
    """
    # Should NOT raise
    capability = SkillCapability(
        name="read_file",
        intent=IntentType.RETRIEVE,
        supported_inputs=[InputType.TEXT],
        supported_outputs=[OutputType.FILE],
        supports_persistence=True,  # ✅ Has side effects (idempotent)
        supports_external_io=True,  # ✅ Has external I/O (idempotent)
        max_complexity=ComplexityLevel.LOW,
        execution_type=ExecutionType.CODE,
        idempotency=IdempotencyLevel.IDEMPOTENT
    )

    assert capability.idempotency == IdempotencyLevel.IDEMPOTENT
    assert capability.retry_safe is True
    assert capability.fallback_safe is True


# =============================================================================
# Run Instructions
# =============================================================================

"""
To run these tests:

    cd /home/onor/ai_os_final/services/core
    pytest execution/test_capability_validation.py -v

Expected output: 6 passed

These tests verify the safety perimeter:
1. SAFE + persistence → blocked
2. SAFE + external_io → blocked
3. NON_IDEMPOTENT + no side effects → blocked
4. Valid SAFE → passes
5. Valid NON_IDEMPOTENT → passes
6. Valid IDEMPOTENT → passes

If any test fails → SAFETY PERIMETER BROKEN
DO NOT integrate with goal system.
"""
