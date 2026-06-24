"""Kubernetes Deployments – generate manifests, apply via kubectl, track status."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import SessionLocal, get_db
from ..deps import ensure_write_access, get_current_user, get_repo, require_user, ensure_read_access
from ..kafka_client import emit_event
from ..logging_config import StructLogger as _SL

logger = _SL(__name__)

router = APIRouter(prefix="/repos", tags=["kubernetes"])

_KUBECTL = shutil.which("kubectl")  # None if not installed


def _build_manifest(deploy: models.K8sDeployment, env: Optional[dict] = None) -> str:
    """Generate a minimal Kubernetes Deployment + Service manifest."""
    env_block = ""
    if env:
        env_block = "\n".join(
            f'            - name: {k}\n              value: "{v}"'
            for k, v in env.items()
        )
        env_block = "          env:\n" + env_block + "\n"

    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: stud-app-{deploy.repo_id}
  namespace: {deploy.namespace}
  labels:
    app: stud-app-{deploy.repo_id}
    managed-by: stud
spec:
  replicas: {deploy.replicas}
  selector:
    matchLabels:
      app: stud-app-{deploy.repo_id}
  template:
    metadata:
      labels:
        app: stud-app-{deploy.repo_id}
    spec:
      containers:
        - name: app
          image: {deploy.image}:{deploy.tag}
          imagePullPolicy: Always
{env_block}          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
---
apiVersion: v1
kind: Service
metadata:
  name: stud-app-{deploy.repo_id}
  namespace: {deploy.namespace}
spec:
  selector:
    app: stud-app-{deploy.repo_id}
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
"""


def _apply_manifest(deploy_id: int, manifest_yaml: str, env: Optional[dict]) -> None:
    """Background thread: write manifest to tmp file and kubectl apply."""
    db = SessionLocal()
    try:
        deploy = db.query(models.K8sDeployment).filter(models.K8sDeployment.id == deploy_id).first()
        if deploy is None:
            return

        deploy.status = "running"
        deploy.updated_at = time.time()
        db.commit()

        if _KUBECTL is None:
            # kubectl not available – store manifest, mark done (dry-run mode)
            deploy.log = "kubectl not found; manifest stored only (dry-run)\n"
            deploy.status = "succeeded"
            deploy.updated_at = time.time()
            db.commit()
            emit_event("k8s.deploy.dryrun", {"deploy_id": deploy_id})
            return

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(manifest_yaml)
            tmp_path = tmp.name

        result = subprocess.run(
            [_KUBECTL, "apply", "-f", tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        log = result.stdout + result.stderr
        deploy.log = log[:65000]
        deploy.status = "succeeded" if result.returncode == 0 else "failed"
        deploy.updated_at = time.time()
        db.commit()

        emit_event("k8s.deploy.done", {
            "deploy_id": deploy_id,
            "status": deploy.status,
        })
    except Exception as exc:
        logger.error("k8s.deploy.error", deploy_id=deploy_id, reason=str(exc))
        try:
            deploy = db.query(models.K8sDeployment).filter(models.K8sDeployment.id == deploy_id).first()
            if deploy:
                deploy.status = "failed"
                deploy.log = str(exc)[:65000]
                deploy.updated_at = time.time()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _deploy_out(d: models.K8sDeployment) -> schemas.K8sDeployOut:
    return schemas.K8sDeployOut(
        id=d.id,
        namespace=d.namespace,
        image=d.image,
        tag=d.tag,
        replicas=d.replicas,
        status=d.status,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


@router.post("/{owner}/{repo}/deployments", response_model=schemas.K8sDeployOut, status_code=202)
def create_deployment(
    owner: str,
    repo: str,
    body: schemas.K8sDeployRequest,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)

    deploy = models.K8sDeployment(
        repo_id=repo_row.id,
        triggered_by_id=user.id,
        namespace=body.namespace,
        image=body.image,
        tag=body.tag,
        replicas=body.replicas,
        status="pending",
    )
    db.add(deploy)
    db.flush()

    # build or use override manifest
    if body.manifest_override:
        manifest_yaml = body.manifest_override
    else:
        manifest_yaml = _build_manifest(deploy, body.env)

    deploy.manifest = manifest_yaml[:65000]
    db.commit()
    db.refresh(deploy)

    t = threading.Thread(
        target=_apply_manifest,
        args=(deploy.id, manifest_yaml, body.env),
        daemon=True,
    )
    t.start()

    emit_event("k8s.deploy.triggered", {
        "repo": f"{owner}/{repo}",
        "deploy_id": deploy.id,
        "image": f"{body.image}:{body.tag}",
        "triggered_by": user.username,
    })
    return _deploy_out(deploy)


@router.get("/{owner}/{repo}/deployments", response_model=List[schemas.K8sDeployOut])
def list_deployments(
    owner: str,
    repo: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    deploys = (
        db.query(models.K8sDeployment)
        .filter(models.K8sDeployment.repo_id == repo_row.id)
        .order_by(models.K8sDeployment.created_at.desc())
        .all()
    )
    return [_deploy_out(d) for d in deploys]


@router.get("/{owner}/{repo}/deployments/{deploy_id}", response_model=schemas.K8sDeployOut)
def get_deployment(
    owner: str,
    repo: str,
    deploy_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    d = (
        db.query(models.K8sDeployment)
        .filter(
            models.K8sDeployment.id == deploy_id,
            models.K8sDeployment.repo_id == repo_row.id,
        )
        .first()
    )
    if d is None:
        raise HTTPException(status_code=404, detail="deployment not found")
    return _deploy_out(d)


@router.get("/{owner}/{repo}/deployments/{deploy_id}/logs")
def get_deployment_logs(
    owner: str,
    repo: str,
    deploy_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    d = (
        db.query(models.K8sDeployment)
        .filter(
            models.K8sDeployment.id == deploy_id,
            models.K8sDeployment.repo_id == repo_row.id,
        )
        .first()
    )
    if d is None:
        raise HTTPException(status_code=404, detail="deployment not found")
    return {"log": d.log}


@router.get("/{owner}/{repo}/deployments/{deploy_id}/manifest")
def get_deployment_manifest(
    owner: str,
    repo: str,
    deploy_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    d = (
        db.query(models.K8sDeployment)
        .filter(
            models.K8sDeployment.id == deploy_id,
            models.K8sDeployment.repo_id == repo_row.id,
        )
        .first()
    )
    if d is None:
        raise HTTPException(status_code=404, detail="deployment not found")
    return {"manifest": d.manifest}


@router.delete("/{owner}/{repo}/deployments/{deploy_id}")
def rollback_deployment(
    owner: str,
    repo: str,
    deploy_id: int,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Trigger kubectl rollout undo for the deployment's namespace/resource."""
    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)
    d = (
        db.query(models.K8sDeployment)
        .filter(
            models.K8sDeployment.id == deploy_id,
            models.K8sDeployment.repo_id == repo_row.id,
        )
        .first()
    )
    if d is None:
        raise HTTPException(status_code=404, detail="deployment not found")

    if _KUBECTL:
        res = subprocess.run(
            [
                _KUBECTL, "rollout", "undo",
                f"deployment/stud-app-{repo_row.id}",
                "-n", d.namespace,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        log_append = "\n[rollback]\n" + res.stdout + res.stderr
        d.log = (d.log or "")[:64900] + log_append[:100]

    d.status = "pending"
    d.updated_at = time.time()
    db.commit()
    return {"rolled_back": True, "deploy_id": deploy_id}
