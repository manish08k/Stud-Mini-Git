from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=256)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    username: str
    token: str


class UserOut(BaseModel):
    id: int
    username: str


class RepoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    private: bool = False
    default_branch: str = "main"


class RepoUpdate(BaseModel):
    private: Optional[bool] = None
    default_branch: Optional[str] = None


class RepoOut(BaseModel):
    id: int
    owner: str
    name: str
    private: bool
    default_branch: str


class CollaboratorAdd(BaseModel):
    username: str
    role: str = "write"  # read | write | admin


class CollaboratorOut(BaseModel):
    username: str
    role: str


class RefUpdate(BaseModel):
    oid: str


class ObjectPayload(BaseModel):
    type: str
    data: str  # hex-encoded
