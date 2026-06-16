import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.exceptions import StudError
from .schema import Job, Step, Workflow
from .secrets import SecretsStore


class RunnerError(StudError):
    pass


@dataclass
class StepResult:
    name: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0
    skipped: bool = False

    @property
    def success(self) -> bool:
        return self.skipped or self.exit_code == 0


@dataclass
class JobResult:
    name: str
    steps: List[StepResult] = field(default_factory=list)
    duration: float = 0.0

    @property
    def success(self) -> bool:
        return all(s.success or s.name == "skipped" for s in self.steps)

    @property
    def exit_code(self) -> int:
        for s in self.steps:
            if not s.success:
                return s.exit_code
        return 0


@dataclass
class WorkflowResult:
    workflow_name: str
    jobs: List[JobResult] = field(default_factory=list)
    duration: float = 0.0

    @property
    def success(self) -> bool:
        return all(j.success for j in self.jobs)


class StepRunner:
    def __init__(self, work_dir: str, env: Dict[str, str], timeout: Optional[float] = None):
        self.work_dir = work_dir
        self.env = env
        self.timeout = timeout

    def run_step(self, step: Step) -> StepResult:
        if step.if_ is not None:
            evaluated = self._eval_condition(step.if_)
            if not evaluated:
                return StepResult(name=step.name, skipped=True)

        step_env = {**self.env, **step.env}

        if step.run:
            return self._run_shell(step, step_env)
        if step.uses:
            return self._run_action(step, step_env)

        return StepResult(name=step.name, exit_code=1, stderr="step has no 'run' or 'uses'")

    def _eval_condition(self, condition: str) -> bool:
        safe_globals = {"__builtins__": {}}
        safe_locals = {k.replace("-", "_"): v for k, v in self.env.items()}
        try:
            return bool(eval(condition, safe_globals, safe_locals))  # noqa: S307
        except Exception:
            return False

    def _run_shell(self, step: Step, env: Dict[str, str]) -> StepResult:
        start = time.monotonic()
        try:
            result = subprocess.run(
                step.run,
                shell=True,
                cwd=self.work_dir,
                env={**os.environ, **env},
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            duration = time.monotonic() - start
            return StepResult(
                name=step.name,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                name=step.name,
                exit_code=124,
                stderr=f"step timed out after {self.timeout}s",
                duration=time.monotonic() - start,
            )
        except Exception as e:
            return StepResult(
                name=step.name,
                exit_code=1,
                stderr=str(e),
                duration=time.monotonic() - start,
            )

    def _run_action(self, step: Step, env: Dict[str, str]) -> StepResult:
        start = time.monotonic()
        uses = step.uses
        action_env = {**env, **{f"INPUT_{k.upper()}": str(v) for k, v in step.with_.items()}}
        action_path = os.path.join(self.work_dir, ".stud", "actions", uses, "action.sh")
        if not os.path.exists(action_path):
            return StepResult(
                name=step.name,
                exit_code=1,
                stderr=f"action not found: {uses} (expected {action_path})",
                duration=time.monotonic() - start,
            )
        result = subprocess.run(
            ["bash", action_path],
            cwd=self.work_dir,
            env={**os.environ, **action_env},
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        return StepResult(
            name=step.name,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration=time.monotonic() - start,
        )


class JobRunner:
    def __init__(self, work_dir: str, global_env: Dict[str, str],
                  secrets: Optional[SecretsStore] = None, timeout: Optional[float] = None):
        self.work_dir = work_dir
        self.global_env = global_env
        self.secrets = secrets
        self.timeout = timeout

    def run_job(self, job: Job) -> JobResult:
        start = time.monotonic()
        secret_env = self.secrets.as_env() if self.secrets else {}
        env = {**self.global_env, **secret_env, **job.env}
        step_runner = StepRunner(self.work_dir, env, timeout=self.timeout)

        results: List[StepResult] = []
        for step in job.steps:
            result = step_runner.run_step(step)
            results.append(result)
            if not result.success and not step.continue_on_error:
                break

        return JobResult(name=job.name, steps=results, duration=time.monotonic() - start)


class WorkflowRunner:
    def __init__(self, work_dir: str, env: Optional[Dict[str, str]] = None,
                  secrets: Optional[SecretsStore] = None, timeout: Optional[float] = None):
        self.work_dir = work_dir
        self.base_env = env or {}
        self.secrets = secrets
        self.timeout = timeout

    def run(self, workflow: Workflow) -> WorkflowResult:
        start = time.monotonic()
        global_env = {**self.base_env, **workflow.env}
        completed: Dict[str, JobResult] = {}
        waves = workflow.execution_order()

        for wave in waves:
            for job_name in wave:
                job = workflow.jobs[job_name]
                if any(not completed[dep].success for dep in job.needs if dep in completed):
                    results = [StepResult(name=s.name, skipped=True) for s in job.steps]
                    completed[job_name] = JobResult(name=job_name, steps=results)
                    continue

                runner = JobRunner(
                    self.work_dir,
                    {**global_env, "STUD_JOB_NAME": job_name},
                    secrets=self.secrets,
                    timeout=self.timeout,
                )
                result = runner.run_job(job)
                completed[job_name] = result

        return WorkflowResult(
            workflow_name=workflow.name,
            jobs=list(completed.values()),
            duration=time.monotonic() - start,
        )
