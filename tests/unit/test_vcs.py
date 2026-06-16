import sys, tempfile
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[3]))

from stud.vcs import VCSService, VCSError


@pytest.fixture
def repo(tmp_path):
    svc = VCSService.init(tmp_path / "repo")
    return svc


def test_init(repo):
    assert repo.stud_dir.exists()
    assert repo.refs.current_branch() == "main"


def test_add_and_commit(repo):
    (repo.work_dir / "a.txt").write_text("hello\n")
    repo.add()
    oid = repo.commit("initial")
    assert repo.refs.get_head() == oid


def test_branch_and_checkout(repo):
    (repo.work_dir / "a.txt").write_text("v1\n")
    repo.add()
    repo.commit("init")
    repo.create_branch("feature")
    repo.checkout("feature")
    assert repo.refs.current_branch() == "feature"


def test_merge_no_conflict(repo):
    (repo.work_dir / "a.txt").write_text("hello\n")
    repo.add()
    repo.commit("init")
    repo.create_branch("feat")
    repo.checkout("feat")
    (repo.work_dir / "b.txt").write_text("world\n")
    repo.add()
    repo.commit("add b")
    repo.checkout("main")
    result = repo.merge("feat")
    assert result.conflicts == []
    assert (repo.work_dir / "b.txt").exists()


def test_nothing_to_commit(repo):
    (repo.work_dir / "a.txt").write_text("hello\n")
    repo.add()
    repo.commit("init")
    with pytest.raises(VCSError, match="nothing to commit"):
        repo.commit("empty")
