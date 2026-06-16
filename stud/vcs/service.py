import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from ..core.exceptions import StudError
from ..core.ignore import IgnoreFilter
from ..core.object_store import ObjectStore
from .diff import DiffEntry, tree_diff
from .index import Index
from .merge import MergeResult, merge_trees
from .objects import Blob, Commit, flatten_tree
from .refs import RefManager

STUD_DIR_NAME = ".stud"
DEFAULT_AUTHOR = "user <user@example.com>"


class VCSError(StudError):
    pass


class VCSService:
    def __init__(self, work_dir: Path, stud_dir: Optional[Path] = None):
        self.work_dir = Path(work_dir).resolve()
        self.stud_dir = Path(stud_dir) if stud_dir else self.work_dir / STUD_DIR_NAME
        self.objects = ObjectStore(self.stud_dir / "objects")
        self.refs = RefManager(self.stud_dir)
        self.index = Index(self.stud_dir / "index")
        self.ignore = IgnoreFilter.from_root(self.work_dir)

    # -- repository lifecycle ------------------------------------------------

    @classmethod
    def init(cls, work_dir: Path) -> "VCSService":
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        return cls(work_dir)

    @property
    def initialized(self) -> bool:
        return self.stud_dir.exists()

    # -- working tree helpers --------------------------------------------------

    def _iter_work_files(self) -> List[str]:
        results: List[str] = []
        for root, dirs, files in os.walk(self.work_dir):
            rel_root = os.path.relpath(root, self.work_dir)
            rel_root = "" if rel_root == "." else rel_root.replace(os.sep, "/")

            dirs[:] = [
                d for d in dirs
                if d != STUD_DIR_NAME
                and not self.ignore.is_ignored(f"{rel_root}/{d}" if rel_root else d, is_dir=True)
            ]

            for name in files:
                rel_path = f"{rel_root}/{name}" if rel_root else name
                if self.ignore.is_ignored(rel_path):
                    continue
                results.append(rel_path)
        return sorted(results)

    # -- staging --------------------------------------------------------------

    def add(self, paths: Optional[List[str]] = None) -> List[str]:
        """Stage files. If paths is None, stage all tracked working-tree files."""
        if paths is None:
            paths = self._iter_work_files()

        staged = []
        for rel_path in paths:
            full = self.work_dir / rel_path
            if not full.exists() or not full.is_file():
                continue
            data = full.read_bytes()
            oid = self.objects.write(data, "blob")
            self.index.add(rel_path, oid, size=len(data), mtime=full.stat().st_mtime)
            staged.append(rel_path)

        self.index.save()
        return staged

    def unstage(self, paths: List[str]) -> None:
        for p in paths:
            self.index.remove(p)
        self.index.save()

    # -- status / diff ---------------------------------------------------------

    def status(self) -> Dict[str, List[str]]:
        head_oid = self.refs.get_head()
        head_tree = Commit.read(self.objects, head_oid).tree if head_oid else None
        head_files = flatten_tree(self.objects, head_tree)

        staged_added: List[str] = []
        staged_modified: List[str] = []
        staged_deleted: List[str] = []

        for path, entry in head_files.items():
            idx = self.index.get(path)
            if idx is None:
                staged_deleted.append(path)
            elif idx.oid != entry.oid:
                staged_modified.append(path)

        indexed_paths = {p for p, _ in self.index.entries()}
        for path in indexed_paths:
            if path not in head_files:
                staged_added.append(path)

        work_files = set(self._iter_work_files())
        untracked: List[str] = []
        unstaged_modified: List[str] = []
        unstaged_deleted: List[str] = []

        for path in work_files:
            if path not in indexed_paths:
                untracked.append(path)
            else:
                full = self.work_dir / path
                data = full.read_bytes()
                live_oid = self.objects.write(data, "blob")
                idx_entry = self.index.get(path)
                if idx_entry is not None and live_oid != idx_entry.oid:
                    unstaged_modified.append(path)

        for path in indexed_paths:
            if path not in work_files:
                unstaged_deleted.append(path)

        return {
            "staged_added": sorted(staged_added),
            "staged_modified": sorted(staged_modified),
            "staged_deleted": sorted(staged_deleted),
            "untracked": sorted(untracked),
            "unstaged_modified": sorted(unstaged_modified),
            "unstaged_deleted": sorted(unstaged_deleted),
        }

    def diff_commits(self, old_oid: Optional[str], new_oid: Optional[str]) -> List[DiffEntry]:
        old_tree = Commit.read(self.objects, old_oid).tree if old_oid else None
        new_tree = Commit.read(self.objects, new_oid).tree if new_oid else None
        return tree_diff(self.objects, old_tree, new_tree)

    # -- commits -----------------------------------------------------------------

    def commit(self, message: str, author: str = DEFAULT_AUTHOR) -> str:
        tree_oid = self.index.to_tree(self.objects)
        head_oid = self.refs.get_head()
        parents = [head_oid] if head_oid else []

        if head_oid is not None:
            parent_tree = Commit.read(self.objects, head_oid).tree
            if parent_tree == tree_oid:
                raise VCSError("nothing to commit, working tree clean")

        commit = Commit(
            tree=tree_oid,
            parents=parents,
            author=author,
            committer=author,
            message=message,
            timestamp=time.time(),
        )
        oid = commit.write(self.objects)
        self.refs.update_head(oid)
        return oid

    def log(self, start: Optional[str] = None, limit: Optional[int] = None) -> List[Commit]:
        oid = start or self.refs.get_head()
        result: List[Commit] = []
        seen: Set[str] = set()
        while oid and oid not in seen and (limit is None or len(result) < limit):
            seen.add(oid)
            commit = Commit.read(self.objects, oid)
            result.append(commit)
            oid = commit.parents[0] if commit.parents else None
        return result

    # -- ancestry / merge base -----------------------------------------------------

    def _ancestors(self, oid: Optional[str]) -> Set[str]:
        result: Set[str] = set()
        stack = [oid] if oid else []
        while stack:
            current = stack.pop()
            if current is None or current in result:
                continue
            result.add(current)
            commit = Commit.read(self.objects, current)
            stack.extend(commit.parents)
        return result

    def merge_base(self, a_oid: str, b_oid: str) -> Optional[str]:
        a_ancestors = self._ancestors(a_oid)
        seen: Set[str] = set()
        queue = [b_oid]
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            if current in a_ancestors:
                return current
            commit = Commit.read(self.objects, current)
            queue.extend(commit.parents)
        return None

    # -- branches / checkout ----------------------------------------------------------

    def create_branch(self, name: str, start: Optional[str] = None) -> None:
        start_oid = start or self.refs.get_head()
        if start_oid is None:
            raise VCSError("cannot create a branch: no commits yet")
        self.refs.create_branch(name, start_oid)

    def checkout(self, name: str) -> None:
        oid = self.refs.resolve(name)
        if oid is None:
            raise VCSError(f"unknown revision: {name}")

        commit = Commit.read(self.objects, oid)
        self._checkout_tree(commit.tree)

        if name in self.refs.list_branches():
            self.refs.set_head_symbolic(name)
        else:
            self.refs.set_head_detached(oid)

    def _checkout_tree(self, tree_oid: Optional[str]) -> None:
        target_files = flatten_tree(self.objects, tree_oid)

        for path, _ in list(self.index.entries()):
            if path not in target_files:
                full = self.work_dir / path
                if full.exists():
                    full.unlink()

        for path, entry in target_files.items():
            full = self.work_dir / path
            full.parent.mkdir(parents=True, exist_ok=True)
            blob = Blob.read(self.objects, entry.oid)
            full.write_bytes(blob.data)

        self.index.from_tree(self.objects, tree_oid)
        self.index.save()

    # -- merge -----------------------------------------------------------------------

    def merge(self, branch: str, author: str = DEFAULT_AUTHOR) -> MergeResult:
        head_oid = self.refs.get_head()
        if head_oid is None:
            raise VCSError("no commits on current branch")

        other_oid = self.refs.resolve(branch)
        if other_oid is None:
            raise VCSError(f"unknown branch: {branch}")

        head_tree = Commit.read(self.objects, head_oid).tree

        if other_oid == head_oid:
            return MergeResult(tree_oid=head_tree, conflicts=[])

        base_oid = self.merge_base(head_oid, other_oid)
        base_tree = Commit.read(self.objects, base_oid).tree if base_oid else None
        other_tree = Commit.read(self.objects, other_oid).tree

        if base_oid == other_oid:
            return MergeResult(tree_oid=head_tree, conflicts=[])

        if base_oid == head_oid:
            self._checkout_tree(other_tree)
            self.refs.update_head(other_oid)
            return MergeResult(tree_oid=other_tree, conflicts=[])

        result = merge_trees(self.objects, base_tree, head_tree, other_tree)
        self._checkout_tree(result.tree_oid)

        if not result.conflicts:
            commit = Commit(
                tree=result.tree_oid,
                parents=[head_oid, other_oid],
                author=author,
                committer=author,
                message=f"Merge branch '{branch}'",
                timestamp=time.time(),
            )
            oid = commit.write(self.objects)
            self.refs.update_head(oid)

        return result
