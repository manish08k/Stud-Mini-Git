import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .exceptions import ConfigError

CONFIG_FILENAME = "stud.json"
GLOBAL_CONFIG_DIR_ENV = "STUD_CONFIG_DIR"


def _default_global_config_dir() -> Path:
    env = os.environ.get(GLOBAL_CONFIG_DIR_ENV)
    if env:
        return Path(env)
    if os.name == "nt":
        base = os.environ.get("APPDATA", str(Path.home()))
        return Path(base) / "stud"
    return Path.home() / ".config" / "stud"


@dataclass
class ProjectConfig:
    name: str = "unnamed"
    version: str = "0.1.0"
    description: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)
    dev_dependencies: Dict[str, str] = field(default_factory=dict)
    scripts: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "ProjectConfig":
        path = Path(path)
        if not path.exists():
            raise ConfigError(f"config file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"invalid JSON in {path}: {e}") from e

        known = {f for f in cls.__dataclass_fields__ if f != "extra"}
        kwargs = {k: v for k, v in raw.items() if k in known}
        extra = {k: v for k, v in raw.items() if k not in known}
        return cls(**kwargs, extra=extra)

    def save(self, path: Path) -> None:
        path = Path(path)
        data = asdict(self)
        extra = data.pop("extra", {})
        data.update(extra)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")

    @classmethod
    def find_and_load(cls, start: Optional[Path] = None) -> "ProjectConfig":
        start = Path(start or Path.cwd()).resolve()
        for d in (start, *start.parents):
            candidate = d / CONFIG_FILENAME
            if candidate.exists():
                return cls.load(candidate)
        raise ConfigError(f"no {CONFIG_FILENAME} found in {start} or its parents")


@dataclass
class GlobalConfig:
    registry_url: str = "https://registry.stud.dev"
    telemetry: bool = False
    default_ai_provider: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "GlobalConfig":
        path = Path(path) if path else (_default_global_config_dir() / "config.json")
        if not path.exists():
            return cls()

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"invalid JSON in {path}: {e}") from e

        known = {f for f in cls.__dataclass_fields__ if f != "extra"}
        kwargs = {k: v for k, v in raw.items() if k in known}
        extra = {k: v for k, v in raw.items() if k not in known}
        return cls(**kwargs, extra=extra)

    def save(self, path: Optional[Path] = None) -> None:
        path = Path(path) if path else (_default_global_config_dir() / "config.json")
        data = asdict(self)
        extra = data.pop("extra", {})
        data.update(extra)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
