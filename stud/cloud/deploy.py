import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from ..core.exceptions import StudError


class DeployError(StudError):
    pass


@dataclass
class DeployConfig:
    target: str
    project_dir: Path
    output_dir: Optional[Path] = None
    env: Dict[str, str] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeployResult:
    success: bool
    url: Optional[str] = None
    output_dir: Optional[Path] = None
    logs: str = ""
    error: Optional[str] = None


class Deployer:
    """Orchestrates deployment to a configured target."""

    def __init__(self, config: DeployConfig):
        self.config = config

    def deploy(self) -> DeployResult:
        from .targets.python_target import PythonTarget
        from .targets.node_target import NodeTarget
        from .targets.react_target import ReactTarget
        from .targets.angular_target import AngularTarget
        from .targets.flutter_web_target import FlutterWebTarget

        targets = {
            "python": PythonTarget,
            "node": NodeTarget,
            "react": ReactTarget,
            "angular": AngularTarget,
            "flutter-web": FlutterWebTarget,
        }

        cls = targets.get(self.config.target)
        if cls is None:
            raise DeployError(f"unknown target: {self.config.target!r}")

        target = cls(self.config)
        return target.build()
