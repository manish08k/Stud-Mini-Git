import argparse
from pathlib import Path

from ...core.exceptions import StudError
from ...packages.manifest import PackageManifest
from ...packages.service import PackageService
from ...packages.registry_client import LocalRegistry, RegistryClient
from ..ui import get_ui


def _get_registry(args: argparse.Namespace):
    url = getattr(args, "registry", None) or "https://registry.stud.dev"
    if url.startswith("file://"):
        return LocalRegistry(Path(url[len("file://"):]))
    return RegistryClient(url)


def cmd_install(args: argparse.Namespace) -> int:
    ui = get_ui()
    registry = _get_registry(args)
    svc = PackageService(Path.cwd(), registry)
    try:
        lockfile = svc.install()
        ui.success(f"Installed {len(lockfile.packages)} package(s)")
        return 0
    except StudError as e:
        ui.error(str(e))
        return 1


def cmd_add_pkg(args: argparse.Namespace) -> int:
    ui = get_ui()
    registry = _get_registry(args)
    svc = PackageService(Path.cwd(), registry)
    constraint = args.version or "latest"
    try:
        svc.add_dependency(args.name, constraint, dev=args.dev)
        ui.success(f"Added {args.name}@{constraint}")
        return 0
    except StudError as e:
        ui.error(str(e))
        return 1


def cmd_remove_pkg(args: argparse.Namespace) -> int:
    ui = get_ui()
    registry = _get_registry(args)
    svc = PackageService(Path.cwd(), registry)
    try:
        svc.remove_dependency(args.name, dev=args.dev)
        ui.success(f"Removed {args.name}")
        return 0
    except StudError as e:
        ui.error(str(e))
        return 1


def cmd_publish(args: argparse.Namespace) -> int:
    ui = get_ui()
    registry = _get_registry(args)
    from ...packages.publisher import Publisher
    publisher = Publisher(registry)
    try:
        integrity = publisher.publish(Path(args.directory or Path.cwd()))
        ui.success(f"Published. Integrity: {integrity}")
        return 0
    except StudError as e:
        ui.error(str(e))
        return 1


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("install", help="Install dependencies")
    p.add_argument("--registry")
    p.set_defaults(func=cmd_install)

    p = subparsers.add_parser("add-pkg", help="Add a package dependency")
    p.add_argument("name")
    p.add_argument("--version")
    p.add_argument("--dev", action="store_true")
    p.add_argument("--registry")
    p.set_defaults(func=cmd_add_pkg)

    p = subparsers.add_parser("remove-pkg", help="Remove a package dependency")
    p.add_argument("name")
    p.add_argument("--dev", action="store_true")
    p.add_argument("--registry")
    p.set_defaults(func=cmd_remove_pkg)

    p = subparsers.add_parser("publish", help="Publish package to registry")
    p.add_argument("directory", nargs="?")
    p.add_argument("--registry")
    p.set_defaults(func=cmd_publish)
