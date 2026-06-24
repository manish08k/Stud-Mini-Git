from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_user
from ..security import (
    clear_failed_logins,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_token,
    hash_password,
    hash_token,
    is_locked_out,
    record_failed_login,
    verify_password,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _make_token_response(user: models.User, db: Session) -> schemas.TokenResponse:
    access = create_access_token(user.id, user.username)
    refresh_raw = create_refresh_token(user.id)
    db.add(models.RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_raw),
        expires_at=time.time() + REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    ))
    db.commit()
    return schemas.TokenResponse(
        username=user.username,
        access_token=access,
        refresh_token=refresh_raw,
    )


@router.post("/register", response_model=schemas.TokenResponse, status_code=201)
def register(body: schemas.RegisterRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == body.username).first():
        raise HTTPException(status_code=400, detail="username already taken")
    user = models.User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _make_token_response(user, db)


@router.post("/login", response_model=schemas.TokenResponse)
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    if is_locked_out(body.username):
        raise HTTPException(status_code=429, detail="account temporarily locked — too many failed attempts")

    user = db.query(models.User).filter(models.User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        record_failed_login(body.username)
        raise HTTPException(status_code=401, detail="invalid username or password")

    clear_failed_logins(body.username)
    return _make_token_response(user, db)


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh(body: schemas.RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_refresh_token(body.refresh_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="invalid refresh token")

    token_hash = hash_token(body.refresh_token)
    row = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.token_hash == token_hash,
            models.RefreshToken.revoked == False,  # noqa: E712
        )
        .first()
    )
    if row is None or row.expires_at < time.time():
        raise HTTPException(status_code=401, detail="refresh token expired or revoked")

    # rotate: revoke old, issue new
    row.revoked = True
    db.commit()

    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")

    return _make_token_response(user, db)


@router.post("/logout")
def logout(body: schemas.RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(body.refresh_token)
    row = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == token_hash).first()
    if row:
        row.revoked = True
        db.commit()
    return {"ok": True}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(require_user)):
    return schemas.UserOut(id=user.id, username=user.username)
