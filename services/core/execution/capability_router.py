"""
Capability Router - Pure deterministic selection

DUMB selector, NOT smart brain.
Works with declarations only. No runtime logic. No fallbacks.

Depends on: intent_schema, capability_contract
Author: AI-OS Architecture v3.1
Date: 2026-03-03
"""

from pydantic import BaseModel, Field
from typing import List
from enum import Enum

from execution.intent_schema import TaskIntent, COMPLEXITY_RANK
from execution.capability_contract import SkillCapability


# =============================================================================
# Exceptions
# =============================================================================

class NoCapabilityFound(Exception):
    """
    Raised when no capability matches the intent.

    This is a CORRECT system state, not an error to hide.
    Caller should handle: either fallback or reject task.
    """

    def __init__(self, intent: str, reason: str):
        self.intent = intent
        self.reason = reason
        super().__init__(f"No capability found for intent '{intent}': {reason}")


# =============================================================================
# Enums
# =============================================================================

class RejectionReason(str, Enum):
    """Why a capability was rejected during matching."""

    # Filter stages
    INTENT_MISMATCH = "intent_mismatch"          # Step 1: Intent doesn't match
    INPUT_TYPE_MISMATCH = "input_type_mismatch"  # Step 2: Input type not supported
    OUTPUT_TYPE_MISMATCH = "output_type_mismatch" # Step 2: Output type not supported
    PERSISTENCE_NOT_SUPPORTED = "persistence_not_supported"  # Step 3: Persistence required but not supported
    EXTERNAL_IO_NOT_SUPPORTED = "external_io_not_supported"  # Step 3: External I/O required but not supported
    COMPLEXITY_TOO_HIGH = "complexity_too_high"  # Step 3: Task complexity exceeds capability max


# =============================================================================
# Models
# =============================================================================

class RejectedCapability(BaseModel):
    """A capability that was rejected during selection (for observability)."""

    capability: SkillCapability = Field(
        ...,
        description="The capability that was rejected"
    )

    reason: RejectionReason = Field(
        ...,
        description="Why this capability was rejected"
    )

    detail: str = Field(
        ...,
        description="Human-readable explanation"
    )


class SelectionResult(BaseModel):
    """
    Result of capability routing.

    Contains selected capability PLUS metadata for observability.
    Not for routing logic - only for debug and audit.
    """

    selected: SkillCapability = Field(
        ...,
        description="The capability that was selected"
    )

    rejected: List[RejectedCapability] = Field(
        default_factory=list,
        description="Capabilities that were considered but rejected"
    )

    total_candidates: int = Field(
        ...,
        description="Total capabilities considered for selection"
    )

    selection_reason: str = Field(
        ...,
        description="Why this capability was selected (e.g., 'priority=100')"
    )

    @property
    def has_rejections(self) -> bool:
        """Whether any capabilities were rejected."""
        return len(self.rejected) > 0


# =============================================================================
# Router
# =============================================================================

