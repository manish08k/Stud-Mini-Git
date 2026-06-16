import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core.object_store import ObjectStore


def _enc(s: str) -> bytes:
    return s.encode("utf-8")


def _dec(b: bytes) -> str:
    return b.decode("utf-8")


@dataclass
class Blob:
    data: bytes

    def write(self, store: ObjectStore) -> str:
        return store.write(self.data, "blob")

    @classmethod
    def read(cls, store: ObjectStore, oid: str) -> "Blob":
        obj_type, data = store.read(oid)
        if obj_type != "blob":
            raise ValueError(f"object {oid} is not a blob (got {obj_type})")
        return cls(data=data)


@dataclass
class TreeEntry:
    mode: str   # "100644" file, "100755" executable, "040000" directory
    name: str
    oid: str
    type: str   # "blob" or "tree"

    def serialize(self) -> str:
        return f"{self.mode} {self.type} {self.oid}\t{self.name}"

    @classmethod
    def parse(cls, line: str) -> "TreeEntry":
        meta, name = line.split("\t", 1)
        mode, obj_type, oid = meta.split(" ")
        return cls(mode=mode, name=name, oid=oid, type=obj_type)


@dataclass
class Tree:
    entries: List[TreeEntry] = field(default_factory=list)

    def add(self, entry: TreeEntry) -> None:
        self.entries = [e for e in self.entries if e.name != entry.name]
        self.entries.append(entry)
        self.entries.sort(key=lambda e: e.name)

    def get(self, name: str) -> Optional[TreeEntry]:
        for e in self.entries:
            if e.name == name:
                return e
        return None

    def serialize(self) -> bytes:
        lines = [e.serialize() for e in sorted(self.entries, key=lambda e: e.name)]
        return _enc("\n".join(lines) + ("\n" if lines else ""))

    def write(self, store: ObjectStore) -> str:
        return store.write(self.serialize(), "tree")

    @classmethod
    def deserialize(cls, data: bytes) -> "Tree":
        text = _dec(data)
        entries = [TreeEntry.parse(l) for l in text.splitlines() if l]
        return cls(entries=entries)

    @classmethod
    def read(cls, store: ObjectStore, oid: str) -> "Tree":
        obj_type, data = store.read(oid)
        if obj_type != "tree":
            raise ValueError(f"object {oid} is not a tree (got {obj_type})")
        return cls.deserialize(data)


@dataclass
class Commit:
    tree: str
    parents: List[str] = field(default_factory=list)
    author: str = "unknown"
    committer: str = "unknown"
    message: str = ""
    timestamp: float = field(default_factory=time.time)

    def serialize(self) -> bytes:
        lines = [f"tree {self.tree}"]
        for p in self.parents:
            lines.append(f"parent {p}")
        lines.append(f"author {self.author} {self.timestamp}")
        lines.append(f"committer {self.committer} {self.timestamp}")
        lines.append("")
        lines.append(self.message)
        return _enc("\n".join(lines))

    def write(self, store: ObjectStore) -> str:
        return store.write(self.serialize(), "commit")

    @classmethod
    def deserialize(cls, data: bytes) -> "Commit":
        text = _dec(data)
        header, _, message = text.partition("\n\n")

        tree = ""
        parents: List[str] = []
        author = "unknown"
        committer = "unknown"
        timestamp = 0.0

        for line in header.splitlines():
            key, _, value = line.partition(" ")
            if key == "tree":
                tree = value
            elif key == "parent":
                parents.append(value)
            elif key == "author":
                name, ts = value.rsplit(" ", 1)
                author = name
                timestamp = float(ts)
            elif key == "committer":
                name, ts = value.rsplit(" ", 1)
                committer = name
                timestamp = float(ts)

        return cls(tree=tree, parents=parents, author=author, committer=committer,
                    message=message, timestamp=timestamp)

    @classmethod
    def read(cls, store: ObjectStore, oid: str) -> "Commit":
        obj_type, data = store.read(oid)
        if obj_type != "commit":
            raise ValueError(f"object {oid} is not a commit (got {obj_type})")
        return cls.deserialize(data)


def flatten_tree(store: ObjectStore, tree_oid: Optional[str]) -> Dict[str, TreeEntry]:
    """Recursively flatten a tree into {full_path: TreeEntry} for blobs only."""
    result: Dict[str, TreeEntry] = {}
    if tree_oid is None:
        return result

    def walk(oid: str, prefix: str) -> None:
        tree = Tree.read(store, oid)
        for entry in tree.entries:
            path = f"{prefix}{entry.name}"
            if entry.type == "tree":
                walk(entry.oid, path + "/")
            else:
                result[path] = entry

    walk(tree_oid, "")
    return result


def build_tree_from_entries(store: ObjectStore, entries: Dict[str, TreeEntry]) -> str:
    """Build a (possibly nested) tree object hierarchy from {full_path: TreeEntry}."""
    root: dict = {}
    for path, entry in entries.items():
        parts = path.split("/")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = entry

    def write_tree(node: dict) -> str:
        tree = Tree()
        for name, value in node.items():
            if isinstance(value, dict):
                oid = write_tree(value)
                tree.add(TreeEntry(mode="040000", name=name, oid=oid, type="tree"))
            else:
                tree.add(TreeEntry(mode=value.mode, name=name, oid=value.oid, type="blob"))
        return tree.write(store)

    return write_tree(root)
