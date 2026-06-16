from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_user
from ..security import generate_token, hash_password, hash_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenResponse)
def register(body: schemas.RegisterRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == body.username).first():
        raise HTTPException(status_code=400, detail="username already taken")

    user = models.User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    raw_token = generate_token()
    db.add(models.Token(user_id=user.id, token_hash=hash_token(raw_token), name="default"))
    db.commit()

    return schemas.TokenResponse(username=user.username, token=raw_token)


@router.post("/login", response_model=schemas.TokenResponse)
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid username or password")

    raw_token = generate_token()
    db.add(models.Token(user_id=user.id, token_hash=hash_token(raw_token), name="login"))
    db.commit()

    return schemas.TokenResponse(username=user.username, token=raw_token)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(require_user)):
    return schemas.UserOut(id=user.id, username=user.username)
