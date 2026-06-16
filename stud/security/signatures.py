import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Signature:
    signer: str
    timestamp: float
    algorithm: str
    digest: str
    signature: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Signature":
        return cls(**json.loads(text))


class SignatureError(Exception):
    pass


class Signer:
    """HMAC-SHA256-based package signer (swap for real asymmetric crypto in production)."""

    ALGORITHM = "hmac-sha256"

    def __init__(self, identity: str, secret_key: bytes):
        self.identity = identity
        self.secret_key = secret_key

    @staticmethod
    def _file_digest(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def sign_file(self, path: Path) -> Signature:
        digest = self._file_digest(path)
        mac = hmac.new(self.secret_key, digest.encode("utf-8"), hashlib.sha256).hexdigest()
        return Signature(
            signer=self.identity,
            timestamp=time.time(),
            algorithm=self.ALGORITHM,
            digest=digest,
            signature=mac,
        )

    def verify_file(self, path: Path, sig: Signature) -> bool:
        digest = self._file_digest(path)
        if digest != sig.digest:
            raise SignatureError("file digest mismatch")
        expected_mac = hmac.new(self.secret_key, sig.digest.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig.signature, expected_mac):
            raise SignatureError("signature verification failed")
        return True


def sign_package(tarball: Path, identity: str, secret_key: bytes,
                  sig_path: Optional[Path] = None) -> Signature:
    signer = Signer(identity, secret_key)
    sig = signer.sign_file(tarball)
    if sig_path:
        Path(sig_path).write_text(sig.to_json(), encoding="utf-8")
    return sig


def verify_package(tarball: Path, sig_path: Path, secret_key: bytes) -> bool:
    sig = Signature.from_json(Path(sig_path).read_text(encoding="utf-8"))
    signer = Signer(sig.signer, secret_key)
    return signer.verify_file(tarball, sig)
