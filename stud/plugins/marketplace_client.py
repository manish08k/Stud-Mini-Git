import json
import urllib.error
import urllib.request
from typing import List, Optional

from ..core.exceptions import StudError


class MarketplaceError(StudError):
    pass


class MarketplaceClient:
    def __init__(self, base_url: str, token: Optional[str] = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise MarketplaceError(f"GET {url} failed: {e}") from e

    def search(self, query: str) -> List[dict]:
        data = self._get(f"/plugins?q={urllib.request.quote(query)}")
        return data.get("plugins", [])

    def get_plugin(self, name: str) -> dict:
        return self._get(f"/plugins/{name}")

    def get_versions(self, name: str) -> List[str]:
        data = self._get(f"/plugins/{name}/versions")
        return data.get("versions", [])

    def download_url(self, name: str, version: str) -> str:
        data = self._get(f"/plugins/{name}/{version}")
        url = data.get("download_url")
        if not url:
            raise MarketplaceError(f"no download_url for {name}@{version}")
        return url

    def download(self, name: str, version: str, dest_path) -> None:
        from pathlib import Path
        url = self.download_url(name, version)
        req = urllib.request.Request(url, headers=self._headers())
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp, open(dest, "wb") as f:
                import shutil
                shutil.copyfileobj(resp, f)
        except urllib.error.URLError as e:
            raise MarketplaceError(f"download {url} failed: {e}") from e
