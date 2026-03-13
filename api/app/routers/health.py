"""
Health history and SSE pipeline streaming endpoints.

Endpoints:
  GET /api/v1/sites/{id}/health-history    — paginated health event history
  GET /api/v1/pipelines/{id}/stream        — SSE log stream for a pipeline
"""

import asyncio
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.authorize import authorize
from app.core.database import SessionLocal, get_db
from app.core.permissions import Permission
from app.models.health_event import HealthEvent
from app.models.pipeline import PipelineRun, PipelineStage
from app.models.site import Site

router = APIRouter(tags=["health"])


class HealthEventResponse(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    check_time: datetime
    status_code: int | None
    response_ms: int | None
    healthy: bool
    action_taken: str | None

    model_config = {"from_attributes": True}


class SiteHealthSummary(BaseModel):
    site_id: uuid.UUID
    site_slug: str
    health_status: str | None
    health_failure_count: int
    last_health_check: datetime | None
    last_healthy_at: datetime | None
    recent_events: list[HealthEventResponse]


@router.get(
    "/api/v1/sites/{site_id}/health-history",
    response_model=SiteHealthSummary,
)
async def get_health_history(
    site_id: uuid.UUID,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get health check history for a site."""
    await authorize(user, Permission.SITE_VIEW, "site", site_id, db)

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    events = (
        db.query(HealthEvent)
        .filter(HealthEvent.site_id == site_id)
        .order_by(HealthEvent.check_time.desc())
        .limit(limit)
        .all()
    )

    return SiteHealthSummary(
        site_id=site.id,
        site_slug=site.slug,
        health_status=site.health_status,
        health_failure_count=site.health_failure_count or 0,
        last_health_check=site.last_health_check,
        last_healthy_at=site.last_healthy_at,
        recent_events=[HealthEventResponse.model_validate(e) for e in events],
    )


# ── SSE Pipeline Streaming ───────────────────────────────────────────


@router.get("/api/v1/pipelines/{pipeline_run_id}/stream")
async def stream_pipeline(
    pipeline_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Stream pipeline progress via Server-Sent Events.

    Events:
      - pipeline_status: overall status change
      - stage_started:   stage began execution
      - stage_log:       incremental log output
      - stage_completed: stage finished (passed/failed)
      - pipeline_done:   pipeline finished

    The stream polls the database every second for updates.
    Closes when the pipeline reaches a terminal state.
    """
    run = db.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    await authorize(user, Permission.SITE_VIEW, "site", run.site_id, db)

    return StreamingResponse(
        _pipeline_event_generator(str(pipeline_run_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _pipeline_event_generator(pipeline_run_id: str):
    """Generate SSE events by polling pipeline state."""
    import json

    last_status = None
    last_stage_statuses = {}
    last_log_lengths = {}

    while True:
        db = SessionLocal()
        try:
            run = (
                db.query(PipelineRun)
                .filter(PipelineRun.id == pipeline_run_id)
                .first()
            )
            if not run:
                yield _sse_event("error", {"message": "Pipeline not found"})
                return

            # Emit status changes
            if run.status != last_status:
                yield _sse_event(
                    "pipeline_status",
                    {
                        "status": run.status,
                        "started_at": run.started_at.isoformat() if run.started_at else None,
                    },
                )
                last_status = run.status

            # Emit stage updates
            for stage in run.stages:
                stage_key = str(stage.id)
                prev_status = last_stage_statuses.get(stage_key)

                if stage.status != prev_status:
                    if stage.status == "running" and prev_status != "running":
                        yield _sse_event(
                            "stage_started",
                            {"name": stage.name, "order": stage.order},
                        )
                    elif stage.status in ("passed", "failed", "skipped"):
                        yield _sse_event(
                            "stage_completed",
                            {
                                "name": stage.name,
                                "status": stage.status,
                                "duration_ms": stage.duration_ms,
                                "error": stage.error,
                            },
                        )
                    last_stage_statuses[stage_key] = stage.status

                # Emit incremental log updates
                if stage.logs:
                    prev_len = last_log_lengths.get(stage_key, 0)
                    if len(stage.logs) > prev_len:
                        new_logs = stage.logs[prev_len:]
                        yield _sse_event(
                            "stage_log",
                            {"name": stage.name, "log": new_logs},
                        )
                        last_log_lengths[stage_key] = len(stage.logs)

            # Check for terminal state
            if run.status in ("succeeded", "failed", "cancelled"):
                yield _sse_event(
                    "pipeline_done",
                    {
                        "status": run.status,
                        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                        "deployment_id": str(run.deployment_id) if run.deployment_id else None,
                    },
                )
                return

        finally:
            db.close()

        await asyncio.sleep(1)


def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    import json
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
