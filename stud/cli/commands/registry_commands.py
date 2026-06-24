"""CLI commands for the container registry."""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


def _load_cfg():
    cfg_path = Path.cwd() / ".stud" / "config.json"
    return json.loads(cfg_path.read_text()) if cfg_path.exists() else {}


def cmd_registry_push(args: argparse.Namespace) -> int:
    from ..ui import get_ui
    ui = get_ui()
    try:
        cfg = _load_cfg()
        remote_url = cfg.get("remote_url", "")
        token = cfg.get("token", "")
        owner = cfg.get("owner", "")
        repo_name = cfg.get("repo", "")

        payload = json.dumps({
            "name": args.name,
            "tag": args.tag,
            "digest": args.digest or f"sha256:{args.name}-{args.tag}",
            "size_bytes": args.size or 0,
            "layers": [],
        }).encode()
        req = urllib.request.Request(
            f"{remote_url}/repos/{owner}/{repo_name}/packages/container",
            data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            img = json.loads(resp.read())
        ui.success(f"Pushed {img['name']}:{img['tag']} ({img['digest'][:16]}…)")
        return 0
    except Exception as e:
        ui.error(str(e))
        return 1


def cmd_registry_list(args: argparse.Namespace) -> int:
    from ..ui import get_ui
    ui = get_ui()
    try:
        cfg = _load_cfg()
        remote_url = cfg.get("remote_url", "")
        token = cfg.get("token", "")
        owner = cfg.get("owner", "")
        repo_name = cfg.get("repo", "")
        req = urllib.request.Request(
            f"{remote_url}/repos/{owner}/{repo_name}/packages/container",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req) as resp:
            imgs = json.loads(resp.read())
        if not imgs:
            ui.print("No images found.")
            return 0
        for i in imgs:
            ui.print(f"  {i['name']}:{i['tag']}  {i['digest'][:20]}…  {i['size_bytes']} bytes  pushed by {i['pushed_by']}")
        return 0
    except Exception as e:
        ui.error(str(e))
        return 1


def register(subparsers):
    reg_p = subparsers.add_parser("registry", help="Container registry management")
    reg_sub = reg_p.add_subparsers(dest="registry_cmd")

    push_p = reg_sub.add_parser("push", help="Record an image push")
    push_p.add_argument("name", help="Image name")
    push_p.add_argument("--tag", default="latest")
    push_p.add_argument("--digest", default=None)
    push_p.add_argument("--size", type=int, default=0)
    push_p.set_defaults(func=cmd_registry_push)

    list_p = reg_sub.add_parser("list", help="List container images")
    list_p.set_defaults(func=cmd_registry_list)

    reg_p.set_defaults(func=lambda args: (reg_p.print_help(), 0)[1])
