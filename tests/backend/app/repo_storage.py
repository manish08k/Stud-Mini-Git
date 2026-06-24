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


# ── S3-backed object storage ──────────────────────────────────────────────────

import os
from typing import Optional


class S3ObjectStore:
    """Mirrors stud ObjectStore API but reads/writes to S3.

    Activate by setting S3_BUCKET (and optionally AWS_REGION).
    Falls back to disk if boto3 is not installed or the env var is missing.
    """

    def __init__(self, bucket: str, prefix: str = "objects/"):
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/"
        try:
            import boto3  # type: ignore
            self._s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        except ImportError:
            self._s3 = None

    def _key(self, oid: str) -> str:
        return f"{self.prefix}{oid[:2]}/{oid}"

    def exists(self, oid: str) -> bool:
        if self._s3 is None:
            return False
        try:
            self._s3.head_object(Bucket=self.bucket, Key=self._key(oid))
            return True
        except Exception:
            return False

    def read(self, oid: str):
        resp = self._s3.get_object(Bucket=self.bucket, Key=self._key(oid))
        data = resp["Body"].read()
        # first 32 bytes encode the object type as a null-terminated string (matches ObjectStore)
        null_idx = data.index(b"\x00")
        obj_type = data[:null_idx].decode()
        return obj_type, data[null_idx + 1:]

    def write(self, data: bytes, obj_type: str) -> str:
        import hashlib
        header = obj_type.encode() + b"\x00"
        full = header + data
        oid = hashlib.sha256(full).hexdigest()
        if not self.exists(oid):
            self._s3.put_object(Bucket=self.bucket, Key=self._key(oid), Body=full)
        return oid


_S3_BUCKET: Optional[str] = os.environ.get("S3_BUCKET")


class HybridRepoStorage(RepoStorage):
    """Use S3 for object storage when S3_BUCKET is set, disk otherwise."""

    def __init__(self, owner: str, name: str):
        super().__init__(owner, name)
        if _S3_BUCKET:
            self._s3_store = S3ObjectStore(
                bucket=_S3_BUCKET,
                prefix=f"repos/{owner}/{name}/objects/",
            )
        else:
            self._s3_store = None

    def has_object(self, oid: str) -> bool:
        if self._s3_store:
            return self._s3_store.exists(oid)
        return super().has_object(oid)

    def read_object(self, oid: str):
        if self._s3_store:
            return self._s3_store.read(oid)
        return super().read_object(oid)

    def write_object(self, data: bytes, obj_type: str) -> str:
        if self._s3_store:
            return self._s3_store.write(data, obj_type)
        return super().write_object(data, obj_type)
