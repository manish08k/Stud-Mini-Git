from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class PluginContext:
    plugin_name: str
    config: Dict[str, Any] = field(default_factory=dict)
    _hooks: Dict[str, List[Callable]] = field(default_factory=dict, repr=False)

    def on(self, event: str, handler: Callable) -> None:
        self._hooks.setdefault(event, []).append(handler)

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        for handler in self._hooks.get(event, []):
            handler(*args, **kwargs)

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)


class Plugin:
    """Base class for all Stud plugins."""
    name: str = ""
    version: str = "0.1.0"
    description: str = ""

    def setup(self, ctx: PluginContext) -> None:
        pass

    def teardown(self, ctx: PluginContext) -> None:
        pass


@dataclass
class Command:
    name: str
    help: str
    handler: Callable
    args: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PluginManifestMeta:
    name: str
    version: str
    description: str = ""
    author: str = ""
    entry_point: str = "plugin:Plugin"
    commands: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)


def hook(event: str):
    """Decorator to mark a Plugin method as a hook handler for a given event."""
    def decorator(fn: Callable) -> Callable:
        fn._stud_hook_event = event
        return fn
    return decorator
