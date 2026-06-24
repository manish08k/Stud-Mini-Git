"""Self-Hosted Runners – register, heartbeat, list, deregister."""
from __future__ import annotations

import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_user, get_current_user
from ..security import generate_token, hash_token

router = APIRouter(prefix="/runners", tags=["runners"])


def _runner_out(r: models.Runner) -> schemas.RunnerOut:
    return schemas.RunnerOut(
        id=r.id,
        name=r.name,
        labels=r.labels,
        status=r.status,
        os=r.os,
        arch=r.arch,
        last_seen_at=r.last_seen_at,
        created_at=r.created_at,
    )


@router.post("", response_model=schemas.RunnerOut, status_code=201)
def register_runner(
    body: schemas.RunnerRegister,
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_id: Optional[int] = None
    if repo_owner and repo_name:
        owner_row = db.query(models.User).filter(models.User.username == repo_owner).first()
        if owner_row:
            repo = (
                db.query(models.Repository)
                .filter(
                    models.Repository.owner_id == owner_row.id,
                    models.Repository.name == repo_name,
                )
                .first()
            )
            if repo:
                repo_id = repo.id

    raw_token = generate_token()
    runner = models.Runner(
        owner_id=user.id,
        repo_id=repo_id,
        name=body.name,
        token_hash=hash_token(raw_token),
        labels=body.labels,
        os=body.os,
        arch=body.arch,
        status="offline",
    )
    db.add(runner)
    db.commit()
    db.refresh(runner)
    out = _runner_out(runner)
    # attach token only on registration (one-time)
    return {**out.model_dump(), "registration_token": raw_token}


@router.get("", response_model=List[schemas.RunnerOut])
def list_runners(
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    runners = db.query(models.Runner).filter(models.Runner.owner_id == user.id).all()
    return [_runner_out(r) for r in runners]


@router.get("/{runner_id}", response_model=schemas.RunnerOut)
def get_runner(
    runner_id: int,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    r = db.query(models.Runner).filter(
        models.Runner.id == runner_id,
        models.Runner.owner_id == user.id,
    ).first()
    if r is None:
        raise HTTPException(status_code=404, detail="runner not found")
    return _runner_out(r)


@router.post("/{runner_id}/heartbeat", response_model=schemas.RunnerOut)
def runner_heartbeat(
    runner_id: int,
    body: schemas.RunnerHeartbeat,
    token: str,
    db: Session = Depends(get_db),
):
    """Runners call this endpoint periodically to report liveness.
    Authentication uses the registration token (passed as ?token=…)."""
    r = db.query(models.Runner).filter(models.Runner.id == runner_id).first()
    if r is None or hash_token(token) != r.token_hash:
        raise HTTPException(status_code=401, detail="invalid runner token")
    if body.status not in ("online", "busy", "offline"):
        raise HTTPException(status_code=400, detail="status must be online, busy, or offline")
    r.status = body.status
    r.last_seen_at = time.time()
    db.commit()
    db.refresh(r)
    return _runner_out(r)


@router.delete("/{runner_id}")
def deregister_runner(
    runner_id: int,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    r = db.query(models.Runner).filter(
        models.Runner.id == runner_id,
        models.Runner.owner_id == user.id,
    ).first()
    if r is None:
        raise HTTPException(status_code=404, detail="runner not found")
    db.delete(r)
    db.commit()
    return {"deleted": True}
