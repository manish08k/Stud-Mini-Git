import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.object_store import ObjectStore
from .objects import TreeEntry, build_tree_from_entries, flatten_tree

CONFLICT_START = "<<<<<<< ours\n"
CONFLICT_MID = "=======\n"
CONFLICT_END = ">>>>>>> theirs\n"


@dataclass
class MergeResult:
    tree_oid: str
    conflicts: List[str] = field(default_factory=list)


def merge_lines(base: List[str], ours: List[str], theirs: List[str]) -> Tuple[List[str], bool]:
    """Line-based 3-way merge. Returns (merged_lines, had_conflict)."""
    base = list(base)
    ours = list(ours)
    theirs = list(theirs)

    if ours == theirs:
        return list(ours), False
    if ours == base:
        return list(theirs), False
    if theirs == base:
        return list(ours), False

    sm_o = difflib.SequenceMatcher(a=base, b=ours, autojunk=False)
    sm_t = difflib.SequenceMatcher(a=base, b=theirs, autojunk=False)

    map_o: Dict[int, int] = {}
    matched_o = set()
    for a, b, size in sm_o.get_matching_blocks():
        for k in range(size):
            map_o[a + k] = b + k
            matched_o.add(a + k)

    map_t: Dict[int, int] = {}
    matched_t = set()
    for a, b, size in sm_t.get_matching_blocks():
        for k in range(size):
            map_t[a + k] = b + k
            matched_t.add(a + k)

    stable = sorted(matched_o & matched_t)
    n = len(base)

    anchors: List[Tuple[int, int]] = []
    i = 0
    while i < len(stable):
        j = i
        while j + 1 < len(stable) and stable[j + 1] == stable[j] + 1:
            j += 1
        anchors.append((stable[i], stable[j]))
        i = j + 1

    result: List[str] = []
    conflict = False
    prev = 0
    prev_o = 0
    prev_t = 0

    def emit_hunk(b_base: List[str], b_ours: List[str], b_theirs: List[str]) -> None:
        nonlocal conflict
        if b_ours == b_base and b_theirs == b_base:
            return
        if b_ours == b_base:
            result.extend(b_theirs)
        elif b_theirs == b_base:
            result.extend(b_ours)
        elif b_ours == b_theirs:
            result.extend(b_ours)
        else:
            conflict = True
            result.append(CONFLICT_START)
            result.extend(b_ours)
            result.append(CONFLICT_MID)
            result.extend(b_theirs)
            result.append(CONFLICT_END)

    for a_start, a_end in anchors:
        ob, tb = map_o[a_start], map_t[a_start]
        emit_hunk(base[prev:a_start], ours[prev_o:ob], theirs[prev_t:tb])
        result.extend(base[a_start:a_end + 1])
        prev = a_end + 1
        prev_o = map_o[a_end] + 1
        prev_t = map_t[a_end] + 1

    emit_hunk(base[prev:n], ours[prev_o:len(ours)], theirs[prev_t:len(theirs)])

    return result, conflict


def merge_trees(store: ObjectStore, base_oid: Optional[str], ours_oid: Optional[str],
                 theirs_oid: Optional[str]) -> MergeResult:
    """Merge two trees with a common ancestor tree into a new tree."""
    base_files = flatten_tree(store, base_oid)
    ours_files = flatten_tree(store, ours_oid)
    theirs_files = flatten_tree(store, theirs_oid)

    all_paths = sorted(set(base_files) | set(ours_files) | set(theirs_files))
    merged: Dict[str, Optional[TreeEntry]] = {}
    conflicts: List[str] = []

    for path in all_paths:
        b = base_files.get(path)
        o = ours_files.get(path)
        t = theirs_files.get(path)

        if o == t:
            merged[path] = o
            continue

        both_changed = (
            o is not None and t is not None
            and (b is None or (o.oid != b.oid and t.oid != b.oid))
        )

        if both_changed:
            base_data = store.read_data(b.oid) if b else b""
            ours_data = store.read_data(o.oid)
            theirs_data = store.read_data(t.oid)

            try:
                merged_lines, had_conflict = merge_lines(
                    base_data.decode("utf-8").splitlines(keepends=True),
                    ours_data.decode("utf-8").splitlines(keepends=True),
                    theirs_data.decode("utf-8").splitlines(keepends=True),
                )
                merged_data = "".join(merged_lines).encode("utf-8")
            except UnicodeDecodeError:
                merged_data = ours_data
                had_conflict = ours_data != theirs_data

            new_oid = store.write(merged_data, "blob")
            merged[path] = TreeEntry(mode=o.mode, name=path.rsplit("/", 1)[-1],
                                      oid=new_oid, type="blob")
            if had_conflict:
                conflicts.append(path)
            continue

        if b == o:
            merged[path] = t
            continue

        if b == t:
            merged[path] = o
            continue

        merged[path] = o if o is not None else t
        if b != o and b != t:
            conflicts.append(path)

    tree_oid = build_tree_from_entries(store, {p: e for p, e in merged.items() if e is not None})
    return MergeResult(tree_oid=tree_oid, conflicts=conflicts)
