import time

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(Float, default=time.time)

    tokens = relationship("Token", back_populates="user", cascade="all, delete-orphan")
    repos = relationship("Repository", back_populates="owner", cascade="all, delete-orphan")


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(128), default="default")
    created_at = Column(Float, default=time.time)
    last_used_at = Column(Float, nullable=True)

    user = relationship("User", back_populates="tokens")


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_owner_repo_name"),)

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(128), nullable=False)
    is_private = Column(Boolean, default=False)
    default_branch = Column(String(128), default="main")
    created_at = Column(Float, default=time.time)

    owner = relationship("User", back_populates="repos")
    collaborators = relationship(
        "Collaborator", back_populates="repo", cascade="all, delete-orphan"
    )


class Collaborator(Base):
    __tablename__ = "collaborators"
    __table_args__ = (UniqueConstraint("repo_id", "user_id", name="uq_repo_user"),)

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(16), default="write")  # read | write | admin

    repo = relationship("Repository", back_populates="collaborators")
    user = relationship("User")


# ── Pull Requests ─────────────────────────────────────────────────────────────

class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (UniqueConstraint("repo_id", "number", name="uq_pr_repo_number"),)

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    number = Column(Integer, nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(String(8192), default="")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    base_branch = Column(String(128), default="main")
    head_branch = Column(String(128), nullable=False)
    status = Column(String(16), default="open")  # open | merged | closed
    merged_at = Column(Float, nullable=True)
    created_at = Column(Float, default=time.time)
    updated_at = Column(Float, default=time.time)

    repo = relationship("Repository")
    author = relationship("User", foreign_keys=[author_id])
    reviews = relationship("PRReview", back_populates="pr", cascade="all, delete-orphan")
    comments = relationship("PRComment", back_populates="pr", cascade="all, delete-orphan")


class PRReview(Base):
    __tablename__ = "pr_reviews"

    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    verdict = Column(String(16), default="comment")  # approved | changes_requested | comment
    body = Column(String(8192), default="")
    created_at = Column(Float, default=time.time)

    pr = relationship("PullRequest", back_populates="reviews")
    reviewer = relationship("User")


class PRComment(Base):
    __tablename__ = "pr_comments"

    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(String(8192), nullable=False)
    file_path = Column(String(512), nullable=True)
    line_number = Column(Integer, nullable=True)
    created_at = Column(Float, default=time.time)

    pr = relationship("PullRequest", back_populates="comments")
    author = relationship("User")


# ── OAuth Apps ────────────────────────────────────────────────────────────────

class OAuthApp(Base):
    __tablename__ = "oauth_apps"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(128), nullable=False)
    client_id = Column(String(64), unique=True, nullable=False)
    client_secret_hash = Column(String(128), nullable=False)
    redirect_uris = Column(String(2048), default="")  # comma-separated
    scopes = Column(String(512), default="repo")
    created_at = Column(Float, default=time.time)

    owner = relationship("User")
    tokens = relationship("OAuthToken", back_populates="app", cascade="all, delete-orphan")


