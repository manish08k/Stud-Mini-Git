import argparse
from pathlib import Path

from ...security.audit import AuditService
from ...security.secret_scanner import scan_directory
from ...security.signatures import sign_package, verify_package
from ...security.vuln_scanner import VulnScanner
from ...packages.manifest import PackageManifest
from ..ui import get_ui


def cmd_audit(args: argparse.Namespace) -> int:
    ui = get_ui()
    project_dir = Path.cwd()

    try:
        manifest = PackageManifest.load(project_dir / "stud.json")
        packages = {**manifest.dependencies, **manifest.dev_dependencies}
    except Exception:
        packages = {}

    svc = AuditService(project_dir, vuln_scanner=VulnScanner(offline_db={}))
    report = svc.run_full_audit(packages, project_name=getattr(manifest, "name", "project") if packages else "project")

    summary = report.summary()
    ui.rule("Security Audit Report")
    ui.table(
        ["Metric", "Count"],
        [
            ["Vulnerabilities", summary["total_vulnerabilities"]],
            ["Secrets found", summary["secret_findings"]],
            ["Critical issues", int(summary["has_critical"])],
        ],
        title="Summary",
    )

    if report.secret_findings:
        ui.warn(f"{len(report.secret_findings)} potential secret(s) found:")
        for f in report.secret_findings[:10]:
            ui.print(f"  [{f.rule}] {f.file}:{f.line} -> {f.matched[:60]}")

    if report.has_critical:
        ui.error("CRITICAL vulnerabilities found!")
        return 2

    if summary["total_vulnerabilities"] > 0:
        ui.warn("Vulnerabilities found. Review and update affected packages.")
        return 1

    ui.success("No known vulnerabilities found.")
    return 0


def cmd_scan_secrets(args: argparse.Namespace) -> int:
    ui = get_ui()
    root = Path(args.directory or Path.cwd())
    findings = scan_directory(root)

    if not findings:
        ui.success("No secrets detected.")
        return 0

    ui.warn(f"{len(findings)} potential secret(s) detected:")
    for f in findings:
        ui.print(f"  [{f.rule}] {f.file}:{f.line}:{f.col}  {f.matched[:80]}")
    return 1


def cmd_sign(args: argparse.Namespace) -> int:
    ui = get_ui()
    key = args.key.encode("utf-8")
    try:
        sig = sign_package(Path(args.file), args.identity, key, sig_path=Path(args.output) if args.output else None)
        ui.success(f"Signed {args.file}  digest={sig.digest[:16]}...")
        return 0
    except Exception as e:
        ui.error(str(e))
        return 1


def cmd_verify(args: argparse.Namespace) -> int:
    ui = get_ui()
    key = args.key.encode("utf-8")
    try:
        ok = verify_package(Path(args.file), Path(args.sig), key)
        if ok:
            ui.success("Signature verified.")
        return 0 if ok else 1
    except Exception as e:
        ui.error(str(e))
        return 1


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("audit", help="Run security audit")
    p.set_defaults(func=cmd_audit)

    p = subparsers.add_parser("scan-secrets", help="Scan for secrets in source code")
    p.add_argument("directory", nargs="?")
    p.set_defaults(func=cmd_scan_secrets)

    p = subparsers.add_parser("sign", help="Sign a package tarball")
    p.add_argument("file")
    p.add_argument("--identity", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--output", "-o")
    p.set_defaults(func=cmd_sign)

    p = subparsers.add_parser("verify", help="Verify a package signature")
    p.add_argument("file")
    p.add_argument("--sig", required=True)
    p.add_argument("--key", required=True)
    p.set_defaults(func=cmd_verify)
