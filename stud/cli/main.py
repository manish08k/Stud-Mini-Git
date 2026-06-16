#!/usr/bin/env python3
"""
stud - the all-in-one developer tool.
"""
import argparse
import sys
from typing import List, Optional

from .ui import UI, set_ui
from .completion import get_completion_script
from .repl import REPL
from .commands import (
    register_vcs,
    register_packages,
    register_workflows,
    register_ai,
    register_security,
    register_remote,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stud",
        description="stud: VCS + package manager + workflows + AI, in one tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--no-color", action="store_true", help="Disable color output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-error output")
    parser.add_argument("--version", action="version", version="stud 0.1.0")

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    register_vcs(subparsers)
    register_packages(subparsers)
    register_workflows(subparsers)
    register_ai(subparsers)
    register_security(subparsers)
    register_remote(subparsers)

    # completion
    comp = subparsers.add_parser("completion", help="Print shell completion script")
    comp.add_argument("shell", choices=["bash", "zsh", "fish"])
    comp.set_defaults(func=lambda args: (print(get_completion_script(args.shell)), 0)[1])

    # repl
    repl_p = subparsers.add_parser("repl", help="Start interactive REPL")
    repl_p.set_defaults(func=None)

    return parser


def dispatch(argv: List[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    ui = UI(color=not args.no_color, quiet=args.quiet)
    set_ui(ui)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "repl":
        def _dispatch(inner_argv: list) -> int:
            return dispatch(inner_argv)
        REPL(_dispatch, ui=ui).run()
        return 0

    if not hasattr(args, "func") or args.func is None:
        parser.print_help()
        return 1

    from ..core.exceptions import StudError
    try:
        return args.func(args) or 0
    except StudError as e:
        ui.error(str(e))
        return 1
    except KeyboardInterrupt:
        ui.print("\nInterrupted.")
        return 130


def main() -> None:
    sys.exit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    main()
