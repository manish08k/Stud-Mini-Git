import subprocess
from pathlib import Path

from ..deploy import DeployConfig, DeployResult


class FlutterWebTarget:
    def __init__(self, config: DeployConfig):
        self.config = config

    def build(self) -> DeployResult:
        project_dir = Path(self.config.project_dir)
        output_dir = self.config.output_dir or project_dir / "build" / "web"
        logs = []

        result = subprocess.run(
            ["flutter", "build", "web", "--output", str(output_dir)],
            cwd=str(project_dir), capture_output=True, text=True,
        )
        logs.append(result.stdout)
        if result.returncode != 0:
            return DeployResult(success=False, logs="\n".join(logs), error=result.stderr)

        logs.append(f"Flutter web build complete -> {output_dir}")
        return DeployResult(success=True, output_dir=output_dir, logs="\n".join(logs))
