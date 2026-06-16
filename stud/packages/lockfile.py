import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Optional

LOCKFILE_FILENAME = "stud.lock"
LOCKFILE_VERSION = 1


@dataclass
class LockedPackage:
    name: str
    version: str
    resolved: str = ""
    integrity: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)


@dataclass
class Lockfile:
    lockfile_version: int = LOCKFILE_VERSION
    packages: Dict[str, LockedPackage] = field(default_factory=dict)

    @staticmethod
    def key(name: str, version: str) -> str:
        return f"{name}@{version}"

    def add(self, package: LockedPackage) -> None:
        self.packages[self.key(package.name, package.version)] = package

    def get(self, name: str, version: str) -> Optional[LockedPackage]:
        return self.packages.get(self.key(name, version))

    def remove(self, name: str, version: str) -> None:
        self.packages.pop(self.key(name, version), None)

    @classmethod
    def load(cls, path: Path) -> "Lockfile":
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        packages = {k: LockedPackage(**v) for k, v in raw.get("packages", {}).items()}
        return cls(lockfile_version=raw.get("lockfile_version", LOCKFILE_VERSION), packages=packages)

    def save(self, path: Path) -> None:
        path = Path(path)
        data = {
            "lockfile_version": self.lockfile_version,
            "packages": {k: asdict(v) for k, v in self.packages.items()},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        tmp.replace(path)
