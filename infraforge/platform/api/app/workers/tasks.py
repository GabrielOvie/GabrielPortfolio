"""Celery tasks for the platform worker.

Key tasks:
  - finalize_run_score   — calls grader, stores result, creates portfolio item
  - sweep_stale_runs     — kills expired runs that weren't cleaned up
  - update_lab_stats     — refreshes denormalized lab statistics
  - check_badge_awards   — evaluates badge criteria after a run completes
"""
import uuid
import asyncio
from datetime import datetime, timedelta
from celery import shared_task

from app.workers.celery_app import celery_app


def run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, queue="scoring")
def finalize_run_score(self, run_id: str):
    """Retrieve grading result and store scoring + portfolio entry."""
    async def _run():
        from app.db import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.run import ChallengeRun, RunStatus
        from app.models.scoring import ScoringResult, ScoreBreakdown
        from app.models.portfolio import PortfolioItem
        from app.models.lab import Lab, LabVersion
        from app.services.orchestrator import get_orchestrator_client

        async with AsyncSessionLocal() as db:
            run_result = await db.execute(select(ChallengeRun).where(ChallengeRun.id == uuid.UUID(run_id)))
            run = run_result.scalar_one_or_none()
            if not run:
                return

            lab_result = await db.execute(select(Lab).where(Lab.id == run.lab_id))
            lab = lab_result.scalar_one()

            version_result = await db.execute(select(LabVersion).where(LabVersion.id == run.lab_version_id))
            version = version_result.scalar_one()

            # Request grading from orchestrator → grader
            orchestrator = get_orchestrator_client()
            try:
                grading_job_id = await orchestrator.trigger_grading(
                    run.orchestrator_run_id,
                    version.grading_spec,
                )
                # Poll for result (grader is fast — typically < 30s)
                grade_data = await _poll_grading_result(orchestrator, grading_job_id)
            except Exception as exc:
                raise self.retry(exc=exc)

            # Compute weighted score
            w_c = lab.weight_correctness
            w_s = lab.weight_safety
            w_e = lab.weight_efficiency
            final = (
                grade_data["correctness_score"] * w_c +
                grade_data["safety_score"] * w_s +
                grade_data["efficiency_score"] * w_e
            )

            scoring = ScoringResult(
                run_id=run.id,
                final_score=round(final, 2),
                passed=final >= 60.0,
                correctness_score=grade_data["correctness_score"],
                safety_score=grade_data["safety_score"],
                efficiency_score=grade_data["efficiency_score"],
                weight_correctness=w_c,
                weight_safety=w_s,
                weight_efficiency=w_e,
                summary=grade_data.get("summary"),
                check_results=grade_data.get("check_results", []),
            )
            db.add(scoring)

            # Store individual check rows for reporting
            for check in grade_data.get("check_results", []):
                db.add(ScoreBreakdown(
                    scoring_result_id=scoring.id,
                    check_id=check["check_id"],
                    layer=check["layer"],
                    description=check["description"],
                    passed=check["passed"],
                    weight=check["weight"],
                    detail=check.get("detail"),
                    points_earned=check.get("points_earned", 0),
                    points_possible=check.get("points_possible", 0),
                ))

            # Update run
            run.status = RunStatus.completed
            run.final_score = scoring.final_score
            run.passed = scoring.passed
            run.completed_at = datetime.utcnow()
            if run.started_at:
                run.duration_seconds = int((run.completed_at - run.started_at).total_seconds())

            # Build portfolio item
            _create_portfolio_item(db, run, lab, scoring)

            await db.commit()

            # Teardown environment
            if run.orchestrator_run_id:
                try:
                    await orchestrator.teardown_run(run.orchestrator_run_id)
                except Exception:
                    pass  # sweeper will handle it

            # Check badges (non-blocking)
            check_badge_awards.delay(str(run.user_id), str(run.id))

    run_async(_run())


