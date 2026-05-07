"""
LLM Executor - Executes LLM generation via LiteLLM

Implements BaseExecutor interface.
Calls LiteLLM API, NOT Python code.

Author: AI-OS Architecture v3.1
Date: 2026-03-03
"""

import httpx
from typing import Any, Dict

from execution.execution_dispatcher import BaseExecutor, ExecutionResult, TaskContext
from execution.capability_contract import SkillCapability


# =============================================================================
# Configuration
# =============================================================================

LITELLM_URL = "http://litellm:4000/v1/chat/completions"
LITELLM_API_KEY = "sk-1234"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TIMEOUT = 30.0


# =============================================================================
# Executor
# =============================================================================

class LLMExecutor(BaseExecutor):
    """
    Executes tasks via LLM through LiteLLM.

    Design:
    - Calls LiteLLM chat completions API
    - Passes task as user message
    - Returns text generation result

    Error handling:
    - Catches HTTP errors
    - Catches timeout errors
    - Returns success=False with error message
    """

    def __init__(
        self,
        litellm_url: str = LITELLM_URL,
        api_key: str = LITELLM_API_KEY,
        default_model: str = DEFAULT_MODEL,
        default_max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float = DEFAULT_TIMEOUT
    ):
        """
        Initialize LLM executor.

        Args:
            litellm_url: LiteLLM API endpoint
            api_key: API key for authentication
            default_model: Default model to use
            default_max_tokens: Default max tokens for generation
            timeout: Request timeout in seconds
        """
        self.litellm_url = litellm_url
        self.api_key = api_key
        self.default_model = default_model
        self.default_max_tokens = default_max_tokens
        self.timeout = timeout

    def execute(self, capability: SkillCapability, context: TaskContext) -> ExecutionResult:
        """
        Execute task via LLM.

        Args:
            capability: Selected capability from Router
            context: Task execution context

        Returns:
            ExecutionResult with LLM generation result
        """
        try:
            # Step 1: Prepare request
            model = self._get_model(context)
            max_tokens = self._get_max_tokens(context)

            # Step 2: Call LiteLLM
            response = self._call_llm(
                task=context.raw_input,
                model=model,
                max_tokens=max_tokens
            )

            # Step 3: Extract output
            output = self._extract_response(response)

            # Step 4: Return success result
            return ExecutionResult(
                success=True,
                side_effect_committed=False,  # LLM has no external side effects
                output=output,
                error=None,
                executor_type="llm",
                capability_name=capability.name,
                metadata={
                    "executor": "llm",
                    "model": model,
                    "tokens_used": response.get("usage", {}).get("total_tokens", 0)
                }
            )

        except httpx.TimeoutException as e:
            # Timeout error - no side effects (LLM call failed)
            return ExecutionResult(
                success=False,
                side_effect_committed=False,  # LLM timeout = no side effect
                output=None,
                error=f"LLM request timeout after {self.timeout}s",
                executor_type="llm",
                capability_name=capability.name,
                metadata={"executor": "llm", "error_type": "timeout"}
            )

        except httpx.HTTPStatusError as e:
            # HTTP error (4xx, 5xx) - no side effects (LLM call failed)
            return ExecutionResult(
                success=False,
                side_effect_committed=False,  # LLM error = no side effect
                output=None,
                error=f"LLM request failed: {e.response.status_code} {e.response.reason_phrase}",
                executor_type="llm",
                capability_name=capability.name,
                metadata={
                    "executor": "llm",
                    "error_type": "http_error",
                    "status_code": e.response.status_code
                }
            )

        except Exception as e:
            # Other errors - no side effects (LLM call failed)
            return ExecutionResult(
                success=False,
                side_effect_committed=False,  # LLM error = no side effect
                output=None,
                error=f"LLM execution failed: {str(e)}",
                executor_type="llm",
                capability_name=capability.name,
                metadata={"executor": "llm", "error_type": "unknown"}
            )

    def _get_model(self, context: TaskContext) -> str:
        """
        Get model from context or use default.

        Args:
            context: Task execution context

        Returns:
            Model name
        """
        return context.parameters.get("model", self.default_model)

    def _get_max_tokens(self, context: TaskContext) -> int:
        """
        Get max_tokens from context or use default.

        Args:
            context: Task execution context

        Returns:
            Max tokens for generation
        """
        return context.parameters.get("max_tokens", self.default_max_tokens)

    def _call_llm(self, task: str, model: str, max_tokens: int) -> Dict[str, Any]:
        """
        Call LiteLLM API.

        Args:
            task: User task text
            model: Model name
            max_tokens: Max tokens for generation

        Returns:
            API response dict
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.litellm_url,
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": task}
                    ],
                    "max_tokens": max_tokens
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            return response.json()

    def _extract_response(self, response: Dict[str, Any]) -> str:
        """
        Extract text content from LLM response.

        Args:
            response: Raw API response

        Returns:
            Generated text content
        """
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Invalid LLM response format: {e}")
