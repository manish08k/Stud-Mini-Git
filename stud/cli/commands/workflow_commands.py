import argparse
from pathlib import Path

from ...core.exceptions import StudError
from ...workflows.schema import Workflow
from ...workflows.service import WorkflowService
from ..ui import get_ui


def cmd_run(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = WorkflowService(Path.cwd())
    try:
        result = svc.run(args.workflow, env=dict(e.split("=", 1) for e in (args.env or [])))
        if result.success:
            ui.success(f"Workflow '{args.workflow}' completed in {result.duration:.1f}s")
            return 0
        else:
            ui.error(f"Workflow '{args.workflow}' failed: {result.error}")
            return 1
    except StudError as e:
        ui.error(str(e))
        return 1


def cmd_list_workflows(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = WorkflowService(Path.cwd())
    workflows = svc.list_workflows()
    if not workflows:
        ui.print("No workflows found.")
        return 0
    for wf in workflows:
        triggers = ", ".join(wf.on.keys())
        jobs = ", ".join(wf.jobs.keys())
        ui.print(f"  {wf.name}  triggers=[{triggers}]  jobs=[{jobs}]")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    ui = get_ui()
    try:
        wf = Workflow.load(Path(args.file))
        ui.success(f"Workflow '{wf.name}' is valid ({len(wf.jobs)} job(s))")
        return 0
    except Exception as e:
        ui.error(str(e))
        return 1


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("run", help="Run a workflow")
    p.add_argument("workflow", help="Workflow name or path")
    p.add_argument("-e", "--env", nargs="*", metavar="KEY=VALUE")
    p.set_defaults(func=cmd_run)

    p = subparsers.add_parser("workflows", help="List available workflows")
    p.set_defaults(func=cmd_list_workflows)

    p = subparsers.add_parser("validate", help="Validate a workflow file")
    p.add_argument("file")
    p.set_defaults(func=cmd_validate)
