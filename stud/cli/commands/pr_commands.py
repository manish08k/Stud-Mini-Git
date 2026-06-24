"""CLI commands for pull requests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..ui import get_ui


def _client():
    from ...vcs.remote import HTTPTransport
    from ...core.config import load_config
    cfg = load_config(Path.cwd())
    remote_url = cfg.get("remote_url") or cfg.get("remote", {}).get("url", "")
    token = cfg.get("token", "")
    return HTTPTransport(remote_url, token=token)


def cmd_pr_list(args: argparse.Namespace) -> int:
    ui = get_ui()
    from ...vcs.service import VCSService
    svc = VCSService(Path.cwd())
    try:
        import urllib.request, urllib.error, json as _json
        cfg = svc.stud_dir.parent / ".stud" / "config.json"
        data = _json.loads(cfg.read_text()) if cfg.exists() else {}
        remote_url = data.get("remote_url", "")
        token = data.get("token", "")
        owner = data.get("owner", "")
        repo_name = data.get("repo", "")
        if not (remote_url and owner and repo_name):
            ui.error("no remote configured – run `stud remote add`")
            return 1
        url = f"{remote_url}/repos/{owner}/{repo_name}/pulls"
        if args.status:
            url += f"?status={args.status}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as resp:
            prs = _json.loads(resp.read())
        if not prs:
            ui.print("No pull requests found.")
            return 0
        for pr in prs:
            ui.print(f"  #{pr['number']}  [{pr['status']}]  {pr['title']}  ({pr['head_branch']} → {pr['base_branch']})  by {pr['author']}")
        return 0
    except Exception as e:
        ui.error(str(e))
        return 1


def cmd_pr_create(args: argparse.Namespace) -> int:
    ui = get_ui()
    try:
        import urllib.request, json as _json
        from pathlib import Path as _P
        svc_dir = _P.cwd() / ".stud"
        cfg_path = svc_dir / "config.json"
        data = _json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
        remote_url = data.get("remote_url", "")
        token = data.get("token", "")
        owner = data.get("owner", "")
        repo_name = data.get("repo", "")
        payload = _json.dumps({
            "title": args.title,
            "description": args.description or "",
            "base_branch": args.base or "main",
            "head_branch": args.head,
        }).encode()
        req = urllib.request.Request(
            f"{remote_url}/repos/{owner}/{repo_name}/pulls",
            data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            pr = _json.loads(resp.read())
        ui.success(f"Created PR #{pr['number']}: {pr['title']}")
        return 0
    except Exception as e:
        ui.error(str(e))
        return 1


def cmd_pr_merge(args: argparse.Namespace) -> int:
    ui = get_ui()
    try:
        import urllib.request, json as _json
        from pathlib import Path as _P
        cfg_path = _P.cwd() / ".stud" / "config.json"
        data = _json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
        remote_url = data.get("remote_url", "")
        token = data.get("token", "")
        owner = data.get("owner", "")
        repo_name = data.get("repo", "")
        req = urllib.request.Request(
            f"{remote_url}/repos/{owner}/{repo_name}/pulls/{args.number}/merge",
            data=b"{}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            pr = _json.loads(resp.read())
        ui.success(f"Merged PR #{pr['number']}")
        return 0
    except Exception as e:
        ui.error(str(e))
        return 1


def register(subparsers):
    pr_p = subparsers.add_parser("pr", help="Pull request management")
    pr_sub = pr_p.add_subparsers(dest="pr_cmd")

    ls = pr_sub.add_parser("list", help="List pull requests")
    ls.add_argument("--status", choices=["open", "merged", "closed"], default=None)
    ls.set_defaults(func=cmd_pr_list)

    cr = pr_sub.add_parser("create", help="Open a pull request")
    cr.add_argument("--title", required=True)
    cr.add_argument("--head", required=True, help="Source branch")
    cr.add_argument("--base", default="main", help="Target branch")
    cr.add_argument("--description", default="")
    cr.set_defaults(func=cmd_pr_create)

    mg = pr_sub.add_parser("merge", help="Merge a pull request")
    mg.add_argument("number", type=int)
    mg.set_defaults(func=cmd_pr_merge)

    pr_p.set_defaults(func=lambda args: (pr_p.print_help(), 0)[1])
