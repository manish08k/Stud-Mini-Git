"""Container Registry – push/pull/list OCI images per repository."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import DATA_DIR
from ..database import get_db
from ..deps import ensure_read_access, ensure_write_access, get_current_user, get_repo, require_user
from ..kafka_client import emit_event

router = APIRouter(prefix="/repos", tags=["registry"])

REGISTRY_DIR = DATA_DIR / "registry"
REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def _blob_path(digest: str) -> Path:
    """Content-addressed blob storage under DATA_DIR/registry/blobs/<alg>/<hex>"""
    if ":" in digest:
        alg, hex_val = digest.split(":", 1)
    else:
        alg, hex_val = "sha256", digest
    p = REGISTRY_DIR / "blobs" / alg / hex_val[:2] / hex_val
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _image_out(img: models.ContainerImage) -> schemas.ContainerImageOut:
    return schemas.ContainerImageOut(
        id=img.id,
        name=img.name,
        tag=img.tag,
        digest=img.digest,
        size_bytes=img.size_bytes,
        pushed_by=img.pushed_by.username,
        created_at=img.created_at,
    )


# ── Manifest / metadata push ──────────────────────────────────────────────────

@router.post("/{owner}/{repo}/packages/container", response_model=schemas.ContainerImageOut, status_code=201)
def push_image_manifest(
    owner: str,
    repo: str,
    body: schemas.ContainerImagePush,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)

    # upsert: same name+tag replaces old entry
    existing = (
        db.query(models.ContainerImage)
        .filter(
            models.ContainerImage.repo_id == repo_row.id,
            models.ContainerImage.name == body.name,
            models.ContainerImage.tag == body.tag,
        )
        .first()
    )
    if existing:
        existing.digest = body.digest
        existing.size_bytes = body.size_bytes
        existing.pushed_by_id = user.id
        for layer in existing.layers:
            db.delete(layer)
        db.flush()
        img = existing
    else:
        img = models.ContainerImage(
            repo_id=repo_row.id,
            name=body.name,
            tag=body.tag,
            digest=body.digest,
            size_bytes=body.size_bytes,
            pushed_by_id=user.id,
        )
        db.add(img)
        db.flush()

    for layer in body.layers:
        db.add(models.ImageLayer(
            image_id=img.id,
            digest=layer.digest,
            size_bytes=layer.size_bytes,
            media_type=layer.media_type,
        ))

    db.commit()
    db.refresh(img)
    emit_event("registry.push", {
        "repo": f"{owner}/{repo}", "image": body.name,
        "tag": body.tag, "pusher": user.username,
    })
    return _image_out(img)


@router.get("/{owner}/{repo}/packages/container", response_model=List[schemas.ContainerImageOut])
def list_images(
    owner: str,
    repo: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    imgs = (
        db.query(models.ContainerImage)
        .filter(models.ContainerImage.repo_id == repo_row.id)
        .order_by(models.ContainerImage.created_at.desc())
        .all()
    )
    return [_image_out(i) for i in imgs]


@router.get("/{owner}/{repo}/packages/container/{name}/{tag}", response_model=schemas.ContainerImageOut)
def get_image(
    owner: str,
    repo: str,
    name: str,
    tag: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    img = (
        db.query(models.ContainerImage)
        .filter(
            models.ContainerImage.repo_id == repo_row.id,
            models.ContainerImage.name == name,
            models.ContainerImage.tag == tag,
        )
        .first()
    )
    if img is None:
        raise HTTPException(status_code=404, detail="image not found")
    return _image_out(img)


@router.delete("/{owner}/{repo}/packages/container/{name}/{tag}")
def delete_image(
    owner: str,
    repo: str,
    name: str,
    tag: str,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)
    img = (
        db.query(models.ContainerImage)
        .filter(
            models.ContainerImage.repo_id == repo_row.id,
            models.ContainerImage.name == name,
            models.ContainerImage.tag == tag,
        )
        .first()
    )
    if img is None:
        raise HTTPException(status_code=404, detail="image not found")
    db.delete(img)
    db.commit()
    return {"deleted": True}


# ── Blob upload / download ────────────────────────────────────────────────────

@router.post("/{owner}/{repo}/packages/container/blobs/upload")
async def upload_blob(
    owner: str,
    repo: str,
    file: UploadFile = File(...),
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)

    data = await file.read()
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    blob_path = _blob_path(digest)
    if not blob_path.exists():
        blob_path.write_bytes(data)
    return {"digest": digest, "size": len(data)}


@router.get("/{owner}/{repo}/packages/container/blobs/{digest:path}")
def download_blob(
    owner: str,
    repo: str,
    digest: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    blob_path = _blob_path(digest)
    if not blob_path.exists():
        raise HTTPException(status_code=404, detail="blob not found")
    return FileResponse(str(blob_path), media_type="application/octet-stream")
