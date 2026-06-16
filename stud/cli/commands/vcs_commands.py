import argparse
from pathlib import Path
from typing import Optional

from ...vcs.service import VCSService
from ...core.exceptions import StudError
from ..ui import get_ui
from ..wizards import init_wizard


def _get_svc(path: Optional[Path] = None) -> VCSService:
    return VCSService(Path(path or Path.cwd()))


def cmd_init(args: argparse.Namespace) -> int:
    ui = get_ui()
    if args.no_wizard:
        svc = VCSService.init(Path(args.directory or Path.cwd()))
        ui.success(f"Initialized repository in {svc.stud_dir}")
    else:
        init_wizard(args.directory)
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    paths = args.paths or None
    staged = svc.add(paths)
    for p in staged:
        ui.print(f"  staged: {p}")
    ui.success(f"{len(staged)} file(s) staged")
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    try:
        oid = svc.commit(args.message, author=args.author or "user <user@example.com>")
        ui.success(f"[{oid[:8]}] {args.message}")
        return 0
    except StudError as e:
        ui.error(str(e))
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    status = svc.status()
    any_changes = False
    for category, paths in status.items():
        if paths:
            any_changes = True
            ui.print(f"\n{category.replace('_', ' ')}:")
            for p in paths:
                ui.print(f"  {p}")
    if not any_changes:
        ui.print("nothing to commit, working tree clean")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    commits = svc.log(limit=args.limit)
    if not commits:
        ui.print("No commits yet.")
        return 0
    for commit in commits:
        oid = svc.refs.get_head() or ""
        ui.print(f"\ncommit (unknown)")
        ui.print(f"Author: {commit.author}")
        ui.print(f"Message: {commit.message}")
    return 0


def cmd_branch(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    if args.name:
        try:
            svc.create_branch(args.name, args.start)
            ui.success(f"Branch '{args.name}' created")
        except StudError as e:
            ui.error(str(e))
            return 1
    elif args.delete:
        try:
            svc.refs.delete_branch(args.delete)
            ui.success(f"Branch '{args.delete}' deleted")
        except StudError as e:
            ui.error(str(e))
            return 1
    else:
        current = svc.refs.current_branch()
        for b in svc.refs.list_branches():
            prefix = "* " if b == current else "  "
            ui.print(f"{prefix}{b}")
    return 0


def cmd_checkout(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    try:
        svc.checkout(args.target)
        ui.success(f"Switched to '{args.target}'")
        return 0
    except StudError as e:
        ui.error(str(e))
        return 1


def cmd_merge(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    try:
        result = svc.merge(args.branch)
        if result.conflicts:
            ui.warn(f"Merge completed with conflicts in: {', '.join(result.conflicts)}")
            return 1
        ui.success(f"Merged '{args.branch}'")
        return 0
    except StudError as e:
        ui.error(str(e))
        return 1


def cmd_diff(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    from ...vcs.objects import Commit
    from ...vcs.diff import tree_diff, line_diff

    a_oid = svc.refs.resolve(args.a) if args.a else svc.refs.get_head()
    b_oid = svc.refs.resolve(args.b) if args.b else None

    if a_oid and b_oid:
        a_tree = Commit.read(svc.objects, a_oid).tree
        b_tree = Commit.read(svc.objects, b_oid).tree
        diffs = tree_diff(svc.objects, a_tree, b_tree)
        for d in diffs:
            ui.print(f"{d.status:10} {d.path}")
    else:
        ui.print("Specify two refs to diff: stud diff <a> <b>")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("init", help="Initialize a new repository")
    p.add_argument("directory", nargs="?", default=None)
    p.add_argument("--no-wizard", action="store_true")
    p.set_defaults(func=cmd_init)

    p = subparsers.add_parser("add", help="Stage files")
    p.add_argument("paths", nargs="*")
    p.set_defaults(func=cmd_add)

    p = subparsers.add_parser("commit", help="Create a commit")
    p.add_argument("-m", "--message", required=True)
    p.add_argument("--author")
    p.set_defaults(func=cmd_commit)

    p = subparsers.add_parser("status", help="Show working tree status")
    p.set_defaults(func=cmd_status)

    p = subparsers.add_parser("log", help="Show commit history")
    p.add_argument("-n", "--limit", type=int, default=20)
    p.set_defaults(func=cmd_log)

    p = subparsers.add_parser("branch", help="Manage branches")
    p.add_argument("name", nargs="?")
    p.add_argument("--start")
    p.add_argument("-d", "--delete")
    p.set_defaults(func=cmd_branch)

    p = subparsers.add_parser("checkout", help="Switch branch or restore files")
    p.add_argument("target")
    p.set_defaults(func=cmd_checkout)

    p = subparsers.add_parser("merge", help="Merge a branch")
    p.add_argument("branch")
    p.set_defaults(func=cmd_merge)

    p = subparsers.add_parser("diff", help="Show changes between refs")
    p.add_argument("a", nargs="?")
    p.add_argument("b", nargs="?")
    p.set_defaults(func=cmd_diff)