async def _poll_grading_result(orchestrator, grading_job_id: str, max_wait: int = 120):
    """Poll grader until result is ready (max 2 minutes)."""
    import asyncio
    for _ in range(max_wait // 3):
        await asyncio.sleep(3)
        status = await orchestrator.get_run_status(grading_job_id)
        if status.get("status") == "completed":
            return status.get("result")
    raise TimeoutError(f"Grading job {grading_job_id} timed out")


def _create_portfolio_item(db, run, lab, scoring):
    from app.models.portfolio import PortfolioItem
    import re
    # Slug: {username}-{lab-slug}-{YYYYMMDD}
    # We don't have username here but run.user_id is enough for uniqueness
    slug = f"{str(run.user_id)[:8]}-{lab.slug}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"
    item = PortfolioItem(
        user_id=run.user_id,
        run_id=run.id,
        shareable_slug=slug,
        is_public=True,
        lab_title=lab.title,
        lab_slug=lab.slug,
        lab_category=lab.category.value,
        lab_difficulty=lab.difficulty.value,
        final_score=scoring.final_score,
        passed=scoring.passed,
        correctness_score=scoring.correctness_score,
        safety_score=scoring.safety_score,
        efficiency_score=scoring.efficiency_score,
        duration_seconds=run.duration_seconds,
        summary=scoring.summary,
        completed_at=run.completed_at or datetime.utcnow(),
    )
    db.add(item)


@celery_app.task(queue="default")
def check_badge_awards(user_id: str, run_id: str):
    """Evaluate badge criteria after a run completes. Best-effort."""
    async def _run():
        from app.db import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.scoring import Badge, UserBadge
        from app.models.run import ChallengeRun

        async with AsyncSessionLocal() as db:
            badges_result = await db.execute(select(Badge))
            badges = badges_result.scalars().all()

            run_result = await db.execute(select(ChallengeRun).where(ChallengeRun.id == uuid.UUID(run_id)))
            run = run_result.scalar_one_or_none()
            if not run or not run.scoring_result:
                return

            for badge in badges:
                criteria = badge.criteria
                if criteria.get("type") == "lab_pass":
                    from app.models.lab import Lab
                    lab_result = await db.execute(select(Lab).where(Lab.id == run.lab_id))
                    lab = lab_result.scalar_one_or_none()
                    if lab and lab.slug == criteria.get("lab_slug"):
                        min_score = criteria.get("min_score", 60)
                        if run.final_score and run.final_score >= min_score:
                            # Check not already awarded
                            existing = await db.execute(
                                select(UserBadge).where(
                                    UserBadge.user_id == uuid.UUID(user_id),
                                    UserBadge.badge_id == badge.id,
                                )
                            )
                            if not existing.scalar_one_or_none():
                                db.add(UserBadge(
                                    user_id=uuid.UUID(user_id),
                                    badge_id=badge.id,
                                    run_id=run.id,
                                ))
            await db.commit()

    run_async(_run())


@celery_app.task(queue="default")
def sweep_stale_runs():
    """Kill runs that exceeded their timeout and haven't been cleaned up."""
    async def _run():
        from app.db import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.run import ChallengeRun, RunStatus
        from app.services.orchestrator import get_orchestrator_client

        async with AsyncSessionLocal() as db:
            now = datetime.utcnow()
            result = await db.execute(
                select(ChallengeRun).where(
                    ChallengeRun.status.in_([RunStatus.running, RunStatus.provisioning]),
                    ChallengeRun.timeout_at < now,
                )
            )
            stale_runs = result.scalars().all()
            orchestrator = get_orchestrator_client()

            for run in stale_runs:
                run.status = RunStatus.timeout
                run.completed_at = now
                if run.started_at:
                    run.duration_seconds = int((now - run.started_at).total_seconds())

                if run.orchestrator_run_id:
                    try:
                        await orchestrator.teardown_run(run.orchestrator_run_id)
                    except Exception:
                        pass

            await db.commit()

    run_async(_run())


@celery_app.task(queue="default")
def update_lab_stats():
    """Refresh denormalized stats on the labs table (runs hourly)."""
    async def _run():
        from app.db import AsyncSessionLocal
        from sqlalchemy import select, func
        from app.models.lab import Lab
        from app.models.run import ChallengeRun, RunStatus

        async with AsyncSessionLocal() as db:
            labs_result = await db.execute(select(Lab))
            labs = labs_result.scalars().all()

            for lab in labs:
                stats = await db.execute(
                    select(
                        func.count(ChallengeRun.id).label("total"),
                        func.avg(ChallengeRun.duration_seconds).label("avg_dur"),
                        func.avg(ChallengeRun.final_score).label("avg_score"),
                        func.avg(ChallengeRun.passed.cast(db.bind.dialect.type_descriptor(None).__class__)).label("pass_rate"),
                    ).where(
                        ChallengeRun.lab_id == lab.id,
                        ChallengeRun.status == RunStatus.completed,
                    )
                )
                row = stats.one()
                lab.total_runs = row.total or 0
                lab.avg_completion_minutes = (row.avg_dur / 60) if row.avg_dur else None
                lab.avg_score = row.avg_score
                lab.pass_rate = row.pass_rate

            await db.commit()

    run_async(_run())
