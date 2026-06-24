from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    username: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    username: str


class RepoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    private: bool = False
    default_branch: str = Field(default="main", pattern=r"^[a-zA-Z0-9_\-/\.]+$")


class RepoUpdate(BaseModel):
    private: Optional[bool] = None
    default_branch: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z0-9_\-/\.]+$")


class RepoOut(BaseModel):
    id: int
    owner: str
    name: str
    private: bool
    default_branch: str
    deleted: bool = False


class CollaboratorAdd(BaseModel):
    username: str
    role: str = "write"


class CollaboratorOut(BaseModel):
    username: str
    role: str


class RefUpdate(BaseModel):
    oid: str = Field(pattern=r"^[0-9a-f]{64}$")


class ObjectPayload(BaseModel):
    type: str = Field(pattern=r"^(blob|tree|commit|tag)$")
    data: str  # hex-encoded


class PaginatedRepos(BaseModel):
    items: List[RepoOut]
    total: int
    page: int
    page_size: int


class AuditLogOut(BaseModel):
    id: int
    actor: str
    action: str
    resource: str
    detail: Optional[str]
    created_at: float
