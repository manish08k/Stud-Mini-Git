"""Signed Commits – sign a commit OID with HMAC-SHA256, verify signatures."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import SECRET_KEY
from ..database import get_db
from ..deps import ensure_read_access, ensure_write_access, get_current_user, get_repo, require_user

router = APIRouter(prefix="/repos", tags=["signatures"])

_KEY = SECRET_KEY.encode("utf-8")


def _compute_sig(commit_oid: str, user_id: int) -> str:
    msg = f"{commit_oid}:{user_id}".encode()
    return hmac.new(_KEY, msg, hashlib.sha256).hexdigest()


def _verify_sig(commit_oid: str, user_id: int, signature: str) -> bool:
    expected = _compute_sig(commit_oid, user_id)
    return hmac.compare_digest(expected, signature)


def _sig_out(s: models.CommitSignature) -> schemas.CommitSignatureOut:
    return schemas.CommitSignatureOut(
        id=s.id,
        commit_oid=s.commit_oid,
        signer=s.signer.username,
        algorithm=s.algorithm,
        verified=s.verified,
        created_at=s.created_at,
    )


@router.post("/{owner}/{repo}/commits/{commit_oid}/sign", response_model=schemas.CommitSignatureOut, status_code=201)
def sign_commit(
    owner: str,
    repo: str,
    commit_oid: str,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Server-side signs a commit OID for the authenticated user using HMAC-SHA256.
    The resulting signature is stored and can be verified later."""
    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)

    # prevent duplicate
    existing = (
        db.query(models.CommitSignature)
        .filter(
            models.CommitSignature.repo_id == repo_row.id,
            models.CommitSignature.commit_oid == commit_oid,
            models.CommitSignature.signer_id == user.id,
        )
        .first()
    )
    if existing:
        return _sig_out(existing)

    sig_value = _compute_sig(commit_oid, user.id)
    sig = models.CommitSignature(
        repo_id=repo_row.id,
        commit_oid=commit_oid,
        signer_id=user.id,
        algorithm="hmac-sha256",
        signature=sig_value,
        verified=True,
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    return _sig_out(sig)


@router.post("/{owner}/{repo}/commits/{commit_oid}/verify", response_model=schemas.CommitSignatureOut)
def verify_commit(
    owner: str,
    repo: str,
    commit_oid: str,
    body: schemas.SignCommitRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify a client-supplied signature against the stored one."""
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)

    sig = (
        db.query(models.CommitSignature)
        .filter(
            models.CommitSignature.repo_id == repo_row.id,
            models.CommitSignature.commit_oid == commit_oid,
        )
        .first()
    )
    if sig is None:
        raise HTTPException(status_code=404, detail="no signature found for this commit")

    verified = hmac.compare_digest(sig.signature, body.signature)
    sig.verified = verified
    db.commit()
    if not verified:
        raise HTTPException(status_code=400, detail="signature verification failed")
    return _sig_out(sig)


@router.get("/{owner}/{repo}/commits/{commit_oid}/signatures", response_model=List[schemas.CommitSignatureOut])
def list_signatures(
    owner: str,
    repo: str,
    commit_oid: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    sigs = (
        db.query(models.CommitSignature)
        .filter(
            models.CommitSignature.repo_id == repo_row.id,
            models.CommitSignature.commit_oid == commit_oid,
        )
        .all()
    )
    return [_sig_out(s) for s in sigs]
