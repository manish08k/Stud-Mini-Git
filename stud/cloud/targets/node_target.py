import json
import shutil
import subprocess
from pathlib import Path

from ..deploy import DeployConfig, DeployResult


class NodeTarget:
    def __init__(self, config: DeployConfig):
        self.config = config

    def build(self) -> DeployResult:
        project_dir = Path(self.config.project_dir)
        output_dir = self.config.output_dir or project_dir / "dist"
        output_dir.mkdir(parents=True, exist_ok=True)
        logs = []

        pkg_json = project_dir / "package.json"
        if pkg_json.exists():
            with open(pkg_json) as f:
                pkg = json.load(f)
            build_script = pkg.get("scripts", {}).get("build")
            if build_script:
                result = subprocess.run(
                    ["npm", "run", "build"],
                    cwd=str(project_dir), capture_output=True, text=True,
                )
                logs.append(result.stdout)
                if result.returncode != 0:
                    return DeployResult(success=False, logs="\n".join(logs), error=result.stderr)

        built = project_dir / "dist"
        if built.exists() and built != output_dir:
            shutil.copytree(built, output_dir, dirs_exist_ok=True)

        logs.append(f"Node build complete -> {output_dir}")
        return DeployResult(success=True, output_dir=output_dir, logs="\n".join(logs))
