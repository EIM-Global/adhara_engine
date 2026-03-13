"""
Git webhook receivers for automatic deployments.

Endpoints:
  POST /api/v1/webhooks/github  — GitHub push events (HMAC-SHA256 verified)
  POST /api/v1/webhooks/gitlab  — GitLab push events (token header verified)

Flow:
  1. Receive webhook payload
  2. Verify signature/token
  3. Normalize to PushEvent
  4. Find matching site (by repo URL + branch + auto_deploy=True)
  5. Dedup by commit SHA (skip if already deployed)
  6. Create PipelineRun and enqueue ARQ job
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass

from arq.connections import RedisSettings, create_pool
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.pipeline import PipelineRun
from app.models.preview_environment import PreviewEnvironment
from app.models.site import Site
from app.services.preview_manager import create_or_update_preview, destroy_preview

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])

# Lazily initialized ARQ pool
_arq_pool = None


async def _get_arq_pool():
    global _arq_pool
    if _arq_pool is None:
        url = settings.redis_url.replace("redis://", "")
        parts = url.split("/")
        host_port = parts[0]
        database = int(parts[1]) if len(parts) > 1 else 0
        host, port = (host_port.rsplit(":", 1) + ["6379"])[:2]
        _arq_pool = await create_pool(
            RedisSettings(host=host, port=int(port), database=database)
        )
    return _arq_pool


@dataclass
class PushEvent:
    """Normalized push event from any git provider."""

    provider: str  # "github" or "gitlab"
    repo_url: str  # HTTPS clone URL
    repo_path: str  # "owner/repo"
    branch: str  # "main"
    commit_sha: str
    commit_message: str | None
    commit_author: str | None
    is_branch_delete: bool


# ── GitHub ───────────────────────────────────────────────────────────


@router.post("/api/v1/webhooks/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive GitHub push webhook.

    Verification: HMAC-SHA256 of request body using per-site webhook_secret.
    Header: X-Hub-Signature-256: sha256=<hex>
    """
    body = await request.body()
    payload = await request.json()

    event_type = request.headers.get("X-GitHub-Event", "")
    if event_type == "ping":
        return {"status": "pong"}

    # Handle PR events for preview environments
    if event_type == "pull_request":
        return await _handle_github_pr(payload, body, db)

    if event_type != "push":
        return {"status": "ignored", "reason": f"event type '{event_type}' not handled"}

    # Parse push event
    push = _parse_github_push(payload)
    if push is None:
        return {"status": "ignored", "reason": "could not parse push event"}
    if push.is_branch_delete:
        return {"status": "ignored", "reason": "branch delete"}

    # Find matching site
    site = _find_site_for_push(db, push)
    if site is None:
        logger.info(f"No matching site for GitHub push to {push.repo_path}:{push.branch}")
        return {"status": "ignored", "reason": "no matching site"}

    # Verify HMAC signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not site.webhook_secret:
        raise HTTPException(status_code=403, detail="Site has no webhook secret configured")
    if not _verify_github_signature(body, site.webhook_secret, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Dedup: skip if this SHA was already deployed
    if site.last_deployed_sha == push.commit_sha:
        return {"status": "skipped", "reason": "commit already deployed"}

    # Enqueue pipeline
    result = await _enqueue_pipeline(db, site, push)
    return result


def _parse_github_push(payload: dict) -> PushEvent | None:
    """Parse a GitHub push webhook payload into a PushEvent."""
    try:
        ref = payload.get("ref", "")
        if not ref.startswith("refs/heads/"):
            return None

        branch = ref.replace("refs/heads/", "")
        is_delete = payload.get("deleted", False)

        repo = payload.get("repository", {})
        clone_url = repo.get("clone_url", "")
        full_name = repo.get("full_name", "")

        head_commit = payload.get("head_commit") or {}
        commit_sha = payload.get("after", "")
        commit_message = head_commit.get("message")
        commit_author = (head_commit.get("author") or {}).get("name")

        return PushEvent(
            provider="github",
            repo_url=clone_url,
            repo_path=full_name,
            branch=branch,
            commit_sha=commit_sha,
            commit_message=commit_message,
            commit_author=commit_author,
            is_branch_delete=is_delete,
        )
    except Exception as e:
        logger.warning(f"Failed to parse GitHub push payload: {e}")
        return None


def _verify_github_signature(body: bytes, secret: str, signature: str) -> bool:
    """Verify GitHub HMAC-SHA256 webhook signature."""
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── GitLab ───────────────────────────────────────────────────────────


@router.post("/api/v1/webhooks/gitlab")
async def gitlab_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive GitLab push webhook.

    Verification: X-Gitlab-Token header must match per-site webhook_secret.
    """
    payload = await request.json()

    event_type = payload.get("object_kind", "")

    # Handle MR events for preview environments
    if event_type == "merge_request":
        return await _handle_gitlab_mr(payload, db)

    if event_type != "push":
        return {"status": "ignored", "reason": f"event type '{event_type}' not handled"}

    # Parse push event
    push = _parse_gitlab_push(payload)
    if push is None:
        return {"status": "ignored", "reason": "could not parse push event"}
    if push.is_branch_delete:
        return {"status": "ignored", "reason": "branch delete"}

    # Find matching site
    site = _find_site_for_push(db, push)
    if site is None:
        logger.info(f"No matching site for GitLab push to {push.repo_path}:{push.branch}")
        return {"status": "ignored", "reason": "no matching site"}

    # Verify token
    token = request.headers.get("X-Gitlab-Token", "")
    if not site.webhook_secret:
        raise HTTPException(status_code=403, detail="Site has no webhook secret configured")
    if not hmac.compare_digest(token, site.webhook_secret):
        raise HTTPException(status_code=403, detail="Invalid token")

    # Dedup
    if site.last_deployed_sha == push.commit_sha:
        return {"status": "skipped", "reason": "commit already deployed"}

    # Enqueue pipeline
    result = await _enqueue_pipeline(db, site, push)
    return result


def _parse_gitlab_push(payload: dict) -> PushEvent | None:
    """Parse a GitLab push webhook payload into a PushEvent."""
    try:
        ref = payload.get("ref", "")
        if not ref.startswith("refs/heads/"):
            return None

        branch = ref.replace("refs/heads/", "")
        # GitLab signals delete with after=0000...
        after = payload.get("after", "")
        is_delete = after == "0" * 40

        project = payload.get("project", {})
        clone_url = project.get("http_url", "") or project.get("git_http_url", "")
        path_with_ns = project.get("path_with_namespace", "")

        commits = payload.get("commits", [])
        last_commit = commits[-1] if commits else {}
        commit_sha = payload.get("checkout_sha") or after
        commit_message = last_commit.get("message")
        commit_author = (last_commit.get("author") or {}).get("name")

        return PushEvent(
            provider="gitlab",
            repo_url=clone_url,
            repo_path=path_with_ns,
            branch=branch,
            commit_sha=commit_sha,
            commit_message=commit_message,
            commit_author=commit_author,
            is_branch_delete=is_delete,
        )
    except Exception as e:
        logger.warning(f"Failed to parse GitLab push payload: {e}")
        return None


# ── Shared helpers ───────────────────────────────────────────────────


def _find_site_for_push(db: Session, push: PushEvent) -> Site | None:
    """Find a site that matches this push event.

    Matches on:
      - source_url contains the repo path (handles URL variations)
      - git_branch matches the pushed branch
      - auto_deploy is True
      - git_provider matches (or is None for legacy sites)
    """
    # Normalize repo URL for comparison
    repo_path_lower = push.repo_path.lower()

    sites = (
        db.query(Site)
        .filter(
            Site.auto_deploy.is_(True),
            Site.source_type == "git_repo",
        )
        .all()
    )

    for site in sites:
        if not site.source_url:
            continue

        # Check if the repo matches (comparing normalized paths)
        site_url_lower = site.source_url.lower()
        if repo_path_lower not in site_url_lower:
            continue

        # Check branch match
        site_branch = site.git_branch or "main"
        if site_branch != push.branch:
            continue

        # Check provider match (if specified)
        if site.git_provider and site.git_provider != push.provider:
            continue

        return site

    return None


async def _enqueue_pipeline(db: Session, site: Site, push: PushEvent) -> dict:
    """Create a PipelineRun and enqueue it via ARQ."""
    run = PipelineRun(
        site_id=site.id,
        tenant_id=site.tenant_id,
        trigger="webhook",
        git_provider=push.provider,
        git_ref=f"refs/heads/{push.branch}",
        commit_sha=push.commit_sha,
        commit_message=push.commit_message,
        commit_author=push.commit_author,
        status="pending",
        triggered_by=f"webhook:{push.provider}",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        pool = await _get_arq_pool()
        await pool.enqueue_job("run_pipeline", str(run.id))
    except Exception as e:
        run.status = "failed"
        db.commit()
        logger.error(f"Failed to enqueue webhook pipeline: {e}")
        return {"status": "error", "error": str(e)}

    logger.info(
        f"Webhook pipeline {run.id} enqueued for {site.slug} "
        f"({push.provider} {push.branch}@{push.commit_sha[:8]})"
    )
    return {
        "status": "accepted",
        "pipeline_run_id": str(run.id),
        "site": site.slug,
        "commit": push.commit_sha[:8],
    }


# ── PR/MR Preview Handlers ──────────────────────────────────────────


async def _handle_github_pr(payload: dict, body: bytes, db) -> dict:
    """Handle GitHub pull_request events for preview environments."""
    action = payload.get("action", "")
    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")

    if not pr_number:
        return {"status": "ignored", "reason": "no PR number"}

    repo = payload.get("repository", {})
    repo_path = repo.get("full_name", "").lower()

    # Find the matching site
    site = _find_site_for_repo(db, repo_path, "github")
    if not site:
        return {"status": "ignored", "reason": "no matching site for PR preview"}

    # Verify signature
    signature = payload.get("X-Hub-Signature-256", "")
    # For PR events we still verify the signature if present
    if site.webhook_secret and signature:
        if not _verify_github_signature(body, site.webhook_secret, signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

    if action in ("opened", "synchronize", "reopened"):
        # Create or update preview
        head = pr.get("head", {})
        preview = await create_or_update_preview(
            db=db,
            site=site,
            pr_number=pr_number,
            pr_branch=head.get("ref", ""),
            commit_sha=head.get("sha", ""),
            git_provider="github",
            pr_title=pr.get("title"),
            pr_author=pr.get("user", {}).get("login"),
            pr_url=pr.get("html_url"),
        )
        return {
            "status": "preview_building",
            "preview_id": str(preview.id),
            "pr_number": pr_number,
        }

    elif action in ("closed",):
        # Destroy preview
        merged = pr.get("merged", False)
        existing = (
            db.query(PreviewEnvironment)
            .filter(
                PreviewEnvironment.site_id == site.id,
                PreviewEnvironment.pr_number == pr_number,
                PreviewEnvironment.status != "destroyed",
            )
            .first()
        )
        if existing:
            existing.pr_state = "merged" if merged else "closed"
            reason = "pr_merged" if merged else "pr_closed"
            await destroy_preview(db, existing, reason=reason)
            return {"status": "preview_destroyed", "reason": reason}

        return {"status": "ignored", "reason": "no active preview for this PR"}

    return {"status": "ignored", "reason": f"PR action '{action}' not handled"}


async def _handle_gitlab_mr(payload: dict, db) -> dict:
    """Handle GitLab merge_request events for preview environments."""
    attrs = payload.get("object_attributes", {})
    action = attrs.get("action", "")
    mr_iid = attrs.get("iid")

    if not mr_iid:
        return {"status": "ignored", "reason": "no MR number"}

    project = payload.get("project", {})
    repo_path = project.get("path_with_namespace", "").lower()

    site = _find_site_for_repo(db, repo_path, "gitlab")
    if not site:
        return {"status": "ignored", "reason": "no matching site for MR preview"}

    if action in ("open", "update", "reopen"):
        preview = await create_or_update_preview(
            db=db,
            site=site,
            pr_number=mr_iid,
            pr_branch=attrs.get("source_branch", ""),
            commit_sha=attrs.get("last_commit", {}).get("id", ""),
            git_provider="gitlab",
            pr_title=attrs.get("title"),
            pr_author=payload.get("user", {}).get("username"),
            pr_url=attrs.get("url"),
        )
        return {
            "status": "preview_building",
            "preview_id": str(preview.id),
            "mr_number": mr_iid,
        }

    elif action in ("close", "merge"):
        existing = (
            db.query(PreviewEnvironment)
            .filter(
                PreviewEnvironment.site_id == site.id,
                PreviewEnvironment.pr_number == mr_iid,
                PreviewEnvironment.status != "destroyed",
            )
            .first()
        )
        if existing:
            existing.pr_state = "merged" if action == "merge" else "closed"
            reason = f"pr_{action}d" if action != "merge" else "pr_merged"
            await destroy_preview(db, existing, reason=reason)
            return {"status": "preview_destroyed", "reason": reason}

        return {"status": "ignored", "reason": "no active preview for this MR"}

    return {"status": "ignored", "reason": f"MR action '{action}' not handled"}


def _find_site_for_repo(db, repo_path: str, provider: str) -> Site | None:
    """Find a site matching a repo path (for PR preview support)."""
    sites = (
        db.query(Site)
        .filter(Site.source_type == "git_repo")
        .all()
    )
    for site in sites:
        if not site.source_url:
            continue
        if repo_path in site.source_url.lower():
            if not site.git_provider or site.git_provider == provider:
                return site
    return None
