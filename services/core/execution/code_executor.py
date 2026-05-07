"""
Code Executor - Executes Python functions from canonical_skills/

Implements BaseExecutor interface.
Runs actual Python code, NOT LLM generation.

Author: AI-OS Architecture v3.1
Date: 2026-03-03
"""

import sys
import importlib
import traceback
from typing import Any, Dict
from pathlib import Path

from execution.execution_dispatcher import BaseExecutor, ExecutionResult, TaskContext
from execution.capability_contract import SkillCapability
from execution.idempotency import IdempotencyLevel


# =============================================================================
# Executor
# =============================================================================

class CodeExecutor(BaseExecutor):
    """
    Executes Python functions from canonical_skills/.

    Design:
    - Finds function by capability.name
    - Executes with context.parameters
    - Returns ExecutionResult

    Error handling:
    - Catches ALL exceptions
    - Returns success=False with error message
    - Does NOT crash dispatcher
    """

    def __init__(self):
        """Initialize code executor."""
        self.skills_dir = Path(__file__).parent.parent / "canonical_skills"

    def execute(self, capability: SkillCapability, context: TaskContext) -> ExecutionResult:
        """
        Execute Python function for given capability.

        Args:
            capability: Selected capability from Router
            context: Task execution context

        Returns:
            ExecutionResult with success/output/error
        """
        try:
            # Step 1: Find function in canonical_skills
            func = self._find_function(capability.name)

            # Step 2: Prepare parameters
            params = self._prepare_parameters(context)

            # Step 3: Execute function
            output = func(**params)

            # Step 3.5: Extract artifacts if output is SkillResult
            artifacts = []
            if hasattr(output, 'artifacts'):
                # SkillResult object - extract artifacts
                artifacts = [a.to_dict() if hasattr(a, 'to_dict') else a for a in output.artifacts]
                # Also extract the dict representation for output
                output = output.to_dict() if hasattr(output, 'to_dict') else output

            # Step 4: Return success result
            # ✅ Respect capability idempotency contract
            # SAFE capabilities = no side effects
            # NON_IDEMPOTENT capabilities = side effects committed
            side_effect_committed = capability.idempotency != IdempotencyLevel.SAFE

            return ExecutionResult(
                success=True,
                side_effect_committed=side_effect_committed,
                output=output,
                error=None,
                executor_type="code",
                capability_name=capability.name,
                artifacts=artifacts,
                metadata={
                    "executor": "code",
                    "function": func.__name__,
                    "module": func.__module__,
                    "capability_idempotency": capability.idempotency.value,
                    "artifacts_count": len(artifacts)
                }
            )

        except Exception as e:
            # Return error result (do NOT raise)
            # Fail closed: If exception occurred during execution,
            # assume side effect MAY have been committed
            return ExecutionResult(
                success=False,
                side_effect_committed=True,  # Fail closed: assume partial execution
                output=str(e),
                error=f"{type(e).__name__}: {str(e)}",
                executor_type="code",
                capability_name=capability.name,
                metadata={
                    "executor": "code",
                    "traceback": traceback.format_exc()
                }
            )

    def _find_function(self, capability_name: str):
        """
        Find Python function by capability name.

        Strategy:
        1. Check for function with same name in canonical_skills modules
        2. Common patterns:
           - echo() → canonical_skills.echo.echo
           - write_file() → canonical_skills.write_file.write_file
           - summarize() → canonical_skills.summarize_text.summarize

        Args:
            capability_name: Name of capability (e.g., "echo", "write_file")

        Returns:
            Python callable function

        Raises:
            ImportError: If module not found
            AttributeError: If function not found in module
        """
        # Try direct import first
        try:
            module = importlib.import_module(f"canonical_skills.{capability_name}")
            func = getattr(module, capability_name)
            return func
        except (ImportError, AttributeError):
            pass

        # Try common patterns
        patterns = [
            f"canonical_skills.{capability_name}.{capability_name}",  # echo.echo
            f"canonical_skills.{capability_name}_skill.{capability_name}",  # echo_skill.echo
            f"canonical_skills.mvp_skills.{capability_name}",  # mvp_skills.echo
        ]

        for pattern in patterns:
            try:
                module_path = ".".join(pattern.split(".")[:-1])
                func_name = pattern.split(".")[-1]
                module = importlib.import_module(module_path)
                func = getattr(module, func_name)
                return func
            except (ImportError, AttributeError):
                continue

        # If not found, raise
        raise ImportError(
            f"Function not found for capability '{capability_name}'. "
            f"Tried patterns: {patterns}"
        )

    def _prepare_parameters(self, context: TaskContext) -> Dict[str, Any]:
        """
        Prepare parameters for function call.

        Args:
            context: Task execution context

        Returns:
            Dictionary of parameters for function call
        """
        params = {}

        # Add raw_input if function expects it
        params["task"] = context.raw_input

        # Add custom parameters
        if context.parameters:
            params.update(context.parameters)

        return params
