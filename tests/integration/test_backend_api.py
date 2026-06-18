"""Backend API integration tests.

Covers: auth, repos, collaborators, git objects, health endpoints.
Uses FastAPI TestClient with a SQLite in-memory database (shared engine so
tables created by the override are the same ones the app queries).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ── env vars MUST be set before any app import ────────────────────────────────
os.environ["STUD_SERVER_DB_URL"] = "sqlite:///:memory:"
os.environ["KAFKA_ENABLED"] = "false"
os.environ["APP_ENV"] = "test"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

# ── single shared in-memory engine ────────────────────────────────────────────
TEST_DB_URL = "sqlite:///file::test_stud:?mode=memory&cache=shared&uri=true"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False, "uri": True},
)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

# ── patch database engine BEFORE importing app ────────────────────────────────
import backend.app.database as _db_module  # noqa: E402

_db_module.engine = test_engine
_db_module.SessionLocal = TestSession

from backend.app.database import Base, get_db  # noqa: E402
from backend.app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

Base.metadata.create_all(bind=test_engine)


def _override_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_db
client = TestClient(app, raise_server_exceptions=True)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate all tables between tests for isolation."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


# ── helpers ───────────────────────────────────────────────────────────────────

def _register(username: str = "alice", password: str = "secret123") -> str:
    r = client.post("/auth/register", json={"username": username, "password": password})
    assert r.status_code == 200, f"register failed: {r.text}"
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── health ─────────────────────────────────────────────────────────────────────

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready():
    r = client.get("/ready")
    # Redis may be absent in CI — accept 200 or 503
    assert r.status_code in (200, 503)


# ── auth ───────────────────────────────────────────────────────────────────────

def test_register_success():
    r = client.post("/auth/register", json={"username": "bob", "password": "password1"})
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "bob"
    assert "token" in data and len(data["token"]) > 10


def test_register_duplicate():
    _register("alice")
    r = client.post("/auth/register", json={"username": "alice", "password": "other123"})
    assert r.status_code == 400


def test_register_short_password():
    r = client.post("/auth/register", json={"username": "carol", "password": "abc"})
    assert r.status_code == 422  # pydantic validation


def test_login_success():
    _register("alice")
    r = client.post("/auth/login", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 200
    assert "token" in r.json()


def test_login_wrong_password():
    _register("alice")
    r = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user():
    r = client.post("/auth/login", json={"username": "ghost", "password": "pass"})
    assert r.status_code == 401


def test_me():
    tok = _register("alice")
    r = client.get("/auth/me", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_me_unauthorized():
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_bad_token():
    r = client.get("/auth/me", headers={"Authorization": "Bearer bad-token"})
    assert r.status_code == 401


# ── repos ──────────────────────────────────────────────────────────────────────

def test_create_repo():
    tok = _register()
    r = client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok))
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "myrepo"
    assert data["owner"] == "alice"
    assert data["private"] is False


def test_create_private_repo():
    tok = _register()
    r = client.post("/repos", json={"name": "secret", "private": True}, headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["private"] is True


def test_create_repo_duplicate():
    tok = _register()
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok))
    r = client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok))
    assert r.status_code == 400


def test_create_repo_unauthenticated():
    r = client.post("/repos", json={"name": "myrepo"})
    assert r.status_code == 401


def test_list_repos():
    tok = _register()
    client.post("/repos", json={"name": "r1"}, headers=_auth(tok))
    client.post("/repos", json={"name": "r2"}, headers=_auth(tok))
    r = client.get("/repos?owner=alice")
    assert r.status_code == 200
    names = {repo["name"] for repo in r.json()}
    assert {"r1", "r2"} == names


def test_private_repo_hidden_from_anonymous():
    tok = _register()
    client.post("/repos", json={"name": "public"}, headers=_auth(tok))
    client.post("/repos", json={"name": "secret", "private": True}, headers=_auth(tok))
    r = client.get("/repos?owner=alice")
    names = {repo["name"] for repo in r.json()}
    assert "public" in names
    assert "secret" not in names


def test_private_repo_visible_to_owner():
    tok = _register()
    client.post("/repos", json={"name": "secret", "private": True}, headers=_auth(tok))
    r = client.get("/repos?owner=alice", headers=_auth(tok))
    names = {repo["name"] for repo in r.json()}
    assert "secret" in names


def test_get_repo():
    tok = _register()
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok))
    r = client.get("/repos/alice/myrepo")
    assert r.status_code == 200
    assert r.json()["name"] == "myrepo"


def test_get_nonexistent_repo():
    r = client.get("/repos/alice/nonexistent")
    assert r.status_code == 404


def test_update_repo():
    tok = _register()
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok))
    r = client.patch("/repos/alice/myrepo", json={"private": True}, headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["private"] is True


def test_update_repo_default_branch():
    tok = _register()
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok))
    r = client.patch("/repos/alice/myrepo", json={"default_branch": "develop"}, headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["default_branch"] == "develop"


def test_update_repo_non_owner():
    tok_alice = _register("alice")
    tok_bob = _register("bob", "bobpass1")
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok_alice))
    r = client.patch("/repos/alice/myrepo", json={"private": True}, headers=_auth(tok_bob))
    assert r.status_code == 403


def test_delete_repo():
    tok = _register()
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok))
    r = client.delete("/repos/alice/myrepo", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["deleted"] is True


def test_delete_repo_non_owner():
    tok_alice = _register("alice")
    tok_bob = _register("bob", "bobpass1")
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok_alice))
    r = client.delete("/repos/alice/myrepo", headers=_auth(tok_bob))
    assert r.status_code == 403


# ── collaborators ─────────────────────────────────────────────────────────────

def test_add_and_list_collaborator():
    tok_alice = _register("alice")
    _register("bob", "bobpass1")
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok_alice))
    r = client.post(
        "/repos/alice/myrepo/collaborators",
        json={"username": "bob", "role": "write"},
        headers=_auth(tok_alice),
    )
    assert r.status_code == 200
    assert r.json()["username"] == "bob"
    assert r.json()["role"] == "write"

    r2 = client.get("/repos/alice/myrepo/collaborators", headers=_auth(tok_alice))
    assert any(c["username"] == "bob" for c in r2.json())


def test_add_collaborator_invalid_role():
    tok_alice = _register("alice")
    _register("bob", "bobpass1")
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok_alice))
    r = client.post(
        "/repos/alice/myrepo/collaborators",
        json={"username": "bob", "role": "superadmin"},
        headers=_auth(tok_alice),
    )
    assert r.status_code == 400


def test_add_collaborator_unknown_user():
    tok_alice = _register("alice")
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok_alice))
    r = client.post(
        "/repos/alice/myrepo/collaborators",
        json={"username": "ghost", "role": "write"},
        headers=_auth(tok_alice),
    )
    assert r.status_code == 404


def test_remove_collaborator():
    tok_alice = _register("alice")
    _register("bob", "bobpass1")
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok_alice))
    client.post(
        "/repos/alice/myrepo/collaborators",
        json={"username": "bob", "role": "write"},
        headers=_auth(tok_alice),
    )
    r = client.delete("/repos/alice/myrepo/collaborators/bob", headers=_auth(tok_alice))
    assert r.status_code == 200
    assert r.json()["removed"] is True


def test_collaborator_update_role():
    """Adding an existing collaborator with a new role should update it."""
    tok_alice = _register("alice")
    _register("bob", "bobpass1")
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok_alice))
    client.post(
        "/repos/alice/myrepo/collaborators",
        json={"username": "bob", "role": "read"},
        headers=_auth(tok_alice),
    )
    r = client.post(
        "/repos/alice/myrepo/collaborators",
        json={"username": "bob", "role": "admin"},
        headers=_auth(tok_alice),
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_collaborator_requires_admin():
    tok_alice = _register("alice")
    tok_bob = _register("bob", "bobpass1")
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok_alice))
    # Bob (non-admin) tries to add a collaborator
    r = client.post(
        "/repos/alice/myrepo/collaborators",
        json={"username": "alice", "role": "write"},
        headers=_auth(tok_bob),
    )
    assert r.status_code in (403, 404)


def test_collaborator_can_see_private_repo():
    tok_alice = _register("alice")
    tok_bob = _register("bob", "bobpass1")
    client.post("/repos", json={"name": "secret", "private": True}, headers=_auth(tok_alice))
    client.post(
        "/repos/alice/secret/collaborators",
        json={"username": "bob", "role": "read"},
        headers=_auth(tok_alice),
    )
    r = client.get("/repos?owner=alice", headers=_auth(tok_bob))
    names = {repo["name"] for repo in r.json()}
    assert "secret" in names


# ── git objects ────────────────────────────────────────────────────────────────

def test_push_and_fetch_object():
    """Push a blob object then fetch it back by OID."""
    import hashlib
    tok = _register()
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok))
    raw = b"hello stud"
    # Must match stud.core.hashing.hash_object: sha256(b"<type> <size>\0<data>")
    header = f"blob {len(raw)}\0".encode("utf-8")
    oid = hashlib.sha256(header + raw).hexdigest()
    payload = {"type": "blob", "data": raw.hex()}
    r = client.post(f"/repos/alice/myrepo/objects/{oid}", json=payload, headers=_auth(tok))
    assert r.status_code in (200, 201), r.text
    r2 = client.get(f"/repos/alice/myrepo/objects/{oid}", headers=_auth(tok))
    assert r2.status_code == 200
    assert r2.json()["type"] == "blob"


def test_list_refs_empty():
    tok = _register()
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok))
    r = client.get("/repos/alice/myrepo/refs", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json() == {}  # empty before any pushes


def test_update_ref_and_list():
    """Push an object, update a ref pointing to it, then list refs."""
    import hashlib
    tok = _register()
    client.post("/repos", json={"name": "myrepo"}, headers=_auth(tok))
    raw = b"ref test content"
    header = f"blob {len(raw)}\0".encode()
    oid = hashlib.sha256(header + raw).hexdigest()
    # push object
    client.post(
        f"/repos/alice/myrepo/objects/{oid}",
        json={"type": "blob", "data": raw.hex()},
        headers=_auth(tok),
    )
    # update ref
    r = client.post(
        "/repos/alice/myrepo/refs/heads/main",
        json={"oid": oid},
        headers=_auth(tok),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "main"
    assert r.json()["oid"] == oid
    # list refs
    r2 = client.get("/repos/alice/myrepo/refs", headers=_auth(tok))
    assert r2.status_code == 200
    assert "refs/heads/main" in r2.json()


# ── multi-user isolation ───────────────────────────────────────────────────────

def test_two_users_independent_repos():
    tok_alice = _register("alice")
    tok_bob = _register("bob", "bobpass1")
    client.post("/repos", json={"name": "repo"}, headers=_auth(tok_alice))
    client.post("/repos", json={"name": "repo"}, headers=_auth(tok_bob))
    r_alice = client.get("/repos?owner=alice")
    r_bob = client.get("/repos?owner=bob")
    assert len(r_alice.json()) == 1
    assert len(r_bob.json()) == 1
    assert r_alice.json()[0]["owner"] == "alice"
    assert r_bob.json()[0]["owner"] == "bob"
