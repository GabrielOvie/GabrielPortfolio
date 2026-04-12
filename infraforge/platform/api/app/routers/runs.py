import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User, SubscriptionTier
from app.models.lab import Lab, LabVersion
from app.models.run import ChallengeRun, RunStatus
from app.services.orchestrator import get_orchestrator_client, OrchestratorError
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/runs", tags=["runs"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RunOut(BaseModel):
    id: uuid.UUID
    lab_id: uuid.UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    timeout_at: datetime | None
    duration_seconds: int | None
    final_score: float | None
    passed: bool | None
    # Only returned while run is active
    access_credentials: dict | None = None

    model_config = {"from_attributes": True}


class LaunchRunRequest(BaseModel):
    lab_slug: str


class SubmitRunRequest(BaseModel):
    run_id: uuid.UUID


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _count_active_runs(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(
            ChallengeRun.user_id == user_id,
            ChallengeRun.status.in_([RunStatus.queued, RunStatus.provisioning, RunStatus.running])
        )
    )
    return result.scalar_one()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=RunOut, status_code=201)
async def launch_run(
    body: LaunchRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Fetch lab
    lab_result = await db.execute(select(Lab).where(Lab.slug == body.lab_slug, Lab.is_published == True))
    lab = lab_result.scalar_one_or_none()
    if not lab:
        raise HTTPException(404, "Lab not found")

    # Paywall
    if not lab.is_free and current_user.subscription.tier == SubscriptionTier.free:
        raise HTTPException(402, "Pro subscription required")

    # VM labs gated by feature flag
    if lab.execution_model == "vm" and not settings.feature_vm_labs:
        raise HTTPException(503, "VM-based labs are not available in this environment")

    # Concurrent run limit
    active_count = await _count_active_runs(db, current_user.id)
    if active_count >= settings.max_concurrent_runs_per_user:
        raise HTTPException(429, f"You already have {active_count} active run(s). Finish or cancel them first.")

    # Get active lab version
    version_result = await db.execute(
        select(LabVersion).where(LabVersion.lab_id == lab.id, LabVersion.is_active == True)
    )
    version = version_result.scalar_one_or_none()
    if not version:
        raise HTTPException(503, "This lab has no active version. Contact support.")

    timeout_at = datetime.utcnow() + timedelta(minutes=lab.max_runtime_minutes)

    run = ChallengeRun(
        user_id=current_user.id,
        lab_id=lab.id,
        lab_version_id=version.id,
        status=RunStatus.provisioning,
        timeout_at=timeout_at,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Kick off provisioning in background
    background_tasks.add_task(
        _provision_run,
        run_id=run.id,
        template_id=version.template_id,
        image_tag=version.image_tag,
        user_id=current_user.id,
        timeout_minutes=lab.max_runtime_minutes,
    )

    return run


async def _provision_run(
    run_id: uuid.UUID,
    template_id: str,
    image_tag: str,
    user_id: uuid.UUID,
    timeout_minutes: int,
):
    """Background: call orchestrator to spin up the lab environment."""
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            orchestrator = get_orchestrator_client()
            result = await orchestrator.provision_lab(
                run_id=run_id,
                template_id=template_id,
                image_tag=image_tag,
                user_id=user_id,
                timeout_minutes=timeout_minutes,
            )

            run_result = await db.execute(select(ChallengeRun).where(ChallengeRun.id == run_id))
            run = run_result.scalar_one()
            run.orchestrator_run_id = result["orchestrator_run_id"]
            run.access_credentials = result["credentials"]
            run.status = RunStatus.running
            run.started_at = datetime.utcnow()
            await db.commit()

        except OrchestratorError as e:
            run_result = await db.execute(select(ChallengeRun).where(ChallengeRun.id == run_id))
            run = run_result.scalar_one()
            run.status = RunStatus.failed
            run.failure_reason = str(e)
            await db.commit()


@router.get("/{run_id}", response_model=RunOut)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChallengeRun).where(ChallengeRun.id == run_id, ChallengeRun.user_id == current_user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")

    out = RunOut.model_validate(run)
    # Credentials are only surfaced while the run is active
    if run.status not in (RunStatus.running,):
        out.access_credentials = None
    return out


@router.post("/{run_id}/submit", response_model=RunOut)
async def submit_run(
    run_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User triggers manual grading (auto-grading also fires on timeout)."""
    result = await db.execute(
        select(ChallengeRun).where(ChallengeRun.id == run_id, ChallengeRun.user_id == current_user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status != RunStatus.running:
        raise HTTPException(409, f"Run is {run.status}, cannot submit")

    run.status = RunStatus.grading
    await db.commit()

    # Kick off grading
    background_tasks.add_task(_grade_run, run_id=run_id)
    return run


@router.delete("/{run_id}", status_code=204)
async def cancel_run(
    run_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChallengeRun).where(ChallengeRun.id == run_id, ChallengeRun.user_id == current_user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status in (RunStatus.completed, RunStatus.failed):
        raise HTTPException(409, "Run is already finished")

    run.status = RunStatus.cancelled
    await db.commit()

    if run.orchestrator_run_id:
        background_tasks.add_task(_teardown_run, orchestrator_run_id=run.orchestrator_run_id)


async def _grade_run(run_id: uuid.UUID):
    """Background: call orchestrator → grader, then store result."""
    from app.db import AsyncSessionLocal
    from app.workers.tasks import finalize_run_score
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ChallengeRun).where(ChallengeRun.id == run_id)
        )
        run = result.scalar_one()
        # Delegate to Celery so it's retriable and observable
        finalize_run_score.delay(str(run_id))


async def _teardown_run(orchestrator_run_id: str):
    from app.db import AsyncSessionLocal
    orchestrator = get_orchestrator_client()
    try:
        await orchestrator.teardown_run(orchestrator_run_id)
    except Exception:
        pass  # sweeper will catch stale runs
