import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Set

from ..core.exceptions import StudError
from ..core.object_store import ObjectStore
from .objects import Commit, Tree
from .refs import RefManager


class RemoteError(StudError):
    pass


class Transport:
    """Abstract transport for talking to a remote repository."""

    def list_refs(self) -> dict:
        raise NotImplementedError

    def has_object(self, oid: str) -> bool:
        raise NotImplementedError

    def fetch_object(self, oid: str) -> bytes:
        raise NotImplementedError

    def push_object(self, oid: str, data: bytes) -> None:
        raise NotImplementedError

    def update_ref(self, category: str, name: str, oid: str) -> None:
        raise NotImplementedError


class LocalTransport(Transport):
    """Transport backed by another local repository (local clones / tests)."""

    def __init__(self, stud_dir: Path):
        self.stud_dir = Path(stud_dir)
        self.objects = ObjectStore(self.stud_dir / "objects")
        self.refs = RefManager(self.stud_dir)

    def list_refs(self) -> dict:
        result = {}
        for name in self.refs.list_branches():
            result[f"refs/heads/{name}"] = self.refs.read_ref(RefManager.HEADS, name)
        for name in self.refs.list_tags():
            result[f"refs/tags/{name}"] = self.refs.read_ref(RefManager.TAGS, name)
        return result

    def has_object(self, oid: str) -> bool:
        return self.objects.exists(oid)

    def fetch_object(self, oid: str) -> bytes:
        obj_type, data = self.objects.read(oid)
        return json.dumps({"type": obj_type, "data": data.hex()}).encode("utf-8")

    def push_object(self, oid: str, raw: bytes) -> None:
        payload = json.loads(raw.decode("utf-8"))
        self.objects.write(bytes.fromhex(payload["data"]), payload["type"])

    def update_ref(self, category: str, name: str, oid: str) -> None:
        self.refs.write_ref(category, name, oid)


class HTTPTransport(Transport):
    """
    Transport that talks to a remote Stud server over HTTP(S) using a small
    JSON-based protocol:

        GET  {base}/refs                   -> {"refs/heads/main": "<oid>", ...}
        GET  {base}/objects/<oid>          -> {"type": "blob", "data": "<hex>"}
        POST {base}/objects/<oid>          <- {"type": "blob", "data": "<hex>"}
        POST {base}/refs/<category>/<name> <- {"oid": "<oid>"}
    """

    def __init__(self, base_url: str, token: Optional[str] = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, body: Optional[bytes] = None) -> bytes:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, data=body, method=method, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except urllib.error.URLError as e:
            raise RemoteError(f"{method} {url} failed: {e}") from e

    def list_refs(self) -> dict:
        return json.loads(self._request("GET", "/refs"))

    def has_object(self, oid: str) -> bool:
        try:
            self._request("GET", f"/objects/{oid}")
            return True
        except RemoteError:
            return False

    def fetch_object(self, oid: str) -> bytes:
        return self._request("GET", f"/objects/{oid}")

    def push_object(self, oid: str, data: bytes) -> None:
        self._request("POST", f"/objects/{oid}", body=data)

    def update_ref(self, category: str, name: str, oid: str) -> None:
        body = json.dumps({"oid": oid}).encode("utf-8")
        self._request("POST", f"/refs/{category}/{name}", body=body)


class Remote:
    """High-level push/pull/fetch operations against a Transport."""

    def __init__(self, name: str, transport: Transport, store: ObjectStore, refs: RefManager):
        self.name = name
        self.transport = transport
        self.store = store
        self.refs = refs

    def _walk_objects(self, oid: str, seen: Set[str]) -> List[str]:
        """Collect oid and all objects it transitively references, in dependency order."""
        result: List[str] = []
        stack = [oid]
        while stack:
            current = stack.pop()
            if current in seen or not self.store.exists(current):
                continue
            seen.add(current)
            result.append(current)

            obj_type, data = self.store.read(current)
            if obj_type == "commit":
                commit = Commit.deserialize(data)
                stack.append(commit.tree)
                stack.extend(commit.parents)
            elif obj_type == "tree":
                tree = Tree.deserialize(data)
                stack.extend(e.oid for e in tree.entries)
        return result

    def push(self, branch: str) -> str:
        oid = self.refs.branch_commit(branch)
        if oid is None:
            raise RemoteError(f"no such local branch: {branch}")

        for object_id in self._walk_objects(oid, set()):
            if not self.transport.has_object(object_id):
                obj_type, data = self.store.read(object_id)
                payload = json.dumps({"type": obj_type, "data": data.hex()}).encode("utf-8")
                self.transport.push_object(object_id, payload)

        self.transport.update_ref(RefManager.HEADS, branch, oid)
        return oid

    def fetch(self, branch: str) -> Optional[str]:
        remote_refs = self.transport.list_refs()
        oid = remote_refs.get(f"refs/heads/{branch}")
        if oid is None:
            return None

        seen: Set[str] = set()
        stack = [oid]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            if self.store.exists(current):
                seen.add(current)
                continue
            seen.add(current)

            raw = self.transport.fetch_object(current)
            payload = json.loads(raw.decode("utf-8"))
            data = bytes.fromhex(payload["data"])
            self.store.write(data, payload["type"])

            if payload["type"] == "commit":
                commit = Commit.deserialize(data)
                stack.append(commit.tree)
                stack.extend(commit.parents)
            elif payload["type"] == "tree":
                tree = Tree.deserialize(data)
                stack.extend(e.oid for e in tree.entries)

        self.refs.write_ref(RefManager.REMOTES, f"{self.name}/{branch}", oid)
        return oid

    def pull(self, branch: str, vcs_service) -> Optional[str]:
        oid = self.fetch(branch)
        if oid is None:
            return None
        result = vcs_service.merge(f"{self.name}/{branch}")
        return result.tree_oid
