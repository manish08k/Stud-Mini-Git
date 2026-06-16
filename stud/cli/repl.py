import shlex
import sys
from typing import Callable, Dict, Optional

from .ui import UI, get_ui

BANNER = r"""
 ____  _             _ 
/ ___|| |_ _   _  __| |
\___ \| __| | | |/ _` |
 ___) | |_| |_| | (_| |
|____/ \__|\__,_|\__,_|

Type 'help' for commands, 'exit' to quit.
"""


class REPL:
    def __init__(self, dispatch: Callable[[list], int], ui: Optional[UI] = None):
        self.dispatch = dispatch
        self.ui = ui or get_ui()
        self._running = False

    def run(self) -> None:
        self.ui.print(BANNER)
        self._running = True

        while self._running:
            try:
                line = input("stud> ").strip()
            except (EOFError, KeyboardInterrupt):
                self.ui.print("\nBye.")
                break

            if not line or line.startswith("#"):
                continue

            if line in ("exit", "quit", "q"):
                self.ui.print("Bye.")
                break

            try:
                args = shlex.split(line)
            except ValueError as e:
                self.ui.error(f"parse error: {e}")
                continue

            try:
                self.dispatch(args)
            except SystemExit as e:
                if e.code not in (0, None):
                    pass
            except KeyboardInterrupt:
                self.ui.warn("interrupted")
            except Exception as e:
                self.ui.error(str(e))
