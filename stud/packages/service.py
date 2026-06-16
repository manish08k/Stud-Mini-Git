import shutil
from pathlib import Path
from typing import Dict

from ..core.exceptions import StudError
from .lockfile import LockedPackage, Lockfile
from .manifest import MANIFEST_FILENAME, PackageManifest
from .resolver import ResolvedPackage, Resolver
from .sources.registry_source import RegistrySource

MODULES_DIR_NAME = "stud_modules"
LOCKFILE_FILENAME = "stud.lock"


class PackageServiceError(StudError):
    pass


class PackageService:
    def __init__(self, project_dir: Path, registry):
        self.project_dir = Path(project_dir)
        self.registry = registry
        self.modules_dir = self.project_dir / MODULES_DIR_NAME

    @property
    def manifest_path(self) -> Path:
        return self.project_dir / MANIFEST_FILENAME

    @property
    def lockfile_path(self) -> Path:
        return self.project_dir / LOCKFILE_FILENAME

    def load_manifest(self) -> PackageManifest:
        return PackageManifest.load(self.manifest_path)

    def resolve(self) -> Dict[str, ResolvedPackage]:
        manifest = self.load_manifest()
        all_deps = {**manifest.dependencies, **manifest.dev_dependencies}
        return Resolver(self.registry).resolve(all_deps)

    def install(self) -> Lockfile:
        resolved = self.resolve()
        lockfile = Lockfile.load(self.lockfile_path)
        source = RegistrySource(self.registry)

        self.modules_dir.mkdir(parents=True, exist_ok=True)

        for name, pkg in resolved.items():
            dest = self.modules_dir / name
            source.fetch(name, pkg.version, dest)

            lockfile.add(LockedPackage(
                name=name,
                version=str(pkg.version),
                resolved=f"registry:{name}@{pkg.version}",
                dependencies=pkg.dependencies,
            ))

        lockfile.save(self.lockfile_path)
        return lockfile

    def add_dependency(self, name: str, constraint: str, dev: bool = False) -> None:
        manifest = self.load_manifest()
        target = manifest.dev_dependencies if dev else manifest.dependencies
        target[name] = constraint
        manifest.save(self.manifest_path)

    def remove_dependency(self, name: str, dev: bool = False) -> None:
        manifest = self.load_manifest()
        target = manifest.dev_dependencies if dev else manifest.dependencies
        if name not in target:
            raise PackageServiceError(f"no such dependency: {name}")
        del target[name]
        manifest.save(self.manifest_path)

        lockfile = Lockfile.load(self.lockfile_path)
        for key in [k for k in lockfile.packages if k.startswith(f"{name}@")]:
            del lockfile.packages[key]
        lockfile.save(self.lockfile_path)

        pkg_dir = self.modules_dir / name
        if pkg_dir.exists():
            shutil.rmtree(pkg_dir)
