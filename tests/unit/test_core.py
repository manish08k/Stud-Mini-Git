import tempfile
from pathlib import Path
import pytest
import sys
sys.path.insert(0, str(Path(__file__).parents[3]))

from stud.core import (
    ObjectStore, IgnoreFilter, EventBus, LockManager,
    ProjectConfig, GlobalConfig, hash_object, sha256_bytes,
    ObjectNotFoundError,
)


def test_object_store_write_read(tmp_path):
    store = ObjectStore(tmp_path / "objects")
    oid = store.write(b"hello world", "blob")
    t, data = store.read(oid)
    assert t == "blob" and data == b"hello world"


def test_object_store_dedup(tmp_path):
    store = ObjectStore(tmp_path / "objects")
    oid1 = store.write(b"same", "blob")
    oid2 = store.write(b"same", "blob")
    assert oid1 == oid2
    assert list(store.iter_objects()) == [oid1]


def test_object_store_not_found(tmp_path):
    store = ObjectStore(tmp_path / "objects")
    with pytest.raises(ObjectNotFoundError):
        store.read("deadbeef00")


def test_ignore_filter():
    ig = IgnoreFilter(["*.pyc", "/build/", "!keep.pyc", "node_modules"])
    assert ig.is_ignored("foo.pyc")
    assert not ig.is_ignored("keep.pyc")
    assert ig.is_ignored("build", is_dir=True)
    assert not ig.is_ignored("build", is_dir=False)
    assert ig.is_ignored("src/node_modules/x.js")


def test_event_bus():
    bus = EventBus()
    hits = []
    bus.on("save", lambda x: hits.append(x))
    bus.emit("save", 42)
    assert hits == [42]


def test_lock_manager(tmp_path):
    lm = LockManager(tmp_path / "locks")
    with lm.acquire("repo") as lk:
        assert lk.locked
    assert not lk.locked


def test_project_config_roundtrip(tmp_path):
    pc = ProjectConfig(name="myapp", version="1.0.0", dependencies={"fastapi": "^0.110"})
    pc.save(tmp_path / "stud.json")
    pc2 = ProjectConfig.load(tmp_path / "stud.json")
    assert pc2.name == "myapp"
    assert pc2.dependencies["fastapi"] == "^0.110"
