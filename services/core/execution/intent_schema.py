"""
Intent Schema for TaskAnalyzer

Pure data contract layer. No routing logic. No capability knowledge.

Author: AI-OS Architecture v3.1
Date: 2026-03-03
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any
from enum import Enum


# =============================================================================
# Constants (centralized limits)
# =============================================================================

MAX_ESTIMATED_TOKENS = 200_000
MIN_CONFIDENCE_THRESHOLD = 0.6
COMPLEXITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


# =============================================================================
# Enums (controlled vocabulary)
# =============================================================================

class IntentType(str, Enum):
    """Controlled intent vocabulary for execution platform."""
    SUMMARIZE = "summarize"
    GENERATE = "generate"
    ANALYZE = "analyze"
    TRANSFORM = "transform"
    STORE = "store"
    RETRIEVE = "retrieve"
    COMPUTE = "compute"


class ComplexityLevel(str, Enum):
    """Task complexity level (string enum for JSON compatibility)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InputType(str, Enum):
    """Input type classification."""
    TEXT = "text"
    FILE = "file"
    STRUCTURED = "structured"
    NONE = "none"


class OutputType(str, Enum):
    """Output type classification."""
    TEXT = "text"
    FILE = "file"
    STRUCTURED = "structured"
    ARTIFACT = "artifact"


# =============================================================================
# Core Models
# =============================================================================

class TaskIntent(BaseModel):
    """
    Structured intent extracted from user task by TaskAnalyzer.

    PURE DATA CONTRACT - no routing logic, no capability knowledge.
    LLM temperature=0 ensures deterministic classification.
    """

    # Semantic classification
    intent: IntentType = Field(
        ...,
        description="Controlled intent vocabulary"
    )

    # Type constraints
    input_type: InputType = Field(
        ...,
        description="Type of input required"
    )

    output_type: OutputType = Field(
        ...,
        description="Type of output produced"
    )

    # Execution requirements
    requires_persistence: bool = Field(
        ...,
        description="Whether task requires saving result to disk/storage"
    )

    requires_external_io: bool = Field(
        ...,
        description="Whether task requires external I/O (network, disk, API)"
    )

    complexity: ComplexityLevel = Field(
        ...,
        description="Task complexity level"
    )

    # Resource estimation
    estimated_tokens: int = Field(
        ...,
        ge=0,
        le=MAX_ESTIMATED_TOKENS,
        description=f"Estimated LLM tokens needed (max {MAX_ESTIMATED_TOKENS})"
    )

    # Confidence for fallback logic
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=f"LLM confidence (0-1, threshold={MIN_CONFIDENCE_THRESHOLD})"
    )

    # Reserved for policy engine extensions (Phase 2+)
    # IMPORTANT: Must not affect routing in Phase 1
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Reserved for policy engine. Does not affect routing."
    )

    @property
    def complexity_rank(self) -> int:
        """
        Get numeric complexity rank for matching.

        Returns:
            1 for low, 2 for medium, 3 for high
        """
        return COMPLEXITY_RANK[self.complexity.value]

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "intent": "summarize",
                "input_type": "text",
                "output_type": "text",
                "requires_persistence": False,
                "requires_external_io": False,
                "complexity": "medium",
                "estimated_tokens": 800,
                "confidence": 0.95,
                "metadata": None
            }
        }


class TaskAnalysisResult(BaseModel):
    """
    Complete result from TaskAnalyzer.

    Wraps TaskIntent with audit/trace metadata.
    """

    intent: TaskIntent = Field(
        ...,
        description="Structured intent extracted from task"
    )

    raw_task: str = Field(
        ...,
        description="Original user task text"
    )

    analyzer_model: str = Field(
        ...,
        description="LLM model used for analysis"
    )

    # Optional: retry count if low confidence
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retries performed (for low confidence)"
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "intent": {
                    "intent": "summarize",
                    "input_type": "text",
                    "output_type": "text",
                    "requires_persistence": False,
                    "requires_external_io": False,
                    "complexity": "medium",
                    "estimated_tokens": 800,
                    "confidence": 0.95
                },
                "raw_task": "Summarize this document",
                "analyzer_model": "gpt-4o-mini",
                "retry_count": 0
            }
        }
