"""GraphQL API layer – powered by Strawberry + FastAPI.

Mount with:
    from app.graphql_schema import graphql_app
    app.include_router(graphql_app, prefix="/graphql")

or add the Strawberry router directly (see main.py).
"""
from __future__ import annotations

from typing import List, Optional

import strawberry
from strawberry.fastapi import GraphQLRouter
from sqlalchemy.orm import Session

from . import models
from .database import SessionLocal
from .deps import _collab_role
from .logging_config import StructLogger as _SL
get_logger = _SL

logger = get_logger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _db() -> Session:  # cheap session factory for resolvers
    return SessionLocal()


# ── types ──────────────────────────────────────────────────────────────────────

@strawberry.type
class UserType:
    id: int
    username: str


@strawberry.type
class RepoType:
    id: int
    owner: str
    name: str
    private: bool
    default_branch: str


@strawberry.type
class CollaboratorType:
    username: str
    role: str


# ── query ──────────────────────────────────────────────────────────────────────

@strawberry.type
class Query:
    @strawberry.field(description="Fetch a user by username.")
    def user(self, username: str) -> Optional[UserType]:
        db = _db()
        try:
            row = db.query(models.User).filter(models.User.username == username).first()
            if row is None:
                return None
            return UserType(id=row.id, username=row.username)
        finally:
            db.close()

    @strawberry.field(description="List repositories (optionally filter by owner).")
    def repos(self, owner: Optional[str] = None) -> List[RepoType]:
        db = _db()
        try:
            q = db.query(models.Repository)
            if owner:
                q = q.join(models.User, models.Repository.owner_id == models.User.id).filter(
                    models.User.username == owner
                )
            results = []
            for r in q.all():
                if not r.is_private:
                    results.append(
                        RepoType(
                            id=r.id,
                            owner=r.owner.username,
                            name=r.name,
                            private=r.is_private,
                            default_branch=r.default_branch,
                        )
                    )
            return results
        finally:
            db.close()

    @strawberry.field(description="Get a single repository.")
    def repo(self, owner: str, name: str) -> Optional[RepoType]:
        db = _db()
        try:
            owner_row = db.query(models.User).filter(models.User.username == owner).first()
            if not owner_row:
                return None
            r = (
                db.query(models.Repository)
                .filter(
                    models.Repository.owner_id == owner_row.id,
                    models.Repository.name == name,
                )
                .first()
            )
            if r is None or r.is_private:
                return None
            return RepoType(
                id=r.id,
                owner=owner,
                name=r.name,
                private=r.is_private,
                default_branch=r.default_branch,
            )
        finally:
            db.close()

    @strawberry.field(description="List collaborators of a repository.")
    def collaborators(self, owner: str, repo: str) -> List[CollaboratorType]:
        db = _db()
        try:
            owner_row = db.query(models.User).filter(models.User.username == owner).first()
            if not owner_row:
                return []
            r = (
                db.query(models.Repository)
                .filter(
                    models.Repository.owner_id == owner_row.id,
                    models.Repository.name == repo,
                )
                .first()
            )
            if r is None:
                return []
            return [
                CollaboratorType(username=c.user.username, role=c.role)
                for c in r.collaborators
            ]
        finally:
            db.close()


# ── schema & router ───────────────────────────────────────────────────────────

schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema, graphiql=True)


# ── Extended types ─────────────────────────────────────────────────────────────

@strawberry.type
class PRType:
    id: int
    number: int
    title: str
    status: str
    author: str
    base_branch: str
    head_branch: str


@strawberry.type
class RunnerType:
    id: int
    name: str
    status: str
    os: str
    arch: str
    labels: str


@strawberry.type
class DeploymentType:
    id: int
    namespace: str
    image: str
    tag: str
    replicas: int
    status: str


# ── extended query – monkey-patched onto existing schema ───────────────────────
# (Strawberry doesn't support extending types after definition, so we
#  add a second schema route at /graphql/extended instead)

@strawberry.type
class ExtendedQuery(Query):
    @strawberry.field(description="List pull requests for a repo.")
    def pull_requests(self, owner: str, repo: str, status: Optional[str] = None) -> List[PRType]:
        db = _db()
        try:
            from . import models as m
            owner_row = db.query(m.User).filter(m.User.username == owner).first()
            if not owner_row:
                return []
            r = (
                db.query(m.Repository)
                .filter(m.Repository.owner_id == owner_row.id, m.Repository.name == repo)
                .first()
            )
            if r is None or r.is_private:
                return []
            q = db.query(m.PullRequest).filter(m.PullRequest.repo_id == r.id)
            if status:
                q = q.filter(m.PullRequest.status == status)
            return [
                PRType(
                    id=p.id, number=p.number, title=p.title,
                    status=p.status, author=p.author.username,
                    base_branch=p.base_branch, head_branch=p.head_branch,
                )
                for p in q.all()
            ]
        finally:
            db.close()

    @strawberry.field(description="List self-hosted runners for the authenticated user.")
    def runners(self, username: str) -> List[RunnerType]:
        db = _db()
        try:
            from . import models as m
            user = db.query(m.User).filter(m.User.username == username).first()
            if not user:
                return []
            return [
                RunnerType(id=r.id, name=r.name, status=r.status,
                           os=r.os, arch=r.arch, labels=r.labels)
                for r in db.query(m.Runner).filter(m.Runner.owner_id == user.id).all()
            ]
        finally:
            db.close()


extended_schema = strawberry.Schema(query=ExtendedQuery)
extended_graphql_app = GraphQLRouter(extended_schema, graphiql=True)
