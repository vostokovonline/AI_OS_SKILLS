"""
Arbitration Log - Decision trace for learning and analysis.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class ArbitrationLog(Protocol):
    """
    Decision trace storage.

    Records arbitration outcomes for:
        - Learning (future ML)
        - Analysis (dashboard visualization)
        - Audit (why was X rejected?)
        - MCP reasoning (decision history)
    """

    async def record(
        self,
        result: "application.arbitration.arbitration_result.ArbitrationResult"
    ) -> None:
        """
        Record arbitration decision.

        Args:
            result: Arbitration outcome to log
        """
        ...


class NoopArbitrationLog:
    """
    No-op log (placeholder).

    TODO: Replace with implementations that:
        - Store to database for dashboard
        - Feed semantic memory for learning
        - Provide decision audit trail
        - Enable MCP reasoning over history
    """

    async def record(
        self,
        result: "application.arbitration.arbitration_result.ArbitrationResult"
    ) -> None:
        """No-op logging."""
        pass


class InMemoryArbitrationLog:
    """
    In-memory log for testing/dashboard.

    Keeps last N decisions in memory for API access.
    """

    def __init__(self, max_size: int = 100):
        self._history: list = []
        self._max_size = max_size

    async def record(
        self,
        result: "application.arbitration.arbitration_result.ArbitrationResult"
    ) -> None:
        """Store result in circular buffer."""
        self._history.append(result)
        if len(self._history) > self._max_size:
            self._history.pop(0)

    def get_recent(self, limit: int = 10) -> list:
        """Get recent decisions."""
        return self._history[-limit:]

    def get_latest(self) -> "application.arbitration.arbitration_result.ArbitrationResult | None":
        """Get most recent decision."""
        return self._history[-1] if self._history else None
