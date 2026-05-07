"""
Capability Contract - Declarative skill description

Pure declaration layer. No execution logic. No LLM knowledge.
Defines WHAT a skill can do, not HOW.

Depends on: intent_schema.py

Author: AI-OS Architecture v3.1
Date: 2026-03-03
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Set
from enum import Enum

# Import from intent_schema (dependency: intent_schema ← capability_contract)
from execution.intent_schema import IntentType, ComplexityLevel, InputType, OutputType

# Import idempotency contract
from execution.idempotency import IdempotencyLevel, RETRY_SAFE_LEVELS, FALLBACK_SAFE_LEVELS


# =============================================================================
# Contract Validation
# =============================================================================

def validate_capability_consistency(capability: 'SkillCapability') -> None:
    """
    Validate capability contract for internal consistency.

    CRITICAL: This is part of the safety perimeter.
    Prevents misconfigured capabilities from bypassing safety guarantees.

    Rules:
    1. SAFE + (supports_persistence=True OR supports_external_io=True) → ERROR
    2. NON_IDEMPOTENT + (no persistence AND no external_io) → WARNING (likely misconfigured)

    Args:
        capability: SkillCapability to validate

    Raises:
        ValueError: If capability contract violates safety rules
    """
    errors = []

    # Rule 1: SAFE capabilities cannot have side effects
    if capability.idempotency == IdempotencyLevel.SAFE:
        if capability.supports_persistence:
            errors.append(
                f"SAFE capability '{capability.name}' has supports_persistence=True. "
                f"SAFE capabilities must NOT persist data."
            )
        if capability.supports_external_io:
            errors.append(
                f"SAFE capability '{capability.name}' has supports_external_io=True. "
                f"SAFE capabilities must NOT do external I/O."
            )

    # Rule 2: NON_IDEMPOTENT without side effects is suspicious
    if capability.idempotency == IdempotencyLevel.NON_IDEMPOTENT:
        if not capability.supports_persistence and not capability.supports_external_io:
            # This is likely a misconfiguration
            # NON_IDEMPOTENT should have side effects by definition
            errors.append(
                f"NON_IDEMPOTENT capability '{capability.name}' has "
                f"supports_persistence=False AND supports_external_io=False. "
                f"This is contradictory - NON_IDEMPOTENT requires side effects."
            )

    if errors:
        raise ValueError(
            f"Capability contract validation failed for '{capability.name}':\n" +
            "\n".join(f"  - {e}" for e in errors)
        )


# =============================================================================
# Enums (execution classification)
# =============================================================================

class ExecutionType(str, Enum):
    """Type of execution engine."""
    CODE = "code"      # Python function, deterministic
    LLM = "llm"        # Language model, probabilistic


# =============================================================================
# Core Model
# =============================================================================

class SkillCapability(BaseModel):
    """
    Declarative skill capability contract.

    WHAT: Defines what the skill can do
    NOT HOW: No execution binding, no LLM configuration

    Design principles:
    - Pure declaration (no methods)
    - No execution logic (no match, score, select)
    - No LLM knowledge (no model, temperature, prompt)
    - Many capabilities can support same intent (priority decides)
    """

    # Identification
    name: str = Field(
        ...,
        description="Unique skill identifier (e.g., 'echo', 'write_file')"
    )

    # Semantic classification (many-to-one with intent)
    intent: IntentType = Field(
        ...,
        description="Primary intent this capability handles"
    )

    # Type constraints
    supported_inputs: List[InputType] = Field(
        ...,
        min_items=1,
        description="Input types this capability can accept"
    )

    supported_outputs: List[OutputType] = Field(
        ...,
        min_items=1,
        description="Output types this capability can produce"
    )

    # Execution requirements
    supports_persistence: bool = Field(
        ...,
        description="Whether this capability can persist results"
    )

    supports_external_io: bool = Field(
        ...,
        description="Whether this capability requires external I/O (network, disk)"
    )

    # Complexity constraint
    max_complexity: ComplexityLevel = Field(
        ...,
        description="Maximum task complexity this capability can handle"
    )

    # Execution classification
    execution_type: ExecutionType = Field(
        ...,
        description="Execution engine type (code or llm)"
    )

    # Priority for conflict resolution
    priority: int = Field(
        default=0,
        ge=0,
        description="Priority for selection (higher wins when multiple capabilities match)"
    )

    # Idempotency (CRITICAL for retry/fallback safety)
    idempotency: IdempotencyLevel = Field(
        default=IdempotencyLevel.NON_IDEMPOTENT,
        description="Idempotency level - determines retry/fallback safety"
    )

    @property
    def retry_safe(self) -> bool:
        """
        Computed property: Is this capability safe to retry?

        Based on idempotency level.
        Prevents duplicate side effects.

        Returns:
            True if retry is safe, False otherwise
        """
        return self.idempotency in RETRY_SAFE_LEVELS

    @property
    def fallback_safe(self) -> bool:
        """
        Computed property: Is this capability safe to fallback from?

        Based on idempotency level.
        Prevents duplicate side effects from fallback execution.

        Returns:
            True if fallback is safe, False otherwise
        """
        return self.idempotency in FALLBACK_SAFE_LEVELS

    @model_validator(mode='after')
    def validate_contract(self) -> 'SkillCapability':
        """
        Validate capability contract after initialization.

        This is CRITICAL for safety - prevents misconfigured capabilities
        from bypassing idempotency guarantees.

        Raises:
            ValueError: If capability contract violates safety rules
        """
        validate_capability_consistency(self)
        return self

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "name": "echo",
                "intent": "transform",
                "supported_inputs": ["text"],
                "supported_outputs": ["text"],
                "supports_persistence": False,
                "supports_external_io": False,
                "max_complexity": "low",
                "execution_type": "code",
                "priority": 100
            }
        }


# =============================================================================
# Examples (for documentation, not execution)
# =============================================================================

# Example 1: Simple code skill
ECHO_CAPABILITY = SkillCapability(
    name="echo",
    intent=IntentType.TRANSFORM,
    supported_inputs=[InputType.TEXT],
    supported_outputs=[OutputType.TEXT],
    supports_persistence=False,
    supports_external_io=False,
    max_complexity=ComplexityLevel.LOW,
    execution_type=ExecutionType.CODE,
    priority=100,
    idempotency=IdempotencyLevel.SAFE  # ✅ No side effects
)

# Example 2: File writing skill
WRITE_FILE_CAPABILITY = SkillCapability(
    name="write_file",
    intent=IntentType.STORE,
    supported_inputs=[InputType.TEXT],
    supported_outputs=[OutputType.FILE],
    supports_persistence=True,
    supports_external_io=True,
    max_complexity=ComplexityLevel.LOW,
    execution_type=ExecutionType.CODE,
    priority=90,
    idempotency=IdempotencyLevel.NON_IDEMPOTENT  # ✅ Creates files
)

# Example 3: LLM summarization skill
SUMMARIZE_CAPABILITY = SkillCapability(
    name="summarize_text",
    intent=IntentType.SUMMARIZE,
    supported_inputs=[InputType.TEXT],
    supported_outputs=[OutputType.TEXT],
    supports_persistence=False,
    supports_external_io=False,
    max_complexity=ComplexityLevel.HIGH,
    execution_type=ExecutionType.LLM,
    priority=50,
    idempotency=IdempotencyLevel.SAFE  # ✅ No external side effects
)

# Example 4: LLM story generation skill
GENERATE_STORY_CAPABILITY = SkillCapability(
    name="generate_story",
    intent=IntentType.GENERATE,
    supported_inputs=[InputType.TEXT],
    supported_outputs=[OutputType.TEXT],
    supports_persistence=False,
    supports_external_io=False,
    max_complexity=ComplexityLevel.HIGH,
    execution_type=ExecutionType.LLM,
    priority=45,
    idempotency=IdempotencyLevel.SAFE  # ✅ No external side effects
)
