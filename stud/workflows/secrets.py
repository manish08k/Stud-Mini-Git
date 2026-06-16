import base64
import json
import os
from pathlib import Path
from typing import Dict, Optional

from ..core.exceptions import StudError

try:
    from cryptography.fernet import Fernet
    _HAS_CRYPTOGRAPHY = True
except ImportError:
    _HAS_CRYPTOGRAPHY = False


class SecretsError(StudError):
    pass


class SecretsStore:
    """
    Encrypted key-value secret storage backed by a JSON file.
    Uses Fernet (AES-128-CBC + HMAC-SHA256) when the cryptography library is
    available; falls back to plain-text storage (dev/test only).
    """

    KEYFILE_NAME = ".stud_secrets_key"
    STORE_NAME = "secrets.json"

    def __init__(self, store_dir: Path):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.store_path = self.store_dir / self.STORE_NAME
        self.key_path = self.store_dir / self.KEYFILE_NAME
        self._fernet = None

        if _HAS_CRYPTOGRAPHY:
            self._fernet = self._load_or_create_key()

    def _load_or_create_key(self):
        from cryptography.fernet import Fernet
        if self.key_path.exists():
            key = self.key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
            try:
                self.key_path.chmod(0o600)
            except OSError:
                pass
        return Fernet(key)

    def _load_raw(self) -> Dict[str, str]:
        if not self.store_path.exists():
            return {}
        with open(self.store_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_raw(self, data: Dict[str, str]) -> None:
        tmp = self.store_path.with_name(self.store_path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        tmp.replace(self.store_path)

    def _encrypt(self, value: str) -> str:
        if self._fernet:
            return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    def _decrypt(self, token: str) -> str:
        if self._fernet:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        return base64.b64decode(token.encode("ascii")).decode("utf-8")

    def set(self, name: str, value: str) -> None:
        data = self._load_raw()
        data[name] = self._encrypt(value)
        self._save_raw(data)

    def get(self, name: str) -> Optional[str]:
        data = self._load_raw()
        if name not in data:
            return None
        return self._decrypt(data[name])

    def delete(self, name: str) -> None:
        data = self._load_raw()
        data.pop(name, None)
        self._save_raw(data)

    def list(self):
        return list(self._load_raw().keys())

    def as_env(self, names=None) -> Dict[str, str]:
        data = self._load_raw()
        result = {}
        keys = names if names is not None else list(data.keys())
        for k in keys:
            if k in data:
                result[k] = self._decrypt(data[k])
        return result
