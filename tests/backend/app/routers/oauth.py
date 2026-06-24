"""OAuth 2.0 authorization server – apps, authorize, token exchange."""
from __future__ import annotations

import secrets
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_user, get_current_user
from ..security import generate_token, hash_token

router = APIRouter(prefix="/oauth", tags=["oauth"])

_CODE_TTL = 600  # 10 minutes


def _hash(val: str) -> str:
    return hash_token(val)


# ── App management ─────────────────────────────────────────────────────────────

@router.post("/apps", response_model=schemas.OAuthAppWithSecret, status_code=201)
def create_oauth_app(
    body: schemas.OAuthAppCreate,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    client_id = "stud_" + secrets.token_urlsafe(16)
    client_secret = secrets.token_urlsafe(32)
    app = models.OAuthApp(
        owner_id=user.id,
        name=body.name,
        client_id=client_id,
        client_secret_hash=_hash(client_secret),
        redirect_uris=body.redirect_uris,
        scopes=body.scopes,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return schemas.OAuthAppWithSecret(
        id=app.id,
        name=app.name,
        client_id=app.client_id,
        redirect_uris=app.redirect_uris,
        scopes=app.scopes,
        created_at=app.created_at,
        client_secret=client_secret,
    )


@router.get("/apps", response_model=List[schemas.OAuthAppOut])
def list_oauth_apps(
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    apps = db.query(models.OAuthApp).filter(models.OAuthApp.owner_id == user.id).all()
    return [
        schemas.OAuthAppOut(
            id=a.id, name=a.name, client_id=a.client_id,
            redirect_uris=a.redirect_uris, scopes=a.scopes, created_at=a.created_at,
        )
        for a in apps
    ]


@router.delete("/apps/{client_id}")
def delete_oauth_app(
    client_id: str,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    app = db.query(models.OAuthApp).filter(models.OAuthApp.client_id == client_id).first()
    if app is None or app.owner_id != user.id:
        raise HTTPException(status_code=404, detail="app not found")
    db.delete(app)
    db.commit()
    return {"deleted": True}


# ── Authorization code flow ────────────────────────────────────────────────────

@router.post("/authorize")
def authorize(
    body: schemas.OAuthAuthorizeRequest,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Issue an authorization code. In a real flow the user would confirm
    a consent screen; here the authenticated user implicitly grants access."""
    app = db.query(models.OAuthApp).filter(models.OAuthApp.client_id == body.client_id).first()
    if app is None:
        raise HTTPException(status_code=404, detail="unknown client_id")

    allowed = [u.strip() for u in app.redirect_uris.split(",") if u.strip()]
    if allowed and body.redirect_uri not in allowed:
        raise HTTPException(status_code=400, detail="redirect_uri not registered")

    code_raw = secrets.token_urlsafe(32)
    db.add(models.OAuthCode(
        app_id=app.id,
        user_id=user.id,
        code=code_raw,
        scope=body.scope,
        redirect_uri=body.redirect_uri,
        expires_at=time.time() + _CODE_TTL,
    ))
    db.commit()

    redirect = f"{body.redirect_uri}?code={code_raw}"
    if body.state:
        redirect += f"&state={body.state}"
    return {"redirect_uri": redirect, "code": code_raw}


@router.post("/token", response_model=schemas.OAuthTokenResponse)
def token_exchange(
    body: schemas.OAuthTokenRequest,
    db: Session = Depends(get_db),
):
    app = db.query(models.OAuthApp).filter(models.OAuthApp.client_id == body.client_id).first()
    if app is None or _hash(body.client_secret) != app.client_secret_hash:
        raise HTTPException(status_code=401, detail="invalid client credentials")

    if body.grant_type == "authorization_code":
        if not body.code:
            raise HTTPException(status_code=400, detail="code is required")
        code_row = (
            db.query(models.OAuthCode)
            .filter(models.OAuthCode.code == body.code, models.OAuthCode.app_id == app.id)
            .first()
        )
        if code_row is None or code_row.used or code_row.expires_at < time.time():
            raise HTTPException(status_code=400, detail="invalid or expired code")
        code_row.used = True

        access_raw = generate_token()
        refresh_raw = generate_token()
        db.add(models.OAuthToken(
            app_id=app.id,
            user_id=code_row.user_id,
            access_token_hash=_hash(access_raw),
            refresh_token_hash=_hash(refresh_raw),
            scope=code_row.scope,
            expires_at=time.time() + 3600,
        ))
        db.commit()
        return schemas.OAuthTokenResponse(
            access_token=access_raw,
            scope=code_row.scope,
            refresh_token=refresh_raw,
        )

    elif body.grant_type == "refresh_token":
        if not body.refresh_token:
            raise HTTPException(status_code=400, detail="refresh_token is required")
        token_row = (
            db.query(models.OAuthToken)
            .filter(
                models.OAuthToken.refresh_token_hash == _hash(body.refresh_token),
                models.OAuthToken.app_id == app.id,
            )
            .first()
        )
        if token_row is None:
            raise HTTPException(status_code=400, detail="invalid refresh_token")

        new_access_raw = generate_token()
        new_refresh_raw = generate_token()
        token_row.access_token_hash = _hash(new_access_raw)
        token_row.refresh_token_hash = _hash(new_refresh_raw)
        token_row.expires_at = time.time() + 3600
        db.commit()
        return schemas.OAuthTokenResponse(
            access_token=new_access_raw,
            scope=token_row.scope,
            refresh_token=new_refresh_raw,
        )

    else:
        raise HTTPException(status_code=400, detail="unsupported grant_type")


@router.get("/token/info")
def token_info(
    user: Optional[models.User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return info about the currently authenticated user (works for both
    stud tokens and OAuth access tokens that were registered as stud tokens)."""
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return {"user_id": user.id, "username": user.username}
