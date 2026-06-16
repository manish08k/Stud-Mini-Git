from pathlib import Path
from typing import List, Optional

from ..core.exceptions import StudError


class RefError(StudError):
    pass


class RefManager:
    HEADS = "heads"
    TAGS = "tags"
    REMOTES = "remotes"

    def __init__(self, stud_dir: Path):
        self.stud_dir = Path(stud_dir)
        self.refs_dir = self.stud_dir / "refs"
        (self.refs_dir / self.HEADS).mkdir(parents=True, exist_ok=True)
        (self.refs_dir / self.TAGS).mkdir(parents=True, exist_ok=True)
        self.head_path = self.stud_dir / "HEAD"
        if not self.head_path.exists():
            self.set_head_symbolic("main")

    # -- low level ---------------------------------------------------------

    def _ref_path(self, category: str, name: str) -> Path:
        return self.refs_dir / category / name

    def read_ref(self, category: str, name: str) -> Optional[str]:
        path = self._ref_path(category, name)
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8").strip()
        return content or None

    def write_ref(self, category: str, name: str, oid: str) -> None:
        path = self._ref_path(category, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(oid + "\n", encoding="utf-8")

    def delete_ref(self, category: str, name: str) -> None:
        path = self._ref_path(category, name)
        if path.exists():
            path.unlink()

    def list_refs(self, category: str) -> List[str]:
        base = self.refs_dir / category
        if not base.exists():
            return []
        return sorted(
            str(p.relative_to(base)).replace("\\", "/")
            for p in base.rglob("*")
            if p.is_file()
        )

    # -- branches ------------------------------------------------------------

    def create_branch(self, name: str, oid: str) -> None:
        if self.read_ref(self.HEADS, name) is not None:
            raise RefError(f"branch already exists: {name}")
        self.write_ref(self.HEADS, name, oid)

    def update_branch(self, name: str, oid: str) -> None:
        self.write_ref(self.HEADS, name, oid)

    def delete_branch(self, name: str) -> None:
        if self.current_branch() == name:
            raise RefError(f"cannot delete the currently checked-out branch: {name}")
        if self.read_ref(self.HEADS, name) is None:
            raise RefError(f"no such branch: {name}")
        self.delete_ref(self.HEADS, name)

    def list_branches(self) -> List[str]:
        return self.list_refs(self.HEADS)

    def branch_commit(self, name: str) -> Optional[str]:
        return self.read_ref(self.HEADS, name)

    # -- tags ------------------------------------------------------------------

    def create_tag(self, name: str, oid: str) -> None:
        if self.read_ref(self.TAGS, name) is not None:
            raise RefError(f"tag already exists: {name}")
        self.write_ref(self.TAGS, name, oid)

    def delete_tag(self, name: str) -> None:
        if self.read_ref(self.TAGS, name) is None:
            raise RefError(f"no such tag: {name}")
        self.delete_ref(self.TAGS, name)

    def list_tags(self) -> List[str]:
        return self.list_refs(self.TAGS)

    def tag_commit(self, name: str) -> Optional[str]:
        return self.read_ref(self.TAGS, name)

    # -- HEAD --------------------------------------------------------------------

    def set_head_symbolic(self, branch_name: str) -> None:
        self.head_path.write_text(f"ref: refs/{self.HEADS}/{branch_name}\n", encoding="utf-8")

    def set_head_detached(self, oid: str) -> None:
        self.head_path.write_text(oid + "\n", encoding="utf-8")

    def is_detached(self) -> bool:
        content = self.head_path.read_text(encoding="utf-8").strip()
        return not content.startswith("ref:")

    def current_branch(self) -> Optional[str]:
        content = self.head_path.read_text(encoding="utf-8").strip()
        if content.startswith("ref: refs/"):
            ref = content[len("ref: refs/"):]
            category, _, name = ref.partition("/")
            if category == self.HEADS:
                return name
        return None

    def get_head(self) -> Optional[str]:
        content = self.head_path.read_text(encoding="utf-8").strip()
        if content.startswith("ref:"):
            ref = content[len("ref: "):]
            category, _, name = ref[len("refs/"):].partition("/")
            return self.read_ref(category, name)
        return content or None

    def update_head(self, oid: str) -> None:
        """Move whatever HEAD points at (branch tip, or HEAD itself if detached) to oid."""
        branch = self.current_branch()
        if branch is not None:
            self.update_branch(branch, oid)
        else:
            self.set_head_detached(oid)

    # -- resolution ----------------------------------------------------------------

    def resolve(self, name: str) -> Optional[str]:
        """Resolve a branch, tag, remote-tracking ref, 'HEAD', or raw oid to a commit oid."""
        if name == "HEAD":
            return self.get_head()
        for category in (self.HEADS, self.TAGS, self.REMOTES):
            oid = self.read_ref(category, name)
            if oid:
                return oid
        if len(name) >= 4 and all(c in "0123456789abcdef" for c in name):
            return name
        return None
