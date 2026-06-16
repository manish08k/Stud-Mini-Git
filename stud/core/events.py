from collections import defaultdict
from typing import Any, Callable, DefaultDict, List, Optional

from .exceptions import EventError

Handler = Callable[..., None]


class EventBus:
    """Simple synchronous publish/subscribe event bus."""

    def __init__(self):
        self._handlers: DefaultDict[str, List[Handler]] = defaultdict(list)

    def on(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    def off(self, event: str, handler: Handler) -> None:
        try:
            self._handlers[event].remove(handler)
        except ValueError:
            raise EventError(f"handler not registered for event {event!r}")

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        for handler in list(self._handlers.get(event, [])):
            handler(*args, **kwargs)

    def clear(self, event: Optional[str] = None) -> None:
        if event is None:
            self._handlers.clear()
        else:
            self._handlers.pop(event, None)


_global_bus = EventBus()


def get_event_bus() -> EventBus:
    return _global_bus
