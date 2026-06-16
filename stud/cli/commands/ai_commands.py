import argparse
from pathlib import Path

from ...ai.client import LLMClient, LLMError
from ...ai.commit_messages import generate_commit_message
from ...ai.code_review import review_file, review_diff
from ...ai.release_notes import generate_release_notes
from ...ai.workflow_generator import generate_workflow
from ...vcs.service import VCSService
from ..ui import get_ui


def _client(args: argparse.Namespace) -> LLMClient:
    provider = getattr(args, "provider", "anthropic") or "anthropic"
    return LLMClient(provider=provider)


def cmd_ai_commit(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = VCSService(Path.cwd())
    from ...vcs.diff import tree_diff, line_diff
    from ...vcs.objects import Commit

    head = svc.refs.get_head()
    if head is None:
        ui.error("No commits yet")
        return 1

    staged_tree = svc.index.to_tree(svc.objects)
    head_tree = Commit.read(svc.objects, head).tree
    from ...vcs.diff import tree_diff
    diffs = tree_diff(svc.objects, head_tree, staged_tree)
    diff_text = "\n".join(f"{d.status}: {d.path}" for d in diffs)

    try:
        message = generate_commit_message(diff_text, client=_client(args))
        ui.print(f"\nSuggested commit message:\n\n  {message}\n")
        if ui.confirm("Use this message?"):
            oid = svc.commit(message)
            ui.success(f"Committed [{oid[:8]}]")
        return 0
    except LLMError as e:
        ui.error(str(e))
        return 1


def cmd_ai_review(args: argparse.Namespace) -> int:
    ui = get_ui()
    try:
        content = Path(args.file).read_text(encoding="utf-8", errors="ignore")
        review = review_file(args.file, content, client=_client(args))
        ui.panel(review, title=f"Code Review: {args.file}")
        return 0
    except LLMError as e:
        ui.error(str(e))
        return 1


def cmd_ai_release(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = VCSService(Path.cwd())
    commits = svc.log(limit=args.since or 20)
    messages = [c.message for c in commits]
    try:
        notes = generate_release_notes(messages, args.version or "next", client=_client(args))
        ui.panel(notes, title="Release Notes")
        return 0
    except LLMError as e:
        ui.error(str(e))
        return 1


def cmd_ai_workflow(args: argparse.Namespace) -> int:
    ui = get_ui()
    try:
        yaml_text = generate_workflow(args.description, client=_client(args))
        ui.print(yaml_text)
        if args.output:
            Path(args.output).write_text(yaml_text, encoding="utf-8")
            ui.success(f"Saved to {args.output}")
        return 0
    except LLMError as e:
        ui.error(str(e))
        return 1


def register(subparsers: argparse._SubParsersAction) -> None:
    ai = subparsers.add_parser("ai", help="AI-powered commands")
    ai_sub = ai.add_subparsers(dest="ai_command")

    p = ai_sub.add_parser("commit", help="Generate commit message from staged diff")
    p.add_argument("--provider", default="anthropic")
    p.set_defaults(func=cmd_ai_commit)

    p = ai_sub.add_parser("review", help="AI code review of a file")
    p.add_argument("file")
    p.add_argument("--provider", default="anthropic")
    p.set_defaults(func=cmd_ai_review)

    p = ai_sub.add_parser("release", help="Generate release notes from commit history")
    p.add_argument("--version", default="next")
    p.add_argument("--since", type=int, default=20)
    p.add_argument("--provider", default="anthropic")
    p.set_defaults(func=cmd_ai_release)

    p = ai_sub.add_parser("workflow", help="Generate workflow YAML from description")
    p.add_argument("description")
    p.add_argument("--output", "-o")
    p.add_argument("--provider", default="anthropic")
    p.set_defaults(func=cmd_ai_workflow)

    def cmd_ai_help(args):
        ai.print_help()
        return 0

    ai.set_defaults(func=cmd_ai_help)
