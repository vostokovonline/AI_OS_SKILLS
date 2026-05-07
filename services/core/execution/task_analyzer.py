"""
TaskAnalyzer - Deterministic text-to-intent classifier

Pure LLM usage with temperature=0.
Does NOT: retry, call executors, access registry, apply fallback.

Depends on: intent_schema.py (TaskIntent, TaskAnalysisResult, MIN_CONFIDENCE_THRESHOLD)

Author: AI-OS Architecture v3.1
Date: 2026-03-03
"""

import json
from typing import Optional

from execution.intent_schema import (
    TaskIntent,
    TaskAnalysisResult,
    MIN_CONFIDENCE_THRESHOLD,
    IntentType,
    InputType,
    OutputType,
    ComplexityLevel
)


# =============================================================================
# Exceptions
# =============================================================================

class InvalidLLMOutputException(Exception):
    """
    LLM returned invalid JSON or schema.

    This is CLASSIFICATION ERROR, not system error.
    Caller may retry with rephrased task.
    """

    def __init__(self, reason: str, raw_output: str):
        self.reason = reason
        self.raw_output = raw_output
        super().__init__(f"Invalid LLM output: {reason}")


class LowConfidenceException(Exception):
    """
    LLM confidence below threshold.

    This is ORCHESTRATION SIGNAL, not error.
    Caller decides: retry, ask user, or fallback.
    """

    def __init__(self, confidence: float, threshold: float):
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(
            f"Confidence {confidence} below threshold {threshold}"
        )


# =============================================================================
# Analyzer
# =============================================================================

class TaskAnalyzer:
    """
    Deterministic text-to-intent classifier.

    WHAT: Converts free-form text to structured TaskIntent
    NOT HOW:
        - No retry logic (orchestration layer handles)
        - No fallback (orchestration layer handles)
        - No decisions (only interprets)

    Design principles:
    - Temperature=0 (deterministic)
    - Pure classifier (text → TaskAnalysisResult)
    - No access to Router/Dispatcher/Registry
    - Exceptions for error signals (not silent failures)
    """

    def __init__(self, llm_client, model: str = "gpt-4o-mini"):
        """
        Initialize analyzer with LLM client.

        Args:
            llm_client: LLM client with generate(prompt, temperature, model) method
            model: Model name to use
        """
        self.llm = llm_client
        self.model = model
        self.temperature = 0  # CRITICAL: deterministic classification

    def analyze(self, task: str) -> TaskAnalysisResult:
        """
        Convert free-form text to structured TaskIntent.

        Args:
            task: User task text

        Returns:
            TaskAnalysisResult with intent structure

        Raises:
            InvalidLLMOutputException: If LLM returns invalid JSON
            LowConfidenceException: If confidence < MIN_CONFIDENCE_THRESHOLD
        """
        # Step 1: Build prompt
        prompt = self._build_prompt(task)

        # Step 2: Call LLM (temperature=0 for determinism)
        response = self._llm_call(prompt)

        # Step 3: Parse JSON response
        intent_data = self._parse_response(response)

        # Step 4: Validate against TaskIntent schema
        intent = TaskIntent(**intent_data)

        # Step 5: Check confidence threshold
        if intent.confidence < MIN_CONFIDENCE_THRESHOLD:
            raise LowConfidenceException(
                confidence=intent.confidence,
                threshold=MIN_CONFIDENCE_THRESHOLD
            )

        # Step 6: Return result
        return TaskAnalysisResult(
            intent=intent,
            raw_task=task,
            analyzer_model=self.model,
            retry_count=0  # Orchestration layer manages retries
        )

    def _build_prompt(self, task: str) -> str:
        """
        Construct deterministic classification prompt.

        Prompt is CRITICAL for temperature=0 determinism.
        """
        return f"""You are a task classifier for AI-OS execution platform.

Extract structured execution requirements from this task:

"{task}"

Return STRICT JSON with these exact fields:
{{
  "intent": "summarize|generate|analyze|transform|store|retrieve|compute",
  "input_type": "text|file|structured|none",
  "output_type": "text|file|structured|artifact",
  "requires_persistence": true|false,
  "requires_external_io": true|false,
  "complexity": "low|medium|high",
  "estimated_tokens": <integer>,
  "confidence": <0.0-1.0>
}}

Rules:
- intent: Must be one of the 7 options above
- input_type/output_type: Must be one of the 4 options each
- confidence: Your confidence in classification (0.0 to 1.0)
- estimated_tokens: Estimated tokens needed for execution
"""

    def _llm_call(self, prompt: str) -> str:
        """
        Call LLM with temperature=0.

        Args:
            prompt: Classification prompt

        Returns:
            LLM response text
        """
        # Delegate to LLM client
        # Expected interface: client.generate(prompt, temperature, model)
        response = self.llm.generate(
            prompt=prompt,
            temperature=self.temperature,
            model=self.model
        )

        return response

    def _parse_response(self, response: str) -> dict:
        """
        Parse LLM response, extract JSON.

        Handles:
        - Plain JSON
        - Markdown code blocks with ```json
        - Markdown code blocks with ```

        Args:
            response: Raw LLM response

        Returns:
            Parsed JSON dict

        Raises:
            InvalidLLMOutputException: If JSON is invalid or missing
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response:
                # Extract from ```json block
                start = response.find("```json") + 7
                end = response.rfind("```")
                response = response[start:end].strip()
            elif "```" in response:
                # Extract from ``` block (no language specified)
                start = response.find("```") + 3
                end = response.rfind("```")
                response = response[start:end].strip()

            # Parse JSON
            data = json.loads(response)

            # Validate required fields
            required_fields = {
                "intent", "input_type", "output_type",
                "requires_persistence", "requires_external_io",
                "complexity", "estimated_tokens", "confidence"
            }

            missing = required_fields - set(data.keys())
            if missing:
                raise InvalidLLMOutputException(
                    reason=f"Missing required fields: {', '.join(missing)}",
                    raw_output=response
                )

            return data

        except json.JSONDecodeError as e:
            raise InvalidLLMOutputException(
                reason=f"Invalid JSON: {str(e)}",
                raw_output=response
            )
        except Exception as e:
            raise InvalidLLMOutputException(
                reason=f"Parse error: {str(e)}",
                raw_output=response
            )
