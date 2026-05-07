"""
Idempotency Contract - Safety guarantees for skill execution

Critical for retry/fallback safety.
Prevents duplicate side effects.

Author: AI-OS Architecture v3.1
Date: 2026-03-03
"""

from enum import Enum
from typing import Set


class IdempotencyLevel(str, Enum):
    """
    Idempotency guarantees for skill execution.

    IMPORTANT: This determines retry/fallback safety.

    SAFE:
    - No side effects at all
    - Multiple calls = acceptable
    - Examples: calculate, echo, analyze, summarize
    - Retry: YES
    - Fallback: YES

    IDEMPOTENT:
    - Side effects are idempotent (same result on repeated calls)
    - Examples: read_file, get_status, check_exists
    - Retry: YES
    - Fallback: YES

    NON_IDEMPOTENT:
    - Side effects create different state on each call
    - Examples: write_file, web_research, send_email
    - Retry: NO (unless idempotency_key is provided)
    - Fallback: NO (unless primary was not executed)

    NOTE: LLM generation is logically SAFE (no external side effects)
    even though results are non-deterministic. Side effects matter,
    not output determinism.
    """
    SAFE = "safe"                       # No side effects
    IDEMPOTENT = "idempotent"           # Idempotent side effects
    NON_IDEMPOTENT = "non_idempotent"  # Non-idempotent side effects


# Retry-safe levels (computed from idempotency)
RETRY_SAFE_LEVELS: Set[IdempotencyLevel] = {
    IdempotencyLevel.SAFE,
    IdempotencyLevel.IDEMPOTENT,
}

# Fallback-safe levels (computed from idempotency)
FALLBACK_SAFE_LEVELS: Set[IdempotencyLevel] = {
    IdempotencyLevel.SAFE,
    IdempotencyLevel.IDEMPOTENT,
}
