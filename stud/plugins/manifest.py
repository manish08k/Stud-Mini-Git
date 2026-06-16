import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from ..core.exceptions import StudError

PLUGIN_MANIFEST_FILENAME = "plugin.json"


class PluginManifestError(StudError):
    pass


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str = ""
    author: str = ""
    entry_point: str = "plugin:Plugin"
    commands: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.name:
            raise PluginManifestError("plugin name is required")
        if not self.version:
            raise PluginManifestError("plugin version is required")
        if ":" not in self.entry_point:
            raise PluginManifestError(
                f"entry_point must be 'module:ClassName', got {self.entry_point!r}"
            )

    @classmethod
    def load(cls, path: Path) -> "PluginManifest":
        path = Path(path)
        if not path.exists():
            raise PluginManifestError(f"plugin manifest not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        known = {f for f in cls.__dataclass_fields__ if f != "extra"}
        kwargs = {k: v for k, v in raw.items() if k in known}
        extra = {k: v for k, v in raw.items() if k not in known}
        manifest = cls(**kwargs, extra=extra)
        manifest.validate()
        return manifest

    def save(self, path: Path) -> None:
        self.validate()
        path = Path(path)
        data = asdict(self)
        extra = data.pop("extra", {})
        data.update(extra)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
