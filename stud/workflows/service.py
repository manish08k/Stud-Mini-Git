from pathlib import Path
from typing import Dict, List, Optional

from ..core.exceptions import StudError
from .runner import WorkflowResult, WorkflowRunner
from .schema import Workflow, WorkflowSchemaError
from .secrets import SecretsStore
from .triggers import TriggerEvent, workflow_matches

WORKFLOWS_DIR = ".stud/workflows"


class WorkflowServiceError(StudError):
    pass


class WorkflowService:
    def __init__(self, project_dir: Path, secrets_dir: Optional[Path] = None,
                  env: Optional[Dict[str, str]] = None):
        self.project_dir = Path(project_dir)
        self.workflows_dir = self.project_dir / WORKFLOWS_DIR
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

        secrets_path = secrets_dir or self.project_dir / ".stud" / "secrets"
        self.secrets = SecretsStore(secrets_path)
        self.base_env = env or {}

    # -- workflow files -------------------------------------------------------

    def list_workflows(self) -> List[str]:
        return sorted(
            p.stem for p in self.workflows_dir.glob("*.yml")
        ) + sorted(
            p.stem for p in self.workflows_dir.glob("*.yaml")
        )

    def load_workflow(self, name: str) -> Workflow:
        for ext in (".yml", ".yaml"):
            path = self.workflows_dir / (name + ext)
            if path.exists():
                return Workflow.load(path)
        raise WorkflowServiceError(f"workflow not found: {name}")

    def save_workflow(self, workflow: Workflow, name: Optional[str] = None) -> Path:
        filename = (name or workflow.name) + ".yml"
        path = self.workflows_dir / filename
        workflow.save(path)
        return path

    def delete_workflow(self, name: str) -> None:
        for ext in (".yml", ".yaml"):
            path = self.workflows_dir / (name + ext)
            if path.exists():
                path.unlink()
                return
        raise WorkflowServiceError(f"workflow not found: {name}")

    # -- execution -----------------------------------------------------------

    def run(self, name: str, extra_env: Optional[Dict[str, str]] = None,
            timeout: Optional[float] = None) -> WorkflowResult:
        workflow = self.load_workflow(name)
        env = {**self.base_env, **(extra_env or {})}
        runner = WorkflowRunner(str(self.project_dir), env=env,
                                 secrets=self.secrets, timeout=timeout)
        return runner.run(workflow)

    def run_workflow(self, workflow: Workflow, extra_env: Optional[Dict[str, str]] = None,
                     timeout: Optional[float] = None) -> WorkflowResult:
        env = {**self.base_env, **(extra_env or {})}
        runner = WorkflowRunner(str(self.project_dir), env=env,
                                 secrets=self.secrets, timeout=timeout)
        return runner.run(workflow)

    # -- event dispatch ------------------------------------------------------

    def dispatch(self, event: TriggerEvent,
                 timeout: Optional[float] = None) -> Dict[str, WorkflowResult]:
        results: Dict[str, WorkflowResult] = {}
        for name in self.list_workflows():
            try:
                wf = self.load_workflow(name)
            except (WorkflowSchemaError, WorkflowServiceError):
                continue
            if workflow_matches(wf.on, event):
                results[name] = self.run_workflow(wf, timeout=timeout)
        return results

    # -- secrets ------------------------------------------------------------

    def set_secret(self, name: str, value: str) -> None:
        self.secrets.set(name, value)

    def delete_secret(self, name: str) -> None:
        self.secrets.delete(name)

    def list_secrets(self) -> List[str]:
        return self.secrets.list()
