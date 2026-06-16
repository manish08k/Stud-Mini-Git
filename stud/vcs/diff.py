import difflib
from typing import List, NamedTuple, Optional

from ..core.object_store import ObjectStore
from .objects import Tree


class DiffEntry(NamedTuple):
    path: str
    status: str  # "added", "removed", "modified"
    old_oid: Optional[str]
    new_oid: Optional[str]


def tree_diff(store: ObjectStore, old_oid: Optional[str], new_oid: Optional[str]) -> List[DiffEntry]:
    """Recursively diff two trees (either may be None to represent an empty tree)."""
    results: List[DiffEntry] = []

    def entries_of(oid: Optional[str]):
        if oid is None:
            return {}
        return {e.name: e for e in Tree.read(store, oid).entries}

    def walk(old: Optional[str], new: Optional[str], prefix: str) -> None:
        old_entries = entries_of(old)
        new_entries = entries_of(new)
        names = sorted(set(old_entries) | set(new_entries))

        for name in names:
            path = f"{prefix}{name}"
            o = old_entries.get(name)
            n = new_entries.get(name)

            if o and n and o.oid == n.oid and o.type == n.type:
                continue

            if o is None and n is not None:
                if n.type == "tree":
                    walk(None, n.oid, path + "/")
                else:
                    results.append(DiffEntry(path, "added", None, n.oid))
            elif o is not None and n is None:
                if o.type == "tree":
                    walk(o.oid, None, path + "/")
                else:
                    results.append(DiffEntry(path, "removed", o.oid, None))
            else:
                if o.type == "tree" and n.type == "tree":
                    walk(o.oid, n.oid, path + "/")
                elif o.type == "tree" and n.type == "blob":
                    walk(o.oid, None, path + "/")
                    results.append(DiffEntry(path, "added", None, n.oid))
                elif o.type == "blob" and n.type == "tree":
                    results.append(DiffEntry(path, "removed", o.oid, None))
                    walk(None, n.oid, path + "/")
                else:
                    results.append(DiffEntry(path, "modified", o.oid, n.oid))

    walk(old_oid, new_oid, "")
    return results


def line_diff(a_text: str, b_text: str, a_label: str = "a", b_label: str = "b") -> str:
    a_lines = a_text.splitlines(keepends=True)
    b_lines = b_text.splitlines(keepends=True)
    diff = difflib.unified_diff(a_lines, b_lines, fromfile=a_label, tofile=b_label, lineterm="")
    return "\n".join(diff)
