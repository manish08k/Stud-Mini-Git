from dataclasses import dataclass
from typing import Dict, List, Protocol

from ..core.exceptions import StudError
from .semver import Version, max_satisfying, satisfies


class ResolverError(StudError):
    pass


class PackageIndex(Protocol):
    def versions(self, name: str) -> List[Version]: ...
    def dependencies(self, name: str, version: Version) -> Dict[str, str]: ...


@dataclass
class ResolvedPackage:
    name: str
    version: Version
    dependencies: Dict[str, str]


class Resolver:
    """Simple recursive dependency resolver with conflict detection."""

    def __init__(self, index: PackageIndex):
        self.index = index

    def resolve(self, root_dependencies: Dict[str, str]) -> Dict[str, ResolvedPackage]:
        resolved: Dict[str, ResolvedPackage] = {}
        self._resolve_into(root_dependencies, resolved, path=[])
        return resolved

    def _resolve_into(self, dependencies: Dict[str, str],
                       resolved: Dict[str, ResolvedPackage], path: List[str]) -> None:
        for name, constraint in sorted(dependencies.items()):
            if name in path:
                raise ResolverError(f"circular dependency detected: {' -> '.join(path + [name])}")

            existing = resolved.get(name)
            if existing is not None:
                if not satisfies(existing.version, constraint):
                    raise ResolverError(
                        f"conflicting dependency: {name} resolved to {existing.version}, "
                        f"but {' -> '.join(path) or '<root>'} requires {constraint!r}"
                    )
                continue

            available = self.index.versions(name)
            if not available:
                raise ResolverError(f"no versions found for package {name!r}")

            best = max_satisfying(available, constraint)
            if best is None:
                raise ResolverError(f"no version of {name!r} satisfies constraint {constraint!r}")

            sub_deps = self.index.dependencies(name, best)
            resolved[name] = ResolvedPackage(name=name, version=best, dependencies=sub_deps)
            self._resolve_into(sub_deps, resolved, path + [name])
