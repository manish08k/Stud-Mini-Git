import fnmatch
import os
from pathlib import Path, PurePosixPath
from typing import List, Optional

from .exceptions import IgnoreError


class IgnorePattern:
    __slots__ = ("raw", "pattern", "negated", "dir_only", "anchored")

    def __init__(self, raw: str):
        self.raw = raw
        pattern = raw

        self.negated = pattern.startswith("!")
        if self.negated:
            pattern = pattern[1:]

        self.dir_only = pattern.endswith("/")
        if self.dir_only:
            pattern = pattern.rstrip("/")

        self.anchored = pattern.startswith("/")
        if self.anchored:
            pattern = pattern.lstrip("/")

        if not pattern:
            raise IgnoreError(f"invalid ignore pattern: {raw!r}")

        self.pattern = pattern

    def match(self, rel_path: str, is_dir: bool) -> bool:
        if self.dir_only and not is_dir:
            return False

        rel = PurePosixPath(rel_path)

        if "/" in self.pattern or self.anchored:
            return fnmatch.fnmatch(str(rel), self.pattern)

        for part in rel.parts:
            if fnmatch.fnmatch(part, self.pattern):
                return True
        return False


class IgnoreFilter:
    """Gitignore-style filter built from .studignore-style pattern lists."""

    DEFAULT_FILENAME = ".studignore"

    def __init__(self, patterns: Optional[List[str]] = None):
        self._patterns: List[IgnorePattern] = []
        if patterns:
            self.add_lines(patterns)

    @classmethod
    def from_file(cls, path: Path) -> "IgnoreFilter":
        path = Path(path)
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            return cls(f.read().splitlines())

    @classmethod
    def from_root(cls, root: Path, filename: str = DEFAULT_FILENAME) -> "IgnoreFilter":
        return cls.from_file(Path(root) / filename)

    def add_lines(self, lines: List[str]) -> None:
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            self._patterns.append(IgnorePattern(stripped))

    def is_ignored(self, rel_path: str, is_dir: bool = False) -> bool:
        rel_path = rel_path.replace(os.sep, "/").lstrip("/")
        ignored = False
        for pat in self._patterns:
            if pat.match(rel_path, is_dir):
                ignored = not pat.negated
        return ignored

    def filter_paths(self, paths: List[str]) -> List[str]:
        return [p for p in paths if not self.is_ignored(p)]
