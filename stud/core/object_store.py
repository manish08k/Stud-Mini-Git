import os
import zlib
from pathlib import Path
from typing import Iterator, Tuple

from .exceptions import HashMismatchError, ObjectNotFoundError, ObjectStoreError
from .hashing import hash_object


class ObjectStore:
    """
    Content-addressed object store.

    Objects are stored compressed (zlib) under:
        <root>/<oid[:2]>/<oid[2:]>

    The stored payload (before compression) is:
        b"<type> <size>\\0<data>"
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, oid: str) -> Path:
        if len(oid) < 3:
            raise ObjectStoreError(f"invalid object id: {oid!r}")
        return self.root / oid[:2] / oid[2:]

    def exists(self, oid: str) -> bool:
        return self._path_for(oid).exists()

    def write(self, data: bytes, obj_type: str = "blob") -> str:
        oid = hash_object(data, obj_type)
        path = self._path_for(oid)
        if path.exists():
            return oid

        header = f"{obj_type} {len(data)}\0".encode("utf-8")
        compressed = zlib.compress(header + data)

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(path.name + ".tmp")
        with open(tmp_path, "wb") as f:
            f.write(compressed)
        os.replace(tmp_path, path)
        return oid

    def read(self, oid: str) -> Tuple[str, bytes]:
        path = self._path_for(oid)
        if not path.exists():
            raise ObjectNotFoundError(f"object not found: {oid}")

        with open(path, "rb") as f:
            compressed = f.read()

        raw = zlib.decompress(compressed)
        header, _, data = raw.partition(b"\0")
        obj_type, _, size_str = header.decode("utf-8").partition(" ")

        if int(size_str) != len(data):
            raise HashMismatchError(f"size mismatch for object {oid}")

        actual_oid = hash_object(data, obj_type)
        if actual_oid != oid:
            raise HashMismatchError(
                f"object {oid} failed integrity check (got {actual_oid})"
            )

        return obj_type, data

    def read_data(self, oid: str) -> bytes:
        _, data = self.read(oid)
        return data

    def iter_objects(self) -> Iterator[str]:
        for sub in sorted(self.root.iterdir()):
            if not sub.is_dir() or len(sub.name) != 2:
                continue
            for f in sorted(sub.iterdir()):
                if f.is_file() and not f.name.endswith(".tmp"):
                    yield sub.name + f.name

    def delete(self, oid: str) -> None:
        path = self._path_for(oid)
        if path.exists():
            path.unlink()
