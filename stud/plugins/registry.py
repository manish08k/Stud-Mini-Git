import json
from pathlib import Path
from typing import Dict, List, Optional

from ..core.exceptions import StudError


class PluginRegistryError(StudError):
    pass


REGISTRY_FILENAME = "plugins.json"


class PluginRegistry:
    def __init__(self, registry_dir: Path):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.registry_dir / REGISTRY_FILENAME
        self._data: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, sort_keys=True)
            f.write("\n")

    def register(self, name: str, version: str, entry_point: str, metadata: Optional[dict] = None) -> None:
        self._data[name] = {
            "name": name,
            "version": version,
            "entry_point": entry_point,
            "metadata": metadata or {},
        }
        self._save()

    def unregister(self, name: str) -> None:
        if name not in self._data:
            raise PluginRegistryError(f"plugin not found: {name}")
        del self._data[name]
        self._save()

    def get(self, name: str) -> Optional[dict]:
        return self._data.get(name)

    def list_plugins(self) -> List[dict]:
        return list(self._data.values())

    def is_installed(self, name: str) -> bool:
        return name in self._data
