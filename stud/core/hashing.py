import hashlib
from pathlib import Path
from typing import BinaryIO, Union

CHUNK_SIZE = 65536


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_stream(stream: BinaryIO, chunk_size: int = CHUNK_SIZE) -> str:
    h = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        h.update(chunk)
    return h.hexdigest()


def sha256_file(path: Union[str, Path], chunk_size: int = CHUNK_SIZE) -> str:
    path = Path(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def hash_object(data: bytes, obj_type: str = "blob") -> str:
    """Git-style content hash: sha256(b"<type> <size>\\0<data>")."""
    header = f"{obj_type} {len(data)}\0".encode("utf-8")
    return sha256_bytes(header + data)
