from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..core.exceptions import StudError


class WorkflowSchemaError(StudError):
    pass


@dataclass
class Step:
    name: str
    run: Optional[str] = None
    uses: Optional[str] = None
    with_: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)
    if_: Optional[str] = None
    continue_on_error: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "Step":
        if "run" not in data and "uses" not in data:
            raise WorkflowSchemaError(
                f"step {data.get('name', '<unnamed>')!r} must have 'run' or 'uses'"
            )
        return cls(
            name=data.get("name", data.get("run") or data.get("uses") or "step"),
            run=data.get("run"),
            uses=data.get("uses"),
            with_=data.get("with", {}),
            env=data.get("env", {}),
            if_=data.get("if"),
            continue_on_error=bool(data.get("continue-on-error", False)),
        )

    def to_dict(self) -> dict:
        out: Dict[str, Any] = {"name": self.name}
        if self.run is not None:
            out["run"] = self.run
        if self.uses is not None:
            out["uses"] = self.uses
        if self.with_:
            out["with"] = self.with_
        if self.env:
            out["env"] = self.env
        if self.if_ is not None:
            out["if"] = self.if_
        if self.continue_on_error:
            out["continue-on-error"] = True
        return out


@dataclass
class Job:
    name: str
    steps: List[Step] = field(default_factory=list)
    runs_on: str = "local"
    needs: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "Job":
        steps_data = data.get("steps") or []
        if not steps_data:
            raise WorkflowSchemaError(f"job {name!r} has no steps")

        needs = data.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]

        return cls(
            name=name,
            steps=[Step.from_dict(s) for s in steps_data],
            runs_on=data.get("runs-on", "local"),
            needs=list(needs),
            env=data.get("env", {}),
        )

    def to_dict(self) -> dict:
        out: Dict[str, Any] = {"runs-on": self.runs_on, "steps": [s.to_dict() for s in self.steps]}
        if self.needs:
            out["needs"] = self.needs
        if self.env:
            out["env"] = self.env
        return out


@dataclass
class Workflow:
    name: str
    on: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)
    jobs: Dict[str, Job] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "Workflow":
        if not data.get("jobs"):
            raise WorkflowSchemaError("workflow must define at least one job")

        on = data.get("on", {})
        if isinstance(on, str):
            on = {on: {}}
        elif isinstance(on, list):
            on = {trigger: {} for trigger in on}
        elif on is None:
            on = {}

        on = {k: (v or {}) for k, v in on.items()}

        jobs = {name: Job.from_dict(name, job_data or {}) for name, job_data in data["jobs"].items()}
        cls._validate_dag(jobs)

        return cls(
            name=data.get("name", "workflow"),
            on=on,
            env=data.get("env", {}),
            jobs=jobs,
        )

    @staticmethod
    def _validate_dag(jobs: Dict[str, "Job"]) -> None:
        for job_name, job in jobs.items():
            for dep in job.needs:
                if dep not in jobs:
                    raise WorkflowSchemaError(f"job {job_name!r} needs unknown job {dep!r}")

        visiting: set = set()
        visited: set = set()

        def visit(name: str, path: List[str]) -> None:
            if name in visited:
                return
            if name in visiting:
                raise WorkflowSchemaError(f"cyclic job dependency: {' -> '.join(path + [name])}")
            visiting.add(name)
            for dep in jobs[name].needs:
                visit(dep, path + [name])
            visiting.discard(name)
            visited.add(name)

        for job_name in jobs:
            visit(job_name, [])

    def execution_order(self) -> List[List[str]]:
        """Group jobs into sequential 'waves' that can each run in parallel."""
        remaining = dict(self.jobs)
        completed: set = set()
        waves: List[List[str]] = []

        while remaining:
            wave = [
                name for name, job in remaining.items()
                if all(dep in completed for dep in job.needs)
            ]
            if not wave:
                raise WorkflowSchemaError("unable to resolve job execution order (cycle?)")
            waves.append(sorted(wave))
            for name in wave:
                completed.add(name)
                del remaining[name]

        return waves

    @classmethod
    def load(cls, path: Path) -> "Workflow":
        path = Path(path)
        if not path.exists():
            raise WorkflowSchemaError(f"workflow file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise WorkflowSchemaError(f"workflow file {path} must contain a mapping")
        return cls.from_dict(data)

    @classmethod
    def from_yaml(cls, text: str) -> "Workflow":
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise WorkflowSchemaError("workflow YAML must contain a mapping")
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "on": self.on,
            "env": self.env,
            "jobs": {name: job.to_dict() for name, job in self.jobs.items()},
        }

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_yaml(), encoding="utf-8")
