import re
from dataclasses import dataclass
from functools import total_ordering
from typing import List, Optional, Tuple

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-.]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z-.]+))?$"
)

_COMPARATOR_RE = re.compile(r"^(>=|<=|>|<|=|\^|~)?\s*(.+)$")


@total_ordering
@dataclass(frozen=True, eq=False)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    @classmethod
    def parse(cls, s: str) -> "Version":
        s = s.strip()
        if s.startswith("v"):
            s = s[1:]
        m = _SEMVER_RE.match(s)
        if not m:
            raise ValueError(f"invalid semver string: {s!r}")
        pre = tuple(m.group("prerelease").split(".")) if m.group("prerelease") else ()
        build = tuple(m.group("build").split(".")) if m.group("build") else ()
        return cls(int(m.group("major")), int(m.group("minor")), int(m.group("patch")), pre, build)

    def __str__(self) -> str:
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += "-" + ".".join(self.prerelease)
        if self.build:
            s += "+" + ".".join(self.build)
        return s

    def __repr__(self) -> str:
        return f"Version('{self}')"

    def _pre_key(self):
        if not self.prerelease:
            return (1,)
        keys = []
        for part in self.prerelease:
            keys.append((0, int(part)) if part.isdigit() else (1, part))
        return (0, tuple(keys))

    def _cmp_key(self):
        return (self.major, self.minor, self.patch, self._pre_key())

    def __eq__(self, other) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._cmp_key() == other._cmp_key()

    def __lt__(self, other) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._cmp_key() < other._cmp_key()

    def __hash__(self) -> int:
        return hash(self._cmp_key())


@dataclass
class Comparator:
    op: str  # "=", ">", ">=", "<", "<="
    version: Version

    def satisfies(self, v: Version) -> bool:
        if self.op == "=":
            return (v.major, v.minor, v.patch, v.prerelease) == (
                self.version.major, self.version.minor, self.version.patch, self.version.prerelease,
            )
        if self.op == ">":
            return v > self.version
        if self.op == ">=":
            return v >= self.version
        if self.op == "<":
            return v < self.version
        if self.op == "<=":
            return v <= self.version
        raise ValueError(f"unknown operator: {self.op}")


def _parse_partial(s: str) -> Tuple[Optional[int], Optional[int], Optional[int], Tuple[str, ...]]:
    s = s.strip()
    if s.startswith("v"):
        s = s[1:]
    core, _, pre = s.partition("-")
    pre_tuple = tuple(p for p in pre.split(".") if p) if pre else ()
    parts = core.split(".") if core else []

    def _part(idx: int) -> Optional[int]:
        if idx >= len(parts):
            return None
        token = parts[idx]
        if token in ("x", "X", "*", ""):
            return None
        return int(token)

    return _part(0), _part(1), _part(2), pre_tuple


def _expand_piece(op: Optional[str], major: Optional[int], minor: Optional[int],
                   patch: Optional[int], pre: Tuple[str, ...]) -> List[Comparator]:
    if major is None:
        return []  # "*", "x", or empty -> always matches

    M, m, p = major, minor or 0, patch or 0

    if op in (None, "="):
        if patch is not None:
            return [Comparator("=", Version(M, m, p, pre))]
        if minor is not None:
            return [Comparator(">=", Version(M, m, 0)), Comparator("<", Version(M, m + 1, 0))]
        return [Comparator(">=", Version(M, 0, 0)), Comparator("<", Version(M + 1, 0, 0))]

    if op == ">=":
        return [Comparator(">=", Version(M, m, p, pre))]

    if op == ">":
        return [Comparator(">", Version(M, m, p, pre))]

    if op == "<":
        return [Comparator("<", Version(M, m, p, pre))]

    if op == "<=":
        if patch is not None:
            return [Comparator("<=", Version(M, m, p, pre))]
        if minor is not None:
            return [Comparator("<", Version(M, m + 1, 0))]
        return [Comparator("<", Version(M + 1, 0, 0))]

    if op == "^":
        if M > 0:
            return [Comparator(">=", Version(M, m, p, pre)), Comparator("<", Version(M + 1, 0, 0))]
        if minor is not None and minor > 0:
            return [Comparator(">=", Version(M, m, p, pre)), Comparator("<", Version(M, m + 1, 0))]
        if patch is not None:
            return [Comparator(">=", Version(M, m, p, pre)), Comparator("<", Version(M, m, p + 1))]
        return [Comparator(">=", Version(M, 0, 0)), Comparator("<", Version(M + 1, 0, 0))]

    if op == "~":
        if minor is not None:
            return [Comparator(">=", Version(M, m, p, pre)), Comparator("<", Version(M, m + 1, 0))]
        return [Comparator(">=", Version(M, 0, 0)), Comparator("<", Version(M + 1, 0, 0))]

    raise ValueError(f"unknown operator: {op}")


def parse_range(s: str) -> List[List[Comparator]]:
    """Parse a constraint string into an OR-list of AND-lists of comparators."""
    s = s.strip()
    if s in ("", "*", "x", "X"):
        return [[]]

    groups: List[List[Comparator]] = []
    for or_group in s.split("||"):
        comparators: List[Comparator] = []
        for token in re.split(r"[\s,]+", or_group.strip()):
            if not token:
                continue
            m = _COMPARATOR_RE.match(token)
            if not m:
                raise ValueError(f"invalid constraint token: {token!r}")
            op, ver_str = m.group(1), m.group(2)
            major, minor, patch, pre = _parse_partial(ver_str)
            comparators.extend(_expand_piece(op, major, minor, patch, pre))
        groups.append(comparators)
    return groups


def satisfies(version: Version, constraint: str) -> bool:
    groups = parse_range(constraint)
    return any(all(c.satisfies(version) for c in group) for group in groups)


def max_satisfying(versions: List[Version], constraint: str) -> Optional[Version]:
    candidates = [v for v in versions if satisfies(v, constraint)]
    if not candidates:
        return None
    return max(candidates)
