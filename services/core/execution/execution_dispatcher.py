"""
Execution Dispatcher - Dumb delegation layer

Pure infrastructure. NO retry logic. NO fallback. NO routing.
Only delegates to appropriate executor by execution_type.

Depends on: intent_schema, capability_contract, capability_router
Author: AI-OS Architecture v3.1
Date: 2026-03-03
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from enum import Enum

from execution.intent_schema import TaskIntent
from execution.capability_contract import SkillCapability, ExecutionType
from execution.capability_router import SelectionResult


# =============================================================================
# Models
# =============================================================================

class TaskContext(BaseModel):
    """
    Execution context passed to executor.

    Contains everything needed to execute the task.
    Dispatcher does NOT modify or enrich this.
    """

    intent: TaskIntent = Field(
        ...,
        description="Structured intent from TaskAnalyzer"
    )

    raw_input: str = Field(
        ...,
        description="Original user input"
    )

    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution parameters"
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
                "raw_input": "Summarize this document",
                "parameters": {}
            }
        }


class ExecutionResult(BaseModel):
    """
    Result from executor execution.

    Pure data. NO routing logic. NO fallback metadata.
    """

    success: bool = Field(
        ...,
        description="Whether execution succeeded"
    )

    side_effect_committed: bool = Field(
        ...,
        description=(
            "Whether executor committed a side effect before failing. "
            "CRITICAL for fallback safety: If True, fallback is BLOCKED to prevent duplicates. "
            "Fail closed: If uncertain whether side effect occurred, set to True."
        )
    )

    output: Any = Field(
        ...,
        description="Execution output (text, file path, structured data, etc.)"
    )

    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed"
    )

    executor_type: Optional[ExecutionType] = Field(
        default=None,
        description="Type of executor that performed execution (None for escalated results)"
    )

    capability_name: Optional[str] = Field(
        default=None,
        description="Name of capability that was executed (None for escalated results)"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Execution metadata (timing, tokens used, etc.)"
    )

    artifacts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Artifacts produced by execution (files, knowledge, reports, etc.). "
            "Extracted from SkillResult if executor is code-based."
        )
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "success": True,
                "output": "Summary of document...",
                "error": None,
                "executor_type": "llm",
                "capability_name": "summarize_text",
                "metadata": {"tokens_used": 750, "duration_ms": 1200}
            }
        }


# =============================================================================
# Exceptions
# =============================================================================

class ExecutorNotFoundError(Exception):
    """
    Raised when no executor registered for execution_type.

    This is CONFIGURATION ERROR, not runtime error.
    System should not start if executors are missing.
    """

    def __init__(self, execution_type: str):
        self.execution_type = execution_type
        super().__init__(f"No executor registered for execution_type '{execution_type}'")


class ExecutionFailed(Exception):
    """
    Raised when executor execution fails.

    This bubbles up from executor - Dispatcher does NOT catch it.
    Caller (orchestration layer) decides what to do.
    """

    def __init__(self, capability_name: str, reason: str):
        self.capability_name = capability_name
        self.reason = reason
        super().__init__(f"Execution failed for '{capability_name}': {reason}")


# =============================================================================
# Base Executor Interface
# =============================================================================

class BaseExecutor(ABC):
    """
    Abstract base class for executors.

    All executors (code, llm, future types) must implement this interface.
    Dispatcher depends on this interface, NOT concrete classes.
    """

    @abstractmethod
    def execute(
        self,
        capability: SkillCapability,
        context: TaskContext
    ) -> ExecutionResult:
        """
        Execute task using this executor type.

        Args:
            capability: Selected capability from Router
            context: Task execution context

        Returns:
            ExecutionResult with success/output/error

        Raises:
            ExecutionFailed: If execution fails (bubbles up to caller)
        """
        pass


# =============================================================================
# Dispatcher
# =============================================================================

class ExecutionDispatcher:
    """
    Dumb delegation layer.

    WHAT: Delegates execution to appropriate executor by execution_type
    NOT HOW: No routing logic, no fallback, no retry

    Design principles:
    - Pure infrastructure (delegation only)
    - No business logic
    - No error handling (bubbles up to caller)
    - No retry/fallback (that's orchestration layer)
    - Depends on BaseExecutor interface, NOT concrete classes
    """

    def __init__(self, executors: Dict[ExecutionType, BaseExecutor]):
        """
        Initialize dispatcher with executor registry.

        Args:
            executors: Mapping of execution_type to executor instance

        Raises:
            ValueError: If required executors (code, llm) are missing
        """
        # Validate required executors
        required = {ExecutionType.CODE, ExecutionType.LLM}
        missing = required - set(executors.keys())

        if missing:
            raise ValueError(
                f"Missing required executors: {', '.join(m.value for m in missing)}"
            )

        self._executors = executors

    def dispatch(
        self,
        selection: SelectionResult,
        context: TaskContext
    ) -> ExecutionResult:
        """
        Dispatch task to appropriate executor.

        This is a PURE delegation - no logic, no decisions.

        Args:
            selection: SelectionResult from CapabilityRouter
            context: TaskContext with execution parameters

        Returns:
            ExecutionResult from executor

        Raises:
            ExecutorNotFoundError: If no executor for execution_type
            ExecutionFailed: If executor execution fails (bubbled up)
        """
        # Extract execution type from selected capability
        capability = selection.selected
        execution_type = capability.execution_type

        # Find executor (dumb lookup, no fallback)
        if execution_type not in self._executors:
            raise ExecutorNotFoundError(execution_type.value)

        executor = self._executors[execution_type]

        # Delegate execution (NO logic here)
        # Executor may raise ExecutionFailed - we let it bubble up
        result = executor.execute(capability, context)

        return result

    def register_executor(
        self,
        execution_type: ExecutionType,
        executor: BaseExecutor
    ) -> None:
        """
        Register new executor (runtime extension).

        Allows adding new execution types without modifying Dispatcher.

        Args:
            execution_type: Type of executor
            executor: Executor instance
        """
        self._executors[execution_type] = executor
