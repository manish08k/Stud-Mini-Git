from pathlib import Path
from typing import Dict

from stud.core.object_store import ObjectStore
from stud.vcs.refs import RefManager

from .config import REPOS_DIR


class RepoStorage:
    """Bare on-disk storage for one repository, built from stud's own
    ObjectStore + RefManager so the wire format is 100% compatible with
    the existing stud.vcs.remote.HTTPTransport client."""

    def __init__(self, owner: str, name: str):
        self.root = REPOS_DIR / owner / name
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects = ObjectStore(self.root / "objects")
        self.refs = RefManager(self.root)

    @staticmethod
    def delete(owner: str, name: str) -> None:
        import shutil

        root = REPOS_DIR / owner / name
        if root.exists():
            shutil.rmtree(root)

    def list_refs(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for branch in self.refs.list_branches():
            oid = self.refs.read_ref(RefManager.HEADS, branch)
            if oid:
                result[f"refs/heads/{branch}"] = oid
        for tag in self.refs.list_tags():
            oid = self.refs.read_ref(RefManager.TAGS, tag)
            if oid:
                result[f"refs/tags/{tag}"] = oid
        return result

    def has_object(self, oid: str) -> bool:
        return self.objects.exists(oid)

    def read_object(self, oid: str):
        return self.objects.read(oid)

    def write_object(self, data: bytes, obj_type: str) -> str:
        return self.objects.write(data, obj_type)

    def update_ref(self, category: str, name: str, oid: str) -> None:
        self.refs.write_ref(category, name, oid)
