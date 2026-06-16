from pathlib import Path
from typing import Optional

from ..packages.manifest import PackageManifest
from ..vcs.service import VCSService
from .ui import UI, get_ui


def init_wizard(directory: Optional[Path] = None, ui: Optional[UI] = None) -> VCSService:
    ui = ui or get_ui()
    directory = Path(directory or Path.cwd())

    ui.rule("Stud Init")
    ui.print("Initializing a new Stud repository.")

    name = ui.prompt("Project name", default=directory.name)
    version = ui.prompt("Version", default="0.1.0")
    description = ui.prompt("Description", default="")
    license_ = ui.prompt("License", default="MIT")

    manifest = PackageManifest(
        name=name,
        version=version,
        description=description,
        license=license_,
    )

    manifest_path = directory / "stud.json"
    if manifest_path.exists():
        if not ui.confirm("stud.json already exists. Overwrite?", default=False):
            ui.warn("Aborted manifest creation.")
        else:
            manifest.save(manifest_path)
            ui.success("stud.json created")
    else:
        manifest.save(manifest_path)
        ui.success("stud.json created")

    ignore_path = directory / ".studignore"
    if not ignore_path.exists():
        ignore_path.write_text(
            "# Stud ignore file\n"
            "stud_modules/\n"
            "dist/\n"
            "build/\n"
            "__pycache__/\n"
            "*.pyc\n"
            ".env\n"
            ".DS_Store\n",
            encoding="utf-8",
        )
        ui.success(".studignore created")

    svc = VCSService.init(directory)
    ui.success(f"Initialized empty Stud repository in {directory / '.stud'}")

    ui.rule()
    ui.print(f"\nNext steps:\n  cd {directory}\n  stud add .\n  stud commit -m 'initial commit'")

    return svc
