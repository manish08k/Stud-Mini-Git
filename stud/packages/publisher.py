import tarfile
import tempfile
from pathlib import Path
from typing import Optional

from .manifest import PackageManifest
from .registry_client import sha256_of_file
from .semver import Version

EXCLUDED_DIRS = {".stud", "stud_modules", "__pycache__"}


class Publisher:
    """Packs a package directory into a tarball and publishes it to a registry."""

    def __init__(self, registry):
        self.registry = registry

    def pack(self, package_dir: Path, dest: Path) -> Path:
        package_dir = Path(package_dir)
        manifest = PackageManifest.load(package_dir / "stud.json")
        manifest.validate()

        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)

        with tarfile.open(dest, "w:gz") as tar:
            for item in sorted(package_dir.rglob("*")):
                rel = item.relative_to(package_dir)
                if any(part in EXCLUDED_DIRS for part in rel.parts):
                    continue
                if item.is_file():
                    tar.add(item, arcname=str(rel))

        return dest

    def publish(self, package_dir: Path, tarball: Optional[Path] = None) -> str:
        package_dir = Path(package_dir)
        manifest = PackageManifest.load(package_dir / "stud.json")
        manifest.validate()

        cleanup_dir: Optional[Path] = None
        if tarball is None:
            cleanup_dir = Path(tempfile.mkdtemp())
            tarball = self.pack(package_dir, cleanup_dir / "package.tar.gz")

        version = Version.parse(manifest.version)
        integrity = f"sha256-{sha256_of_file(tarball)}"
        manifest_dict = {
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "dependencies": manifest.dependencies,
            "integrity": integrity,
        }

        self.registry.publish(manifest.name, version, manifest_dict, tarball)
        return integrity
