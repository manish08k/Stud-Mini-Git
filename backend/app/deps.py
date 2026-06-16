from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .security import hash_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    if creds is None:
        return None
    token_hash = hash_token(creds.credentials)
    token_row = db.query(models.Token).filter(models.Token.token_hash == token_hash).first()
    if token_row is None:
        return None
    return token_row.user


def require_user(user: Optional[models.User] = Depends(get_current_user)) -> models.User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing token")
    return user


def get_repo(owner: str, repo: str, db: Session) -> models.Repository:
    owner_row = db.query(models.User).filter(models.User.username == owner).first()
    if owner_row is None:
        raise HTTPException(status_code=404, detail="repository not found")
    repo_row = (
        db.query(models.Repository)
        .filter(models.Repository.owner_id == owner_row.id, models.Repository.name == repo)
        .first()
    )
    if repo_row is None:
        raise HTTPException(status_code=404, detail="repository not found")
    return repo_row


def _collab_role(db: Session, repo: models.Repository, user: Optional[models.User]) -> Optional[str]:
    if user is None:
        return None
    if user.id == repo.owner_id:
        return "admin"
    row = (
        db.query(models.Collaborator)
        .filter(models.Collaborator.repo_id == repo.id, models.Collaborator.user_id == user.id)
        .first()
    )
    return row.role if row else None


def ensure_read_access(db: Session, repo: models.Repository, user: Optional[models.User]) -> None:
    if not repo.is_private:
        return
    role = _collab_role(db, repo, user)
    if role is None:
        # hide existence of private repos from unauthorized users
        raise HTTPException(status_code=404, detail="repository not found")


def ensure_write_access(db: Session, repo: models.Repository, user: Optional[models.User]) -> None:
    role = _collab_role(db, repo, user)
    if role not in ("write", "admin"):
        raise HTTPException(status_code=403, detail="write access required")


def ensure_admin_access(db: Session, repo: models.Repository, user: Optional[models.User]) -> None:
    role = _collab_role(db, repo, user)
    if role != "admin":
        raise HTTPException(status_code=403, detail="admin access required")
