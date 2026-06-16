import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

from stud.packages import Version, satisfies, max_satisfying


def test_parse():
    v = Version.parse("1.2.3")
    assert (v.major, v.minor, v.patch) == (1, 2, 3)
    assert Version.parse("v1.2.3") == v


def test_ordering():
    assert Version.parse("1.2.3") < Version.parse("1.2.4")
    assert Version.parse("2.0.0-alpha") < Version.parse("2.0.0")
    assert Version.parse("1.0.0") < Version.parse("2.0.0")


@pytest.mark.parametrize("version,constraint,expected", [
    ("1.2.5", "^1.2.3", True),
    ("2.0.0", "^1.2.3", False),
    ("1.2.9", "~1.2.3", True),
    ("1.3.0", "~1.2.3", False),
    ("1.5.0", ">=1.0.0 <2.0.0", True),
    ("0.2.5", "^0.2.3", True),
    ("0.3.0", "^0.2.3", False),
    ("1.2.3", "1.2.3", True),
    ("3.0.0", "1.x || 3.x", True),
    ("2.0.0", "1.x || 3.x", False),
])
def test_satisfies(version, constraint, expected):
    assert satisfies(Version.parse(version), constraint) == expected


def test_max_satisfying():
    versions = [Version.parse(s) for s in ["1.0.0", "1.2.0", "1.3.0", "2.0.0"]]
    best = max_satisfying(versions, "^1.0.0")
    assert str(best) == "1.3.0"
