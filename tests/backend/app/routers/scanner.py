"""Dependency Scanner – trigger scans, store and query findings via OSV."""
from __future__ import annotations

import json
import time
import threading
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import SessionLocal, get_db
from ..deps import ensure_read_access, ensure_write_access, get_current_user, get_repo, require_user
from ..kafka_client import emit_event
from ..logging_config import StructLogger as _SL

logger = _SL(__name__)

router = APIRouter(prefix="/repos", tags=["scanner"])


def _finding_out(f: models.DependencyFinding) -> schemas.FindingOut:
    return schemas.FindingOut(
        package=f.package,
        version=f.version,
        cve_id=f.cve_id,
        severity=f.severity,
        description=f.description,
        fix_version=f.fix_version,
    )


def _scan_out(scan: models.DependencyScan) -> schemas.ScanOut:
    return schemas.ScanOut(
        id=scan.id,
        repo=scan.repo.name,
        status=scan.status,
        commit_oid=scan.commit_oid,
        findings=[_finding_out(f) for f in scan.findings],
        created_at=scan.created_at,
        finished_at=scan.finished_at,
    )


def _severity_from_osv(vuln: dict) -> str:
    scores = vuln.get("severity", [])
    for s in scores:
        score_type = s.get("type", "")
        score_val = s.get("score", "")
        if "CVSS" in score_type.upper():
            try:
                v = float(score_val)
                if v >= 9.0:
                    return "critical"
                if v >= 7.0:
                    return "high"
                if v >= 4.0:
                    return "medium"
                return "low"
            except (ValueError, TypeError):
                pass
    # fall back to database_specific
    db_spec = vuln.get("database_specific", {})
    sev = str(db_spec.get("severity", "")).lower()
    if sev in ("critical", "high", "medium", "low"):
        return sev
    return "unknown"


def _fix_version_from_osv(vuln: dict, pkg_name: str) -> Optional[str]:
    for affected in vuln.get("affected", []):
        if affected.get("package", {}).get("name", "").lower() != pkg_name.lower():
            continue
        for rng in affected.get("ranges", []):
            for event in rng.get("events", []):
                fixed = event.get("fixed")
                if fixed:
                    return fixed
    return None


def _run_scan(scan_id: int, packages: dict) -> None:
    """Background thread: call OSV API for each package and persist findings."""
    import urllib.request
    import urllib.error

    db = SessionLocal()
    try:
        scan = db.query(models.DependencyScan).filter(models.DependencyScan.id == scan_id).first()
        if scan is None:
            return
        scan.status = "running"
        db.commit()

        findings: list = []
        for pkg, version in packages.items():
            payload = json.dumps({
                "version": version,
                "package": {"name": pkg, "ecosystem": "PyPI"},
            }).encode()
            req = urllib.request.Request(
                "https://api.osv.dev/v1/query",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
            except Exception as exc:
                logger.warning("scanner.osv_error", pkg=pkg, reason=str(exc))
                continue

            for vuln in data.get("vulns", []):
                finding = models.DependencyFinding(
                    scan_id=scan_id,
                    package=pkg,
                    version=version,
                    cve_id=next(
                        (a["value"] for a in vuln.get("aliases", []) if a.get("value", "").startswith("CVE")),
                        vuln.get("id"),
                    ),
                    severity=_severity_from_osv(vuln),
                    description=vuln.get("summary", "")[:2048],
                    fix_version=_fix_version_from_osv(vuln, pkg),
                )
                db.add(finding)
                findings.append(finding)

        summary = {
            "total": len(findings),
            "critical": sum(1 for f in findings if f.severity == "critical"),
            "high": sum(1 for f in findings if f.severity == "high"),
            "medium": sum(1 for f in findings if f.severity == "medium"),
            "low": sum(1 for f in findings if f.severity == "low"),
        }
        scan.status = "done"
        scan.summary = json.dumps(summary)
        scan.finished_at = time.time()
        db.commit()
        emit_event("scanner.done", {"scan_id": scan_id, "summary": summary})
    except Exception as exc:
        logger.error("scanner.run_error", scan_id=scan_id, reason=str(exc))
        try:
            scan = db.query(models.DependencyScan).filter(models.DependencyScan.id == scan_id).first()
            if scan:
                scan.status = "failed"
                scan.finished_at = time.time()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/{owner}/{repo}/scans", response_model=schemas.ScanOut, status_code=202)
def trigger_scan(
    owner: str,
    repo: str,
    body: schemas.ScanTrigger,
    background_tasks: BackgroundTasks,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)

    packages = body.packages or {}

    scan = models.DependencyScan(
        repo_id=repo_row.id,
        commit_oid=body.commit_oid,
        triggered_by_id=user.id,
        status="pending",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    if packages:
        t = threading.Thread(target=_run_scan, args=(scan.id, packages), daemon=True)
        t.start()
    else:
        scan.status = "done"
        scan.finished_at = time.time()
        db.commit()
        db.refresh(scan)

    return _scan_out(scan)


@router.get("/{owner}/{repo}/scans", response_model=List[schemas.ScanOut])
def list_scans(
    owner: str,
    repo: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    scans = (
        db.query(models.DependencyScan)
        .filter(models.DependencyScan.repo_id == repo_row.id)
        .order_by(models.DependencyScan.created_at.desc())
        .all()
    )
    return [_scan_out(s) for s in scans]


@router.get("/{owner}/{repo}/scans/{scan_id}", response_model=schemas.ScanOut)
def get_scan(
    owner: str,
    repo: str,
    scan_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    scan = (
        db.query(models.DependencyScan)
        .filter(
            models.DependencyScan.id == scan_id,
            models.DependencyScan.repo_id == repo_row.id,
        )
        .first()
    )
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")
    return _scan_out(scan)
