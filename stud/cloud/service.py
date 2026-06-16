from pathlib import Path
from typing import Any, Dict, Optional

from .deploy import DeployConfig, DeployResult, Deployer


class CloudService:
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)

    def deploy(self, target: str, output_dir: Optional[Path] = None,
               env: Optional[Dict[str, str]] = None,
               options: Optional[Dict[str, Any]] = None) -> DeployResult:
        config = DeployConfig(
            target=target,
            project_dir=self.project_dir,
            output_dir=output_dir,
            env=env or {},
            options=options or {},
        )
        return Deployer(config).deploy()
