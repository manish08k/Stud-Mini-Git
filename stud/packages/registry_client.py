import hashlib
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from ..core.exceptions import StudError
from .semver import Version


class RegistryError(StudError):
    pass


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class RegistryClient:
    """HTTP client for a remote Stud package registry."""

    def __init__(self, base_url: str, token: Optional[str] = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self, extra: Optional[dict] = None) -> dict:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def _get_json(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RegistryError(f"GET {url} failed: {e}") from e

    def versions(self, name: str) -> List[Version]:
        data = self._get_json(f"/packages/{name}")
        return [Version.parse(v) for v in data.get("versions", [])]

    def manifest(self, name: str, version: Version) -> dict:
        return self._get_json(f"/packages/{name}/{version}")

    def dependencies(self, name: str, version: Version) -> Dict[str, str]:
        return self.manifest(name, version).get("dependencies", {})

    def download(self, name: str, version: Version, dest: Path) -> Path:
        url = f"{self.base_url}/packages/{name}/{version}/download"
        req = urllib.request.Request(url, headers=self._headers())
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp, open(dest, "wb") as f:
                shutil.copyfileobj(resp, f)
        except urllib.error.URLError as e:
            raise RegistryError(f"GET {url} failed: {e}") from e
        return dest

    def publish(self, name: str, version: Version, manifest: dict, tarball: Path) -> None:
        url = f"{self.base_url}/packages/{name}/{version}"
        payload = {"manifest": manifest, "tarball": Path(tarball).read_bytes().hex()}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="PUT",
            headers=self._headers({"Content-Type": "application/json"}),
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout):
                pass
        except urllib.error.URLError as e:
            raise RegistryError(f"PUT {url} failed: {e}") from e


class LocalRegistry:
    """
    Filesystem-backed package registry for offline use, local mirrors, and tests.

    Layout:
        <root>/<name>/<version>/manifest.json
        <root>/<name>/<version>/package.tar.gz
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _pkg_dir(self, name: str, version: Version) -> Path:
        return self.root / name / str(version)

    def versions(self, name: str) -> List[Version]:
        base = self.root / name
        if not base.exists():
            return []
        return sorted(Version.parse(p.name) for p in base.iterdir() if p.is_dir())

    def manifest(self, name: str, version: Version) -> dict:
        path = self._pkg_dir(name, version) / "manifest.json"
        if not path.exists():
            raise RegistryError(f"no such package: {name}@{version}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def dependencies(self, name: str, version: Version) -> Dict[str, str]:
        return self.manifest(name, version).get("dependencies", {})

    def download(self, name: str, version: Version, dest: Path) -> Path:
        src = self._pkg_dir(name, version) / "package.tar.gz"
        if not src.exists():
            raise RegistryError(f"no tarball for {name}@{version}")
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)
        return dest

    def publish(self, name: str, version: Version, manifest: dict, tarball: Path) -> None:
        pkg_dir = self._pkg_dir(name, version)
        pkg_dir.mkdir(parents=True, exist_ok=True)
        with open(pkg_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
        shutil.copy(tarball, pkg_dir / "package.tar.gz")
