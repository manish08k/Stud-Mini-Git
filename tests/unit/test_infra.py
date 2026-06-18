"""Unit tests for infrastructure modules (Redis, Kafka, logging, config)."""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("STUD_SERVER_DB_URL", "sqlite:///:memory:")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("APP_ENV", "test")


# ── logging ───────────────────────────────────────────────────────────────────

class TestJSONLogging:
    def test_json_output(self, capsys):
        from backend.app.logging_config import _JSONFormatter

        formatter = _JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["msg"] == "hello world"
        assert "ts" in data
        assert "service" in data

    def test_get_logger(self):
        from backend.app.logging_config import get_logger
        logger = get_logger("mymodule")
        assert logger.name == "mymodule"


# ── config ────────────────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        from backend.app import config
        assert config.DATABASE_URL.startswith("sqlite")
        assert isinstance(config.CORS_ORIGINS, list)
        assert config.RATE_LIMIT_PER_MINUTE > 0

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "999")
        # re-import to pick up monkeypatched value
        import importlib
        import backend.app.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.RATE_LIMIT_PER_MINUTE == 999

    def test_cors_parsing(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")
        import importlib
        import backend.app.config as cfg_module
        importlib.reload(cfg_module)
        assert "http://a.com" in cfg_module.CORS_ORIGINS
        assert "http://b.com" in cfg_module.CORS_ORIGINS


# ── redis client (mocked) ─────────────────────────────────────────────────────

class TestRedisClient:
    def test_cache_get_returns_none_on_miss(self, monkeypatch):
        from backend.app import redis_client
        monkeypatch.setattr(redis_client, "_client", None)
        monkeypatch.setattr(redis_client, "_get_client", lambda: None)
        assert redis_client.cache_get("missing_key") is None

    def test_cache_set_noop_when_no_client(self, monkeypatch):
        from backend.app import redis_client
        monkeypatch.setattr(redis_client, "_get_client", lambda: None)
        redis_client.cache_set("k", "v")  # should not raise

    def test_rate_limit_allow_when_no_redis(self, monkeypatch):
        from backend.app import redis_client
        monkeypatch.setattr(redis_client, "_get_client", lambda: None)
        assert redis_client.rate_limit_check("user:1", limit=10) is True

    def test_rate_limit_deny_with_mock(self, monkeypatch):
        """Simulate Redis returning count > limit."""
        from backend.app import redis_client

        class FakePipeline:
            def incr(self, k): return self
            def expire(self, k, s): return self
            def execute(self): return (11, True)

        class FakeRedis:
            def pipeline(self): return FakePipeline()

        monkeypatch.setattr(redis_client, "_get_client", lambda: FakeRedis())
        assert redis_client.rate_limit_check("user:2", limit=10) is False

    def test_cache_roundtrip_with_mock(self, monkeypatch):
        from backend.app import redis_client
        store: dict = {}

        class FakeRedis:
            def get(self, k): return store.get(k)
            def setex(self, k, ttl, v): store[k] = v
            def delete(self, *keys):
                for k in keys: store.pop(k, None)
            def keys(self, pattern): return list(store.keys())
            def ping(self): return True

        fake = FakeRedis()
        monkeypatch.setattr(redis_client, "_client", fake)
        monkeypatch.setattr(redis_client, "_get_client", lambda: fake)

        redis_client.cache_set("mykey", {"val": 42}, ttl=10)
        result = redis_client.cache_get("mykey")
        assert result == {"val": 42}

        redis_client.cache_delete("mykey")
        assert redis_client.cache_get("mykey") is None


# ── kafka client ──────────────────────────────────────────────────────────────

class TestKafkaClient:
    def test_producer_noop_when_disabled(self):
        os.environ["KAFKA_ENABLED"] = "false"
        import importlib
        import backend.app.kafka_client as kc
        importlib.reload(kc)
        p = kc.KafkaProducer()
        p.send("test-topic", {"x": 1})  # must not raise
        p.close()

    def test_emit_event_noop(self, monkeypatch):
        from backend.app import kafka_client
        sent = []
        monkeypatch.setattr(
            kafka_client, "get_producer",
            lambda: type("P", (), {"send": lambda self, t, p: sent.append((t, p))})()
        )
        kafka_client.emit_event("push", {"repo": "alice/myrepo"})
        assert len(sent) == 1
        assert sent[0][1]["event"] == "push"


# ── security module ───────────────────────────────────────────────────────────

class TestSecurity:
    def test_hash_password_and_verify(self):
        from backend.app.security import hash_password, verify_password
        h = hash_password("mypassword")
        assert h != "mypassword"
        assert verify_password("mypassword", h)
        assert not verify_password("wrong", h)

    def test_create_and_decode_token(self):
        from backend.app.security import generate_token, hash_token
        token = generate_token()
        assert isinstance(token, str) and len(token) > 10
        hashed = hash_token(token)
        assert hashed != token
        assert len(hashed) == 64  # sha256 hex

    def test_invalid_token_hash_differs(self):
        from backend.app.security import hash_token
        assert hash_token("abc") != hash_token("xyz")


# ── database module ───────────────────────────────────────────────────────────

class TestDatabase:
    def test_session_local_creates_session(self):
        from backend.app.database import SessionLocal
        db = SessionLocal()
        assert db is not None
        db.close()

    def test_get_db_yields_session(self):
        from backend.app.database import get_db
        gen = get_db()
        db = next(gen)
        assert db is not None
        try:
            next(gen)
        except StopIteration:
            pass


# ── repo_storage module ───────────────────────────────────────────────────────

class TestRepoStorage:
    def test_write_and_read_object(self, tmp_path, monkeypatch):
        from backend.app import repo_storage as rs
        monkeypatch.setattr(rs, "REPOS_DIR", tmp_path)
        storage = rs.RepoStorage("alice", "myrepo")
        data = b"hello world"
        oid = storage.write_object(data, "blob")
        assert isinstance(oid, str) and len(oid) == 64
        assert storage.has_object(oid)
        obj_type, read_data = storage.read_object(oid)
        assert obj_type == "blob"
        assert read_data == data

    def test_has_object_false_for_missing(self, tmp_path, monkeypatch):
        from backend.app import repo_storage as rs
        monkeypatch.setattr(rs, "REPOS_DIR", tmp_path)
        storage = rs.RepoStorage("alice", "myrepo")
        assert not storage.has_object("a" * 64)

    def test_write_and_list_refs(self, tmp_path, monkeypatch):
        from backend.app import repo_storage as rs
        monkeypatch.setattr(rs, "REPOS_DIR", tmp_path)
        storage = rs.RepoStorage("alice", "myrepo")
        storage.update_ref("heads", "main", "a" * 64)
        refs = storage.list_refs()
        # list_refs returns a dict: {"refs/heads/main": oid}
        assert "refs/heads/main" in refs
        assert refs["refs/heads/main"] == "a" * 64

    def test_write_ref_and_read_ref(self, tmp_path, monkeypatch):
        from backend.app import repo_storage as rs
        monkeypatch.setattr(rs, "REPOS_DIR", tmp_path)
        storage = rs.RepoStorage("alice", "myrepo")
        storage.update_ref("heads", "develop", "b" * 64)
        refs = storage.list_refs()
        assert "refs/heads/develop" in refs


# ── git router edge cases ─────────────────────────────────────────────────────

class TestGitRouter:
    """Hit lines not covered by integration tests (object read errors, ref update)."""

    def setup_method(self):
        import os
        os.environ.setdefault("STUD_SERVER_DB_URL", "sqlite:///:memory:")
        os.environ.setdefault("KAFKA_ENABLED", "false")

    def test_get_object_not_found(self, tmp_path, monkeypatch):
        from backend.app import repo_storage as rs
        monkeypatch.setattr(rs, "REPOS_DIR", tmp_path)
        storage = rs.RepoStorage("alice", "myrepo")
        assert not storage.has_object("c" * 64)

    def test_duplicate_write_is_idempotent(self, tmp_path, monkeypatch):
        from backend.app import repo_storage as rs
        monkeypatch.setattr(rs, "REPOS_DIR", tmp_path)
        storage = rs.RepoStorage("alice", "myrepo")
        data = b"idempotent"
        oid1 = storage.write_object(data, "blob")
        oid2 = storage.write_object(data, "blob")
        assert oid1 == oid2


# ── telemetry no-op when sdk absent ───────────────────────────────────────────

class TestTelemetry:
    def test_setup_tracing_no_op_without_sdk(self, monkeypatch):
        import sys
        # Remove otel from sys.modules so the import inside setup_tracing fails
        otel_mods = [k for k in sys.modules if k.startswith("opentelemetry")]
        backup = {k: sys.modules.pop(k) for k in otel_mods}
        try:
            import importlib
            import backend.app.telemetry as tel
            importlib.reload(tel)
            tel.setup_tracing()  # must not raise
        finally:
            sys.modules.update(backup)


# ── redis publish_event ───────────────────────────────────────────────────────

class TestRedisPublish:
    def test_publish_event_with_mock(self, monkeypatch):
        from backend.app import redis_client
        published = []

        class FakeRedis:
            def publish(self, ch, msg): published.append((ch, msg))

        monkeypatch.setattr(redis_client, "_get_client", lambda: FakeRedis())
        redis_client.publish_event("stud.events", {"event": "push"})
        assert len(published) == 1
        assert "push" in published[0][1]

    def test_publish_noop_without_redis(self, monkeypatch):
        from backend.app import redis_client
        monkeypatch.setattr(redis_client, "_get_client", lambda: None)
        redis_client.publish_event("ch", {"x": 1})  # must not raise

    def test_cache_delete_pattern_with_mock(self, monkeypatch):
        from backend.app import redis_client
        store = {"key:1": "a", "key:2": "b", "other": "c"}

        class FakeRedis:
            def keys(self, pattern): return [k for k in store if k.startswith("key")]
            def delete(self, *keys):
                for k in keys: store.pop(k, None)

        monkeypatch.setattr(redis_client, "_get_client", lambda: FakeRedis())
        redis_client.cache_delete_pattern("key*")
        assert "key:1" not in store
        assert "key:2" not in store
        assert "other" in store
