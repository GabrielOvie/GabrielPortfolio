from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
import uuid
from datetime import datetime

from app.db import get_db
from app.deps import get_current_user, get_current_admin
from app.models.user import User, SubscriptionTier
from app.models.lab import Lab, LabVersion, LabDifficulty, LabCategory

router = APIRouter(prefix="/labs", tags=["labs"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class LabOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    description: str
    category: str
    difficulty: str
    execution_model: str
    estimated_minutes: int
    max_runtime_minutes: int
    is_free: bool
    total_runs: int
    avg_completion_minutes: float | None
    avg_score: float | None
    pass_rate: float | None
    # Scoring weights
    weight_correctness: float
    weight_safety: float
    weight_efficiency: float

    model_config = {"from_attributes": True}


class LabDetailOut(LabOut):
    # Includes the scenario text from the active version
    scenario_markdown: str | None = None
    version_number: int | None = None


class LabCreateRequest(BaseModel):
    slug: str
    title: str
    description: str
    category: LabCategory
    difficulty: LabDifficulty
    estimated_minutes: int
    max_runtime_minutes: int = 90
    is_free: bool = False
    weight_correctness: float = 0.60
    weight_safety: float = 0.25
    weight_efficiency: float = 0.15


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[LabOut])
async def list_labs(
    category: LabCategory | None = None,
    difficulty: LabDifficulty | None = None,
    free_only: bool = False,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Lab).where(Lab.is_published == True)
    if category:
        q = q.where(Lab.category == category)
    if difficulty:
        q = q.where(Lab.difficulty == difficulty)
    if free_only:
        q = q.where(Lab.is_free == True)
    q = q.order_by(Lab.category, Lab.difficulty, Lab.title).offset(offset).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{slug}", response_model=LabDetailOut)
async def get_lab(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Lab).where(Lab.slug == slug, Lab.is_published == True))
    lab = result.scalar_one_or_none()
    if not lab:
        raise HTTPException(404, "Lab not found")

    # Check paywall
    if not lab.is_free and current_user.subscription.tier == SubscriptionTier.free:
        raise HTTPException(402, "This lab requires a Pro subscription")

    # Get active version scenario
    version_result = await db.execute(
        select(LabVersion).where(LabVersion.lab_id == lab.id, LabVersion.is_active == True)
    )
    version = version_result.scalar_one_or_none()

    out = LabDetailOut.model_validate(lab)
    if version:
        out.scenario_markdown = version.scenario_markdown
        out.version_number = version.version_number
    return out


@router.post("", response_model=LabOut, status_code=201)
async def create_lab(
    body: LabCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    existing = await db.execute(select(Lab).where(Lab.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Lab with this slug already exists")

    lab = Lab(**body.model_dump())
    db.add(lab)
    await db.commit()
    await db.refresh(lab)
    return lab
