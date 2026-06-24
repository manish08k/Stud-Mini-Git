from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Optional

from jose import JWTError, jwt

from .config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY

PBKDF2_ITERATIONS = 200_000
REFRESH_TOKEN_EXPIRE_DAYS = 30
_LOGIN_ATTEMPT_PREFIX = "login_fail:"
_LOCKOUT_THRESHOLD = 5
_LOCKOUT_WINDOW = 300  # 5 min


# ── passwords ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": time.time() + JWT_EXPIRE_MINUTES * 60,
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": time.time() + REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        "type": "refresh",
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        data = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if data.get("type") != "access":
            return None
        return data
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[dict]:
    try:
        data = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if data.get("type") != "refresh":
            return None
        return data
    except JWTError:
        return None


# ── opaque token (legacy / PAT) ───────────────────────────────────────────────

def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── brute-force protection ────────────────────────────────────────────────────

def record_failed_login(username: str) -> None:
    from .redis_client import _get_client
    r = _get_client()
    if r is None:
        return
    key = f"{_LOGIN_ATTEMPT_PREFIX}{username}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, _LOCKOUT_WINDOW)
    pipe.execute()


def is_locked_out(username: str) -> bool:
    from .redis_client import _get_client
    r = _get_client()
    if r is None:
        return False  # fail open
    key = f"{_LOGIN_ATTEMPT_PREFIX}{username}"
    count = r.get(key)
    return int(count) >= _LOCKOUT_THRESHOLD if count else False


def clear_failed_logins(username: str) -> None:
    from .redis_client import _get_client
    r = _get_client()
    if r is None:
        return
    r.delete(f"{_LOGIN_ATTEMPT_PREFIX}{username}")
