from pathlib import Path

from ...core.exceptions import StudError
from ...vcs.objects import Commit
from ...vcs.remote import HTTPTransport, LocalTransport, Remote
from ...vcs.service import VCSService
from ..manifest import PackageManifest


class GitSource:
    """Fetches a package by cloning a stud VCS repository and checking out a ref."""

    def __init__(self, url: str, ref: str = "main"):
        self.url = url
        self.ref = ref

    def _transport(self):
        if self.url.startswith("http://") or self.url.startswith("https://"):
            return HTTPTransport(self.url)
        return LocalTransport(Path(self.url) / ".stud")

    def fetch(self, dest_dir: Path) -> PackageManifest:
        dest_dir = Path(dest_dir)
        svc = VCSService.init(dest_dir)
        remote = Remote("origin", self._transport(), svc.objects, svc.refs)

        oid = remote.fetch(self.ref)
        if oid is None:
            raise StudError(f"ref not found on remote {self.url!r}: {self.ref}")

        commit = Commit.read(svc.objects, oid)
        svc._checkout_tree(commit.tree)

        if self.ref not in svc.refs.list_branches():
            svc.refs.create_branch(self.ref, oid)
        svc.refs.set_head_symbolic(self.ref)

        manifest_path = dest_dir / "stud.json"
        if not manifest_path.exists():
            raise StudError(f"repository {self.url} is missing stud.json")
        return PackageManifest.load(manifest_path)
