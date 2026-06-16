import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

from ..core.object_store import ObjectStore
from .objects import TreeEntry, build_tree_from_entries, flatten_tree


@dataclass
class IndexEntry:
    oid: str
    mode: str = "100644"
    size: int = 0
    mtime: float = 0.0


class Index:
    """Frozen staging area backed by a JSON index file."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._entries: Dict[str, IndexEntry] = {}
        if self.path.exists():
            self.load()

    def load(self) -> None:
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self._entries = {p: IndexEntry(**e) for p, e in raw.items()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {p: asdict(e) for p, e in self._entries.items()}
        tmp = self.path.with_name(self.path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, sort_keys=True)
        tmp.replace(self.path)

    def add(self, rel_path: str, oid: str, mode: str = "100644",
            size: int = 0, mtime: Optional[float] = None) -> None:
        rel_path = rel_path.replace("\\", "/")
        self._entries[rel_path] = IndexEntry(
            oid=oid, mode=mode, size=size,
            mtime=mtime if mtime is not None else time.time(),
        )

    def remove(self, rel_path: str) -> None:
        self._entries.pop(rel_path.replace("\\", "/"), None)

    def get(self, rel_path: str) -> Optional[IndexEntry]:
        return self._entries.get(rel_path.replace("\\", "/"))

    def __contains__(self, rel_path: str) -> bool:
        return rel_path.replace("\\", "/") in self._entries

    def entries(self) -> Iterator[Tuple[str, IndexEntry]]:
        return iter(sorted(self._entries.items()))

    def clear(self) -> None:
        self._entries.clear()

    def to_tree(self, store: ObjectStore) -> str:
        """Build a tree object hierarchy from the flat index and return its root oid."""
        entries = {
            path: TreeEntry(mode=e.mode, name=path.rsplit("/", 1)[-1], oid=e.oid, type="blob")
            for path, e in self._entries.items()
        }
        return build_tree_from_entries(store, entries)

    def from_tree(self, store: ObjectStore, tree_oid: Optional[str]) -> None:
        """Replace index contents with the flattened contents of a tree."""
        self.clear()
        for path, entry in flatten_tree(store, tree_oid).items():
            self.add(path, entry.oid, mode=entry.mode, mtime=0)
