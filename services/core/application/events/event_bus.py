"""
LEGACY - DO NOT USE

This module is deprecated.
Use application.events.bus instead.
"""
from typing import Any

def __getattr__(name: str) -> Any:
    raise RuntimeError(
        "Legacy EventBus is forbidden. "
        "Use 'application.events.bus.get_event_bus' instead."
    )


class EventBus:
    def __init__(self):
        raise RuntimeError(
            "Legacy EventBus is forbidden. "
            "Use 'application.events.bus.get_event_bus' instead."
        )


event_bus = None  #type: ignore
