import subprocess
from pathlib import Path

from ..deploy import DeployConfig, DeployError, DeployResult


class PythonTarget:
    def __init__(self, config: DeployConfig):
        self.config = config

    def build(self) -> DeployResult:
        project_dir = Path(self.config.project_dir)
        output_dir = self.config.output_dir or project_dir / "dist"
        output_dir.mkdir(parents=True, exist_ok=True)

        logs = []

        req_file = project_dir / "requirements.txt"
        if req_file.exists():
            result = subprocess.run(
                ["pip", "install", "-r", str(req_file), "--target", str(output_dir / "deps")],
                capture_output=True, text=True,
            )
            logs.append(result.stdout)
            if result.returncode != 0:
                return DeployResult(success=False, logs="\n".join(logs), error=result.stderr)

        for f in project_dir.rglob("*.py"):
            rel = f.relative_to(project_dir)
            dest = output_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(f.read_bytes())

        logs.append(f"Python build complete -> {output_dir}")
        return DeployResult(success=True, output_dir=output_dir, logs="\n".join(logs))
