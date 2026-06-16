import sys, tempfile, shutil
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[3]))

from stud.packages import (
    Version, PackageManifest, Lockfile, LockedPackage,
    Resolver, LocalRegistry, Publisher, PackageService,
)


@pytest.fixture
def registry(tmp_path):
    reg = LocalRegistry(tmp_path / "registry")
    pub = Publisher(reg)

    for name, version, deps in [
        ("left-pad", "1.2.0", {"core-utils": "^2.0.0"}),
        ("left-pad", "1.0.0", {}),
        ("core-utils", "2.1.0", {}),
    ]:
        d = tmp_path / f"{name}-{version}"
        d.mkdir(exist_ok=True)
        PackageManifest(name=name, version=version, dependencies=deps).save(d / "stud.json")
        (d / "index.js").write_text("module.exports={};\n")
        pub.publish(d)

    return reg


def test_resolve(registry):
    resolved = Resolver(registry).resolve({"left-pad": "^1.0.0"})
    assert str(resolved["left-pad"].version) == "1.2.0"
    assert str(resolved["core-utils"].version) == "2.1.0"


def test_install(registry, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    PackageManifest(name="myapp", version="1.0.0",
                     dependencies={"left-pad": "^1.0.0"}).save(project / "stud.json")
    svc = PackageService(project, registry)
    lf = svc.install()
    assert (project / "stud_modules" / "left-pad" / "index.js").exists()
    assert lf.get("left-pad", "1.2.0") is not None
