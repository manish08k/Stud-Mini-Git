import subprocess
from pathlib import Path

from ..deploy import DeployConfig, DeployResult


class AngularTarget:
    def __init__(self, config: DeployConfig):
        self.config = config

    def build(self) -> DeployResult:
        project_dir = Path(self.config.project_dir)
        output_dir = self.config.output_dir or project_dir / "dist"
        logs = []

        install = subprocess.run(
            ["npm", "install"],
            cwd=str(project_dir), capture_output=True, text=True,
        )
        logs.append(install.stdout)
        if install.returncode != 0:
            return DeployResult(success=False, logs="\n".join(logs), error=install.stderr)

        build = subprocess.run(
            ["npx", "ng", "build", "--output-path", str(output_dir)],
            cwd=str(project_dir), capture_output=True, text=True,
        )
        logs.append(build.stdout)
        if build.returncode != 0:
            return DeployResult(success=False, logs="\n".join(logs), error=build.stderr)

        logs.append(f"Angular build complete -> {output_dir}")
        return DeployResult(success=True, output_dir=output_dir, logs="\n".join(logs))
