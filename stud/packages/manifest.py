import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.exceptions import StudError
from .semver import Version, parse_range

MANIFEST_FILENAME = "stud.json"


class ManifestError(StudError):
    pass


@dataclass
class PackageManifest:
    name: str
    version: str = "0.1.0"
    description: str = ""
    main: str = "index.js"
    dependencies: Dict[str, str] = field(default_factory=dict)
    dev_dependencies: Dict[str, str] = field(default_factory=dict)
    scripts: Dict[str, str] = field(default_factory=dict)
    license: str = "UNLICENSED"
    keywords: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise ManifestError("package name is required")

        try:
            Version.parse(self.version)
        except ValueError as e:
            raise ManifestError(f"invalid version {self.version!r}: {e}") from e

        for dep_name, constraint in {**self.dependencies, **self.dev_dependencies}.items():
            try:
                parse_range(constraint)
            except ValueError as e:
                raise ManifestError(f"invalid constraint for {dep_name!r}: {constraint!r}: {e}") from e

    @classmethod
    def load(cls, path: Path) -> "PackageManifest":
        path = Path(path)
        if not path.exists():
            raise ManifestError(f"manifest not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ManifestError(f"invalid JSON in {path}: {e}") from e

        known = {f for f in cls.__dataclass_fields__ if f != "extra"}
        kwargs = {k: v for k, v in raw.items() if k in known}
        extra = {k: v for k, v in raw.items() if k not in known}

        try:
            manifest = cls(**kwargs, extra=extra)
        except TypeError as e:
            raise ManifestError(f"invalid manifest {path}: {e}") from e

        manifest.validate()
        return manifest

    def save(self, path: Path) -> None:
        self.validate()
        path = Path(path)
        data = asdict(self)
        extra = data.pop("extra", {})
        data.update(extra)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")

    @classmethod
    def find_and_load(cls, start: Optional[Path] = None) -> "PackageManifest":
        start = Path(start or Path.cwd()).resolve()
        for d in (start, *start.parents):
            candidate = d / MANIFEST_FILENAME
            if candidate.exists():
                return cls.load(candidate)
        raise ManifestError(f"no {MANIFEST_FILENAME} found in {start} or its parents")
