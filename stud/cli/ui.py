import sys
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class UI:
    def __init__(self, color: bool = True, quiet: bool = False):
        self.quiet = quiet
        if HAS_RICH:
            self._console = Console(highlight=False, no_color=not color)
            self._err_console = Console(stderr=True, highlight=False, no_color=not color)
        else:
            self._console = None
            self._err_console = None

    def print(self, *args, **kwargs) -> None:
        if self.quiet:
            return
        if HAS_RICH:
            self._console.print(*args, **kwargs)
        else:
            print(*args)

    def error(self, message: str) -> None:
        if HAS_RICH:
            self._err_console.print(f"[bold red]error:[/bold red] {message}")
        else:
            print(f"error: {message}", file=sys.stderr)

    def warn(self, message: str) -> None:
        if self.quiet:
            return
        if HAS_RICH:
            self._console.print(f"[bold yellow]warning:[/bold yellow] {message}")
        else:
            print(f"warning: {message}")

    def success(self, message: str) -> None:
        if self.quiet:
            return
        if HAS_RICH:
            self._console.print(f"[bold green]✓[/bold green] {message}")
        else:
            print(f"ok: {message}")

    def info(self, message: str) -> None:
        if self.quiet:
            return
        if HAS_RICH:
            self._console.print(f"[cyan]info:[/cyan] {message}")
        else:
            print(f"info: {message}")

    def table(self, headers: List[str], rows: List[List[Any]], title: Optional[str] = None) -> None:
        if self.quiet:
            return
        if HAS_RICH:
            t = Table(*headers, title=title)
            for row in rows:
                t.add_row(*[str(c) for c in row])
            self._console.print(t)
        else:
            if title:
                print(f"\n{title}")
            print("  ".join(headers))
            print("-" * 40)
            for row in rows:
                print("  ".join(str(c) for c in row))

    def panel(self, content: str, title: Optional[str] = None) -> None:
        if self.quiet:
            return
        if HAS_RICH:
            self._console.print(Panel(content, title=title))
        else:
            if title:
                print(f"--- {title} ---")
            print(content)

    def rule(self, title: str = "") -> None:
        if self.quiet:
            return
        if HAS_RICH:
            self._console.rule(title)
        else:
            print(f"{'─' * 20} {title} {'─' * 20}" if title else "─" * 40)

    def confirm(self, message: str, default: bool = False) -> bool:
        suffix = "[Y/n]" if default else "[y/N]"
        try:
            answer = input(f"{message} {suffix} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        if not answer:
            return default
        return answer in ("y", "yes")

    def prompt(self, message: str, default: Optional[str] = None,
               password: bool = False) -> str:
        import getpass
        suffix = f" [{default}]" if default else ""
        try:
            if password:
                value = getpass.getpass(f"{message}{suffix}: ")
            else:
                value = input(f"{message}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            return default or ""
        return value or default or ""


_default_ui: Optional[UI] = None


def get_ui() -> UI:
    global _default_ui
    if _default_ui is None:
        _default_ui = UI()
    return _default_ui


def set_ui(ui: UI) -> None:
    global _default_ui
    _default_ui = ui