class OAuthCode(Base):
    __tablename__ = "oauth_codes"

    id = Column(Integer, primary_key=True)
    app_id = Column(Integer, ForeignKey("oauth_apps.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    code = Column(String(128), unique=True, nullable=False)
    scope = Column(String(512), default="repo")
    redirect_uri = Column(String(512), nullable=False)
    expires_at = Column(Float, nullable=False)
    used = Column(Boolean, default=False)

    app = relationship("OAuthApp")
    user = relationship("User")


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True)
    app_id = Column(Integer, ForeignKey("oauth_apps.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    access_token_hash = Column(String(128), unique=True, nullable=False)
    refresh_token_hash = Column(String(128), unique=True, nullable=True)
    scope = Column(String(512), default="repo")
    expires_at = Column(Float, nullable=True)
    created_at = Column(Float, default=time.time)

    app = relationship("OAuthApp", back_populates="tokens")
    user = relationship("User")


# ── Container Registry ────────────────────────────────────────────────────────

class ContainerImage(Base):
    __tablename__ = "container_images"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    name = Column(String(256), nullable=False)
    tag = Column(String(128), default="latest")
    digest = Column(String(128), nullable=False)
    size_bytes = Column(Integer, default=0)
    pushed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(Float, default=time.time)

    repo = relationship("Repository")
    pushed_by = relationship("User")
    layers = relationship("ImageLayer", back_populates="image", cascade="all, delete-orphan")


class ImageLayer(Base):
    __tablename__ = "image_layers"

    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, ForeignKey("container_images.id"), nullable=False)
    digest = Column(String(128), nullable=False)
    size_bytes = Column(Integer, default=0)
    media_type = Column(String(256), default="application/vnd.oci.image.layer.v1.tar+gzip")

    image = relationship("ContainerImage", back_populates="layers")


# ── Self-Hosted Runners ───────────────────────────────────────────────────────

class Runner(Base):
    __tablename__ = "runners"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)  # None = org-level
    name = Column(String(128), nullable=False)
    token_hash = Column(String(128), unique=True, nullable=False)
    labels = Column(String(512), default="self-hosted")  # comma-separated
    status = Column(String(16), default="offline")  # online | offline | busy
    os = Column(String(32), default="linux")
    arch = Column(String(16), default="x64")
    last_seen_at = Column(Float, nullable=True)
    created_at = Column(Float, default=time.time)

    owner = relationship("User")
    repo = relationship("Repository")


# ── Dependency Scanner Results ────────────────────────────────────────────────

class DependencyScan(Base):
    __tablename__ = "dependency_scans"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    commit_oid = Column(String(128), nullable=True)
    triggered_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(16), default="pending")  # pending | running | done | failed
    summary = Column(String(4096), default="{}")  # JSON blob
    created_at = Column(Float, default=time.time)
    finished_at = Column(Float, nullable=True)

    repo = relationship("Repository")
    triggered_by = relationship("User")
    findings = relationship("DependencyFinding", back_populates="scan", cascade="all, delete-orphan")


class DependencyFinding(Base):
    __tablename__ = "dependency_findings"

    id = Column(Integer, primary_key=True)
    scan_id = Column(Integer, ForeignKey("dependency_scans.id"), nullable=False)
    package = Column(String(256), nullable=False)
    version = Column(String(64), nullable=False)
    cve_id = Column(String(64), nullable=True)
    severity = Column(String(16), default="unknown")  # critical | high | medium | low | unknown
    description = Column(String(2048), default="")
    fix_version = Column(String(64), nullable=True)

    scan = relationship("DependencyScan", back_populates="findings")


# ── Signed Commits ────────────────────────────────────────────────────────────

class CommitSignature(Base):
    __tablename__ = "commit_signatures"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    commit_oid = Column(String(128), nullable=False)
    signer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    algorithm = Column(String(32), default="hmac-sha256")
    signature = Column(String(512), nullable=False)
    verified = Column(Boolean, default=False)
    created_at = Column(Float, default=time.time)

    repo = relationship("Repository")
    signer = relationship("User")


# ── Kubernetes Deployments ─────────────────────────────────────────────────────

class K8sDeployment(Base):
    __tablename__ = "k8s_deployments"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    triggered_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    namespace = Column(String(128), default="default")
    image = Column(String(512), nullable=False)
    tag = Column(String(128), default="latest")
    replicas = Column(Integer, default=1)
    status = Column(String(16), default="pending")  # pending | running | succeeded | failed
    manifest = Column(String(65536), default="{}")  # full YAML/JSON manifest
    log = Column(String(65536), default="")
    created_at = Column(Float, default=time.time)
    updated_at = Column(Float, default=time.time)

    repo = relationship("Repository")
    triggered_by = relationship("User")
