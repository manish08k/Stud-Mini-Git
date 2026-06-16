import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TriggerEvent:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)


class Trigger:
    def matches(self, event: TriggerEvent) -> bool:
        raise NotImplementedError


class PushTrigger(Trigger):
    def __init__(self, config: Dict[str, Any]):
        self.branches: List[str] = config.get("branches", ["*"])
        self.paths: List[str] = config.get("paths", [])
        self.tags: List[str] = config.get("tags", [])

    def _glob_match(self, pattern: str, value: str) -> bool:
        regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        return bool(re.fullmatch(regex, value))

    def matches(self, event: TriggerEvent) -> bool:
        if event.type != "push":
            return False
        branch = event.payload.get("branch", "")
        if self.branches:
            if not any(self._glob_match(p, branch) for p in self.branches):
                return False
        if self.paths:
            changed = event.payload.get("changed_paths", [])
            if not any(
                self._glob_match(p, fp) for p in self.paths for fp in changed
            ):
                return False
        if self.tags:
            tag = event.payload.get("tag", "")
            if not any(self._glob_match(p, tag) for p in self.tags):
                return False
        return True


class CommitTrigger(Trigger):
    def __init__(self, config: Dict[str, Any]):
        self.branches: List[str] = config.get("branches", ["*"])

    def matches(self, event: TriggerEvent) -> bool:
        if event.type != "commit":
            return False
        branch = event.payload.get("branch", "")
        return any(
            re.fullmatch(re.escape(p).replace(r"\*", ".*"), branch)
            for p in self.branches
        )


class ScheduleTrigger(Trigger):
    def __init__(self, config: Dict[str, Any]):
        self.cron: str = config.get("cron", "")

    def matches(self, event: TriggerEvent) -> bool:
        return event.type == "schedule" and event.payload.get("cron") == self.cron


class ManualTrigger(Trigger):
    def __init__(self, config: Dict[str, Any]):
        self.inputs: Dict[str, Any] = config.get("inputs", {})

    def matches(self, event: TriggerEvent) -> bool:
        return event.type == "manual"


_TRIGGER_MAP = {
    "push": PushTrigger,
    "commit": CommitTrigger,
    "schedule": ScheduleTrigger,
    "manual": ManualTrigger,
}


def build_triggers(on: Dict[str, Any]) -> List[Trigger]:
    triggers: List[Trigger] = []
    for name, config in on.items():
        cls = _TRIGGER_MAP.get(name)
        if cls:
            triggers.append(cls(config or {}))
    return triggers


def workflow_matches(on: Dict[str, Any], event: TriggerEvent) -> bool:
    return any(t.matches(event) for t in build_triggers(on))
