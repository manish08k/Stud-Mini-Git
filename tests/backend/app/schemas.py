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


# ── Pull Requests ─────────────────────────────────────────────────────────────

class PRCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    description: str = ""
    base_branch: str = "main"
    head_branch: str


class PRUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # open | merged | closed


class PRReviewCreate(BaseModel):
    verdict: str = "comment"  # approved | changes_requested | comment
    body: str = ""


class PRCommentCreate(BaseModel):
    body: str = Field(min_length=1)
    file_path: Optional[str] = None
    line_number: Optional[int] = None


class PRCommentOut(BaseModel):
    id: int
    author: str
    body: str
    file_path: Optional[str]
    line_number: Optional[int]
    created_at: float


class PRReviewOut(BaseModel):
    id: int
    reviewer: str
    verdict: str
    body: str
    created_at: float


class PROut(BaseModel):
    id: int
    number: int
    title: str
    description: str
    author: str
    base_branch: str
    head_branch: str
    status: str
    created_at: float
    updated_at: float
    reviews: List[PRReviewOut] = []
    comments: List[PRCommentOut] = []


# ── OAuth ─────────────────────────────────────────────────────────────────────

class OAuthAppCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    redirect_uris: str = ""
    scopes: str = "repo"


class OAuthAppOut(BaseModel):
    id: int
    name: str
    client_id: str
    redirect_uris: str
    scopes: str
    created_at: float


class OAuthAppWithSecret(OAuthAppOut):
    client_secret: str


class OAuthAuthorizeRequest(BaseModel):
    client_id: str
    redirect_uri: str
    scope: str = "repo"
    state: Optional[str] = None


class OAuthTokenRequest(BaseModel):
    grant_type: str  # authorization_code | refresh_token
    code: Optional[str] = None
    refresh_token: Optional[str] = None
    client_id: str
    client_secret: str
    redirect_uri: Optional[str] = None


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    scope: str
    refresh_token: Optional[str] = None


# ── Container Registry ────────────────────────────────────────────────────────

class ImageLayerIn(BaseModel):
    digest: str
    size_bytes: int = 0
    media_type: str = "application/vnd.oci.image.layer.v1.tar+gzip"


class ContainerImagePush(BaseModel):
    name: str
    tag: str = "latest"
    digest: str
    size_bytes: int = 0
    layers: List[ImageLayerIn] = []


class ContainerImageOut(BaseModel):
    id: int
    name: str
    tag: str
    digest: str
    size_bytes: int
    pushed_by: str
    created_at: float


# ── Self-Hosted Runners ───────────────────────────────────────────────────────

class RunnerRegister(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    labels: str = "self-hosted"
    os: str = "linux"
    arch: str = "x64"


class RunnerOut(BaseModel):
    id: int
    name: str
    labels: str
    status: str
    os: str
    arch: str
    last_seen_at: Optional[float]
    created_at: float


class RunnerToken(BaseModel):
    token: str


class RunnerHeartbeat(BaseModel):
    status: str = "online"  # online | busy | offline


# ── Dependency Scanner ────────────────────────────────────────────────────────

class ScanTrigger(BaseModel):
    commit_oid: Optional[str] = None
    packages: Optional[Dict[str, str]] = None  # {"package": "version"}


class FindingOut(BaseModel):
    package: str
    version: str
    cve_id: Optional[str]
    severity: str
    description: str
    fix_version: Optional[str]


class ScanOut(BaseModel):
    id: int
    repo: str
    status: str
    commit_oid: Optional[str]
    findings: List[FindingOut] = []
    created_at: float
    finished_at: Optional[float]


# ── Signed Commits ────────────────────────────────────────────────────────────

class SignCommitRequest(BaseModel):
    commit_oid: str
    signature: str
    algorithm: str = "hmac-sha256"


class CommitSignatureOut(BaseModel):
    id: int
    commit_oid: str
    signer: str
    algorithm: str
    verified: bool
    created_at: float


# ── Kubernetes Deployments ─────────────────────────────────────────────────────

class K8sDeployRequest(BaseModel):
    namespace: str = "default"
    image: str
    tag: str = "latest"
    replicas: int = 1
    env: Optional[Dict[str, str]] = None
    manifest_override: Optional[str] = None  # raw YAML


class K8sDeployOut(BaseModel):
    id: int
    namespace: str
    image: str
    tag: str
    replicas: int
    status: str
    created_at: float
    updated_at: float
