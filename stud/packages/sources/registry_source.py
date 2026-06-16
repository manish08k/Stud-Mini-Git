import tarfile
import tempfile
from pathlib import Path

from ...core.exceptions import StudError
from ..manifest import PackageManifest
from ..semver import Version


class RegistrySource:
    """Fetches and extracts packages from a registry (HTTP or local)."""

    def __init__(self, registry):
        self.registry = registry

    def fetch(self, name: str, version: Version, dest_dir: Path) -> PackageManifest:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            tarball = Path(tmp) / "package.tar.gz"
            self.registry.download(name, version, tarball)
            with tarfile.open(tarball, "r:gz") as tar:
                tar.extractall(dest_dir)

        manifest_path = dest_dir / "stud.json"
        if not manifest_path.exists():
            raise StudError(f"package {name}@{version} is missing stud.json")
        return PackageManifest.load(manifest_path)
