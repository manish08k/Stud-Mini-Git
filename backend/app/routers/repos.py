from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import (
    ensure_admin_access,
    ensure_read_access,
    get_current_user,
    get_repo,
    require_user,
)
from ..repo_storage import RepoStorage

router = APIRouter(prefix="/repos", tags=["repos"])


def _repo_out(repo: models.Repository) -> schemas.RepoOut:
    return schemas.RepoOut(
        id=repo.id,
        owner=repo.owner.username,
        name=repo.name,
        private=repo.is_private,
        default_branch=repo.default_branch,
    )


@router.post("", response_model=schemas.RepoOut)
def create_repo(
    body: schemas.RepoCreate,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(models.Repository)
        .filter(models.Repository.owner_id == user.id, models.Repository.name == body.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="repository already exists")

    repo = models.Repository(
        owner_id=user.id,
        name=body.name,
        is_private=body.private,
        default_branch=body.default_branch,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    RepoStorage(user.username, repo.name)  # creates objects/ + refs/ + HEAD on disk
    return _repo_out(repo)


@router.get("", response_model=List[schemas.RepoOut])
def list_repos(
    owner: Optional[str] = None,
    user: Optional[models.User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.Repository)
    if owner:
        query = query.join(models.User, models.Repository.owner_id == models.User.id).filter(
            models.User.username == owner
        )

    visible = []
    for repo in query.all():
        if not repo.is_private:
            visible.append(repo)
        elif user is not None and (
            repo.owner_id == user.id
            or any(c.user_id == user.id for c in repo.collaborators)
        ):
            visible.append(repo)
    return [_repo_out(r) for r in visible]


@router.get("/{owner}/{repo}", response_model=schemas.RepoOut)
def get_repo_info(
    owner: str,
    repo: str,
    user: Optional[models.User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    return _repo_out(repo_row)


@router.patch("/{owner}/{repo}", response_model=schemas.RepoOut)
def update_repo(
    owner: str,
    repo: str,
    body: schemas.RepoUpdate,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_admin_access(db, repo_row, user)
    if body.private is not None:
        repo_row.is_private = body.private
    if body.default_branch is not None:
        repo_row.default_branch = body.default_branch
    db.commit()
    db.refresh(repo_row)
    return _repo_out(repo_row)


@router.delete("/{owner}/{repo}")
def delete_repo(
    owner: str,
    repo: str,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_admin_access(db, repo_row, user)
    db.delete(repo_row)
    db.commit()
    RepoStorage.delete(owner, repo)
    return {"deleted": True}


@router.get("/{owner}/{repo}/collaborators", response_model=List[schemas.CollaboratorOut])
def list_collaborators(
    owner: str,
    repo: str,
    user: Optional[models.User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    return [
        schemas.CollaboratorOut(username=c.user.username, role=c.role)
        for c in repo_row.collaborators
    ]


@router.post("/{owner}/{repo}/collaborators", response_model=schemas.CollaboratorOut)
def add_collaborator(
    owner: str,
    repo: str,
    body: schemas.CollaboratorAdd,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_admin_access(db, repo_row, user)

    target = db.query(models.User).filter(models.User.username == body.username).first()
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")
    if body.role not in ("read", "write", "admin"):
        raise HTTPException(status_code=400, detail="role must be read, write or admin")

    existing = (
        db.query(models.Collaborator)
        .filter(models.Collaborator.repo_id == repo_row.id, models.Collaborator.user_id == target.id)
        .first()
    )
    if existing:
        existing.role = body.role
    else:
        db.add(models.Collaborator(repo_id=repo_row.id, user_id=target.id, role=body.role))
    db.commit()
    return schemas.CollaboratorOut(username=target.username, role=body.role)


@router.delete("/{owner}/{repo}/collaborators/{username}")
def remove_collaborator(
    owner: str,
    repo: str,
    username: str,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_admin_access(db, repo_row, user)

    target = db.query(models.User).filter(models.User.username == username).first()
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")

    row = (
        db.query(models.Collaborator)
        .filter(models.Collaborator.repo_id == repo_row.id, models.Collaborator.user_id == target.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="not a collaborator")
    db.delete(row)
    db.commit()
    return {"removed": True}
