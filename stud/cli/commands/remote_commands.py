import argparse
import getpass
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from ...core.config import GlobalConfig
from ...core.exceptions import StudError
from ...vcs.objects import Commit
from ...vcs.refs import RefManager
from ...vcs.remote import HTTPTransport, Remote, RemoteError
from ...vcs.service import VCSService
from ..ui import get_ui


def _get_svc(path: Optional[Path] = None) -> VCSService:
    return VCSService(Path(path or Path.cwd()))


def _remotes_path(stud_dir: Path) -> Path:
    return stud_dir / "remotes.json"


def _load_remotes(stud_dir: Path) -> dict:
    path = _remotes_path(stud_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_remotes(stud_dir: Path, remotes: dict) -> None:
    _remotes_path(stud_dir).write_text(json.dumps(remotes, indent=2, sort_keys=True), encoding="utf-8")


def _set_remote(stud_dir: Path, name: str, url: str) -> None:
    remotes = _load_remotes(stud_dir)
    remotes[name] = url
    _save_remotes(stud_dir, remotes)


def _server_root(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _get_token_for(url: str) -> Optional[str]:
    cfg = GlobalConfig.load()
    servers = cfg.extra.get("servers", {})
    return servers.get(_server_root(url))


def _save_token(url: str, token: str) -> None:
    cfg = GlobalConfig.load()
    servers = cfg.extra.setdefault("servers", {})
    servers[_server_root(url)] = token
    cfg.save()


def _http_post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise StudError(f"server error {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise StudError(f"could not reach server: {e}") from e


def cmd_remote(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    remotes = _load_remotes(svc.stud_dir)

    if args.add:
        name, url = args.add
        remotes[name] = url
        _save_remotes(svc.stud_dir, remotes)
        ui.success(f"Added remote '{name}' -> {url}")
    elif args.remove:
        remotes.pop(args.remove, None)
        _save_remotes(svc.stud_dir, remotes)
        ui.success(f"Removed remote '{args.remove}'")
    else:
        for name, url in sorted(remotes.items()):
            ui.print(f"{name}\t{url}")
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    remotes = _load_remotes(svc.stud_dir)
    url = remotes.get(args.remote)
    if not url:
        ui.error(f"no such remote: {args.remote}")
        return 1

    branch = args.branch or svc.refs.current_branch()
    if not branch:
        ui.error("no current branch to push")
        return 1

    token = _get_token_for(url)
    transport = HTTPTransport(url, token=token)
    remote = Remote(args.remote, transport, svc.objects, svc.refs)
    try:
        oid = remote.push(branch)
    except RemoteError as e:
        ui.error(str(e))
        return 1

    ui.success(f"Pushed '{branch}' -> {args.remote} ({oid[:8]})")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    remotes = _load_remotes(svc.stud_dir)
    url = remotes.get(args.remote)
    if not url:
        ui.error(f"no such remote: {args.remote}")
        return 1

    branch = args.branch or svc.refs.current_branch()
    if not branch:
        ui.error("no current branch to pull into")
        return 1

    token = _get_token_for(url)
    transport = HTTPTransport(url, token=token)
    remote = Remote(args.remote, transport, svc.objects, svc.refs)
    try:
        result = remote.pull(branch, svc)
    except RemoteError as e:
        ui.error(str(e))
        return 1

    if result is None:
        ui.print(f"remote branch '{branch}' not found")
        return 0

    ui.success(f"Pulled '{branch}' from {args.remote}")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    ui = get_ui()
    svc = _get_svc()
    remotes = _load_remotes(svc.stud_dir)
    url = remotes.get(args.remote)
    if not url:
        ui.error(f"no such remote: {args.remote}")
        return 1

    token = _get_token_for(url)
    transport = HTTPTransport(url, token=token)
    remote = Remote(args.remote, transport, svc.objects, svc.refs)
    try:
        oid = remote.fetch(args.branch)
    except RemoteError as e:
        ui.error(str(e))
        return 1

    if oid is None:
        ui.print(f"remote branch '{args.branch}' not found")
        return 0
    ui.success(f"Fetched {args.remote}/{args.branch} -> {oid[:8]}")
    return 0


def cmd_clone(args: argparse.Namespace) -> int:
    ui = get_ui()
    url = args.url
    directory = args.directory or url.rstrip("/").split("/")[-1]
    token = _get_token_for(url)
    transport = HTTPTransport(url, token=token)

    try:
        refs = transport.list_refs()
    except RemoteError as e:
        ui.error(str(e))
        return 1

    svc = VCSService.init(Path(directory))
    remote = Remote("origin", transport, svc.objects, svc.refs)
    _set_remote(svc.stud_dir, "origin", url)
    if token:
        _save_token(url, token)

    branches = sorted(k[len("refs/heads/"):] for k in refs if k.startswith("refs/heads/"))
    if not branches:
        ui.success(f"Cloned empty repository into '{directory}'")
        return 0

    branch = args.branch or ("main" if "main" in branches else branches[0])
    try:
        oid = remote.fetch(branch)
    except RemoteError as e:
        ui.error(str(e))
        return 1

    if oid is not None:
        svc.refs.write_ref(RefManager.HEADS, branch, oid)
        svc.refs.set_head_symbolic(branch)
        commit = Commit.read(svc.objects, oid)
        svc._checkout_tree(commit.tree)

    ui.success(f"Cloned into '{directory}' (branch '{branch}')")
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    ui = get_ui()
    password = args.password or getpass.getpass("Password: ")
    data = _http_post_json(
        f"{args.server.rstrip('/')}/auth/register",
        {"username": args.username, "password": password},
    )
    _save_token(args.server, data["token"])
    ui.success(f"Registered '{data['username']}' on {args.server}")
    ui.print(f"token: {data['token']}")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    ui = get_ui()
    password = args.password or getpass.getpass("Password: ")
    data = _http_post_json(
        f"{args.server.rstrip('/')}/auth/login",
        {"username": args.username, "password": password},
    )
    _save_token(args.server, data["token"])
    ui.success(f"Logged in as '{data['username']}' on {args.server}")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("remote", help="Manage remotes")
    p.add_argument("--add", nargs=2, metavar=("NAME", "URL"))
    p.add_argument("--remove", metavar="NAME")
    p.set_defaults(func=cmd_remote)

    p = subparsers.add_parser("push", help="Push a branch to a remote")
    p.add_argument("remote", nargs="?", default="origin")
    p.add_argument("branch", nargs="?", default=None)
    p.set_defaults(func=cmd_push)

    p = subparsers.add_parser("pull", help="Pull and merge a branch from a remote")
    p.add_argument("remote", nargs="?", default="origin")
    p.add_argument("branch", nargs="?", default=None)
    p.set_defaults(func=cmd_pull)

    p = subparsers.add_parser("fetch", help="Fetch a branch from a remote")
    p.add_argument("remote", nargs="?", default="origin")
    p.add_argument("branch")
    p.set_defaults(func=cmd_fetch)

    p = subparsers.add_parser("clone", help="Clone a remote repository")
    p.add_argument("url")
    p.add_argument("directory", nargs="?", default=None)
    p.add_argument("--branch", default=None)
    p.set_defaults(func=cmd_clone)

    p = subparsers.add_parser("register", help="Create an account on a stud server")
    p.add_argument("server")
    p.add_argument("username")
    p.add_argument("--password", default=None)
    p.set_defaults(func=cmd_register)

    p = subparsers.add_parser("login", help="Log in to a stud server")
    p.add_argument("server")
    p.add_argument("username")
    p.add_argument("--password", default=None)
    p.set_defaults(func=cmd_login)