class CapabilityRouter:
    """
    Pure deterministic capability selector.

    DUMB, not smart:
    - No fallback logic
    - No runtime statistics
    - No cost/latency awareness
    - Works with declarations ONLY

    Routing logic (4 steps, strictly ordered):
    1. Filter by intent (exact match)
    2. Filter by input/output types
    3. Filter by constraints (complexity, persistence, external_io)
    4. Sort by priority and select best
    """

    def __init__(self, capabilities: List[SkillCapability]):
        """
        Initialize router with available capabilities.

        Args:
            capabilities: All registered capabilities in the system
        """
        self.capabilities = capabilities

    def route(self, intent: TaskIntent) -> SelectionResult:
        """
        Select best capability for given intent.

        Args:
            intent: TaskIntent from TaskAnalyzer

        Returns:
            SelectionResult with selected capability and rejection metadata

        Raises:
            NoCapabilityFound: If no capability matches the intent
        """
        # Step 1: Filter by intent
        candidates = self._filter_by_intent(intent)
        rejected = self._track_rejected(self.capabilities, candidates, RejectionReason.INTENT_MISMATCH)

        # Step 2: Filter by input/output types
        candidates = self._filter_by_types(intent, candidates, rejected)

        # Step 3: Filter by constraints
        candidates = self._filter_by_constraints(intent, candidates, rejected)

        # Step 4: Sort by priority and select best
        if not candidates:
            raise NoCapabilityFound(
                intent=intent.intent.value,
                reason=f"No capability matches all requirements. Rejected {len(rejected)} candidates."
            )

        # Select best (highest priority wins)
        selected = max(candidates, key=lambda c: c.priority)

        # Build selection result
        return SelectionResult(
            selected=selected,
            rejected=rejected,
            total_candidates=len(self.capabilities),
            selection_reason=f"Highest priority ({selected.priority})"
        )

    # =========================================================================
    # Private methods (pure filtering, no logic)
    # =========================================================================

    def _filter_by_intent(self, intent: TaskIntent) -> List[SkillCapability]:
        """
        Step 1: Filter by exact intent match.

        Many capabilities can support same intent - this is correct.
        """
        return [c for c in self.capabilities if c.intent == intent.intent]

    def _filter_by_types(
        self,
        intent: TaskIntent,
        candidates: List[SkillCapability],
        rejected: List[RejectedCapability]
    ) -> List[SkillCapability]:
        """
        Step 2: Filter by input/output types.

        Strict match - no "almost fits".
        """
        filtered = []

        for cap in candidates:
            # Input type must be supported
            if intent.input_type not in cap.supported_inputs:
                rejected.append(RejectedCapability(
                    capability=cap,
                    reason=RejectionReason.INPUT_TYPE_MISMATCH,
                    detail=f"Input type '{intent.input_type}' not in supported: {cap.supported_inputs}"
                ))
                continue

            # Output type must be supported
            if intent.output_type not in cap.supported_outputs:
                rejected.append(RejectedCapability(
                    capability=cap,
                    reason=RejectionReason.OUTPUT_TYPE_MISMATCH,
                    detail=f"Output type '{intent.output_type}' not in supported: {cap.supported_outputs}"
                ))
                continue

            filtered.append(cap)

        return filtered

    def _filter_by_constraints(
        self,
        intent: TaskIntent,
        candidates: List[SkillCapability],
        rejected: List[RejectedCapability]
    ) -> List[SkillCapability]:
        """
        Step 3: Filter by execution constraints.

        Check: persistence, external_io, complexity
        """
        filtered = []

        for cap in candidates:
            # Persistence requirement
            if intent.requires_persistence and not cap.supports_persistence:
                rejected.append(RejectedCapability(
                    capability=cap,
                    reason=RejectionReason.PERSISTENCE_NOT_SUPPORTED,
                    detail=f"Task requires persistence, but {cap.name} does not support it"
                ))
                continue

            # External I/O requirement
            if intent.requires_external_io and not cap.supports_external_io:
                rejected.append(RejectedCapability(
                    capability=cap,
                    reason=RejectionReason.EXTERNAL_IO_NOT_SUPPORTED,
                    detail=f"Task requires external I/O, but {cap.name} does not support it"
                ))
                continue

            # Complexity constraint
            if intent.complexity_rank > COMPLEXITY_RANK[cap.max_complexity.value]:
                rejected.append(RejectedCapability(
                    capability=cap,
                    reason=RejectionReason.COMPLEXITY_TOO_HIGH,
                    detail=f"Task complexity '{intent.complexity}' exceeds {cap.name} max '{cap.max_complexity}'"
                ))
                continue

            filtered.append(cap)

        return filtered

    def _track_rejected(
        self,
        all_caps: List[SkillCapability],
        accepted: List[SkillCapability],
        reason: RejectionReason
    ) -> List[RejectedCapability]:
        """
        Helper to track rejected capabilities for observability.
        """
        accepted_names = {c.name for c in accepted}
        rejected = []

        for cap in all_caps:
            if cap.name not in accepted_names:
                rejected.append(RejectedCapability(
                    capability=cap,
                    reason=reason,
                    detail=f"Rejected at stage: {reason.name}"
                ))

        return rejected
