from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import ensure_read_access, ensure_write_access, get_current_user, get_repo, require_user
from ..repo_storage import RepoStorage

router = APIRouter(prefix="/repos", tags=["git"])


@router.get("/{owner}/{repo}/refs")
def get_refs(
    owner: str,
    repo: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    storage = RepoStorage(owner, repo)
    return storage.list_refs()


@router.get("/{owner}/{repo}/objects/{oid}")
def get_object(
    owner: str,
    repo: str,
    oid: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    storage = RepoStorage(owner, repo)
    if not storage.has_object(oid):
        raise HTTPException(status_code=404, detail="object not found")
    obj_type, data = storage.read_object(oid)
    return {"type": obj_type, "data": data.hex()}


@router.post("/{owner}/{repo}/objects/{oid}")
def post_object(
    owner: str,
    repo: str,
    oid: str,
    body: schemas.ObjectPayload,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)
    storage = RepoStorage(owner, repo)

    try:
        data = bytes.fromhex(body.data)
    except ValueError:
        raise HTTPException(status_code=400, detail="data must be hex-encoded")

    written_oid = storage.write_object(data, body.type)
    if written_oid != oid:
        raise HTTPException(status_code=400, detail="object id does not match content hash")
    return {"oid": written_oid}


@router.post("/{owner}/{repo}/refs/{category}/{name:path}")
def post_ref(
    owner: str,
    repo: str,
    category: str,
    name: str,
    body: schemas.RefUpdate,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if category not in ("heads", "tags"):
        raise HTTPException(status_code=400, detail="category must be heads or tags")

    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)
    storage = RepoStorage(owner, repo)

    if not storage.has_object(body.oid):
        raise HTTPException(status_code=400, detail="unknown object id, push the object first")

    storage.update_ref(category, name, body.oid)
    return {"category": category, "name": name, "oid": body.oid}
