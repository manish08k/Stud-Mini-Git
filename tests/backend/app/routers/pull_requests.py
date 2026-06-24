"""Pull Requests router – open, review, merge, comment."""
from __future__ import annotations

import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import ensure_read_access, ensure_write_access, get_current_user, get_repo, require_user
from ..kafka_client import emit_event

router = APIRouter(prefix="/repos", tags=["pull-requests"])


def _next_pr_number(db: Session, repo_id: int) -> int:
    last = (
        db.query(models.PullRequest)
        .filter(models.PullRequest.repo_id == repo_id)
        .order_by(models.PullRequest.number.desc())
        .first()
    )
    return (last.number + 1) if last else 1


def _pr_out(pr: models.PullRequest) -> schemas.PROut:
    return schemas.PROut(
        id=pr.id,
        number=pr.number,
        title=pr.title,
        description=pr.description or "",
        author=pr.author.username,
        base_branch=pr.base_branch,
        head_branch=pr.head_branch,
        status=pr.status,
        created_at=pr.created_at,
        updated_at=pr.updated_at,
        reviews=[
            schemas.PRReviewOut(
                id=r.id,
                reviewer=r.reviewer.username,
                verdict=r.verdict,
                body=r.body or "",
                created_at=r.created_at,
            )
            for r in pr.reviews
        ],
        comments=[
            schemas.PRCommentOut(
                id=c.id,
                author=c.author.username,
                body=c.body,
                file_path=c.file_path,
                line_number=c.line_number,
                created_at=c.created_at,
            )
            for c in pr.comments
        ],
    )


def _get_pr(owner: str, repo: str, pr_number: int, db: Session) -> models.PullRequest:
    repo_row = get_repo(owner, repo, db)
    pr = (
        db.query(models.PullRequest)
        .filter(
            models.PullRequest.repo_id == repo_row.id,
            models.PullRequest.number == pr_number,
        )
        .first()
    )
    if pr is None:
        raise HTTPException(status_code=404, detail="pull request not found")
    return pr


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/{owner}/{repo}/pulls", response_model=schemas.PROut, status_code=201)
def create_pull_request(
    owner: str,
    repo: str,
    body: schemas.PRCreate,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)

    if body.base_branch == body.head_branch:
        raise HTTPException(status_code=400, detail="base and head branches must differ")

    pr = models.PullRequest(
        repo_id=repo_row.id,
        number=_next_pr_number(db, repo_row.id),
        title=body.title,
        description=body.description,
        author_id=user.id,
        base_branch=body.base_branch,
        head_branch=body.head_branch,
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    emit_event("pr.opened", {"repo": f"{owner}/{repo}", "pr": pr.number, "author": user.username})
    return _pr_out(pr)


@router.get("/{owner}/{repo}/pulls", response_model=List[schemas.PROut])
def list_pull_requests(
    owner: str,
    repo: str,
    status: Optional[str] = None,
    user: Optional[models.User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    q = db.query(models.PullRequest).filter(models.PullRequest.repo_id == repo_row.id)
    if status:
        q = q.filter(models.PullRequest.status == status)
    return [_pr_out(pr) for pr in q.order_by(models.PullRequest.number.desc()).all()]


@router.get("/{owner}/{repo}/pulls/{pr_number}", response_model=schemas.PROut)
def get_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    user: Optional[models.User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_row = get_repo(owner, repo, db)
    ensure_read_access(db, repo_row, user)
    return _pr_out(_get_pr(owner, repo, pr_number, db))


@router.patch("/{owner}/{repo}/pulls/{pr_number}", response_model=schemas.PROut)
def update_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    body: schemas.PRUpdate,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    pr = _get_pr(owner, repo, pr_number, db)
    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)

    if body.title is not None:
        pr.title = body.title
    if body.description is not None:
        pr.description = body.description
    if body.status is not None:
        if body.status not in ("open", "merged", "closed"):
            raise HTTPException(status_code=400, detail="status must be open, merged, or closed")
        pr.status = body.status
        if body.status == "merged":
            pr.merged_at = time.time()
            emit_event("pr.merged", {"repo": f"{owner}/{repo}", "pr": pr.number, "by": user.username})
        elif body.status == "closed":
            emit_event("pr.closed", {"repo": f"{owner}/{repo}", "pr": pr.number, "by": user.username})
    pr.updated_at = time.time()
    db.commit()
    db.refresh(pr)
    return _pr_out(pr)


@router.post("/{owner}/{repo}/pulls/{pr_number}/merge", response_model=schemas.PROut)
def merge_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    pr = _get_pr(owner, repo, pr_number, db)
    repo_row = get_repo(owner, repo, db)
    ensure_write_access(db, repo_row, user)

    if pr.status != "open":
        raise HTTPException(status_code=400, detail="pull request is not open")
    pr.status = "merged"
    pr.merged_at = time.time()
    pr.updated_at = time.time()
    db.commit()
    db.refresh(pr)
    emit_event("pr.merged", {"repo": f"{owner}/{repo}", "pr": pr.number, "by": user.username})
    return _pr_out(pr)


# ── Reviews ───────────────────────────────────────────────────────────────────

@router.post("/{owner}/{repo}/pulls/{pr_number}/reviews", response_model=schemas.PRReviewOut, status_code=201)
def create_review(
    owner: str,
    repo: str,
    pr_number: int,
    body: schemas.PRReviewCreate,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    pr = _get_pr(owner, repo, pr_number, db)
    if body.verdict not in ("approved", "changes_requested", "comment"):
        raise HTTPException(status_code=400, detail="verdict must be approved, changes_requested, or comment")

    review = models.PRReview(
        pr_id=pr.id,
        reviewer_id=user.id,
        verdict=body.verdict,
        body=body.body,
    )
    db.add(review)
    pr.updated_at = time.time()
    db.commit()
    db.refresh(review)
    emit_event("pr.reviewed", {
        "repo": f"{owner}/{repo}", "pr": pr_number,
        "reviewer": user.username, "verdict": body.verdict,
    })
    return schemas.PRReviewOut(
        id=review.id,
        reviewer=user.username,
        verdict=review.verdict,
        body=review.body or "",
        created_at=review.created_at,
    )


# ── Comments ──────────────────────────────────────────────────────────────────

@router.post("/{owner}/{repo}/pulls/{pr_number}/comments", response_model=schemas.PRCommentOut, status_code=201)
def create_comment(
    owner: str,
    repo: str,
    pr_number: int,
    body: schemas.PRCommentCreate,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    pr = _get_pr(owner, repo, pr_number, db)
    comment = models.PRComment(
        pr_id=pr.id,
        author_id=user.id,
        body=body.body,
        file_path=body.file_path,
        line_number=body.line_number,
    )
    db.add(comment)
    pr.updated_at = time.time()
    db.commit()
    db.refresh(comment)
    return schemas.PRCommentOut(
        id=comment.id,
        author=user.username,
        body=comment.body,
        file_path=comment.file_path,
        line_number=comment.line_number,
        created_at=comment.created_at,
    )


@router.delete("/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}")
def delete_comment(
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    pr = _get_pr(owner, repo, pr_number, db)
    comment = db.query(models.PRComment).filter(
        models.PRComment.id == comment_id,
        models.PRComment.pr_id == pr.id,
    ).first()
    if comment is None:
        raise HTTPException(status_code=404, detail="comment not found")
    repo_row = get_repo(owner, repo, db)
    if comment.author_id != user.id:
        ensure_write_access(db, repo_row, user)
    db.delete(comment)
    pr.updated_at = time.time()
    db.commit()
    return {"deleted": True}
