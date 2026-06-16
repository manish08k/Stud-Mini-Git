import shutil
from pathlib import Path

from ...core.exceptions import StudError
from ..manifest import PackageManifest


class LocalSource:
    """Fetches a package from a local directory (file: paths, monorepo links)."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def fetch(self, dest_dir: Path) -> PackageManifest:
        if not self.path.exists():
            raise StudError(f"local package path does not exist: {self.path}")

        manifest_path = self.path / "stud.json"
        if not manifest_path.exists():
            raise StudError(f"local package {self.path} is missing stud.json")

        dest_dir = Path(dest_dir)
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(
            self.path, dest_dir,
            ignore=shutil.ignore_patterns(".stud", "stud_modules", "__pycache__"),
        )

        return PackageManifest.load(dest_dir / "stud.json")
