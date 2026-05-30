import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.portfolio import PortfolioItem
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PortfolioItemOut(BaseModel):
    id: uuid.UUID
    shareable_slug: str
    lab_title: str
    lab_slug: str
    lab_category: str
    lab_difficulty: str
    final_score: float
    passed: bool
    correctness_score: float
    safety_score: float
    efficiency_score: float
    duration_seconds: int | None
    summary: str | None
    completed_at: datetime
    is_public: bool

    model_config = {"from_attributes": True}


@router.get("/me", response_model=list[PortfolioItemOut])
async def my_portfolio(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    include_private: bool = True,
):
    q = select(PortfolioItem).where(PortfolioItem.user_id == current_user.id)
    if not include_private:
        q = q.where(PortfolioItem.is_public == True)
    q = q.order_by(PortfolioItem.completed_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/u/{username}", response_model=list[PortfolioItemOut])
async def public_portfolio(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    if not settings.feature_public_portfolio:
        raise HTTPException(503, "Public portfolios are not enabled")

    user_result = await db.execute(
        select(User).where(User.username == username.lower(), User.is_active == True)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    result = await db.execute(
        select(PortfolioItem).where(
            PortfolioItem.user_id == user.id,
            PortfolioItem.is_public == True,
        ).order_by(PortfolioItem.completed_at.desc())
    )
    return result.scalars().all()


@router.get("/p/{slug}", response_model=PortfolioItemOut)
async def get_portfolio_item(slug: str, db: AsyncSession = Depends(get_db)):
    """Public shareable result page."""
    result = await db.execute(
        select(PortfolioItem).where(PortfolioItem.shareable_slug == slug, PortfolioItem.is_public == True)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Portfolio item not found")
    return item


@router.patch("/me/{item_id}/visibility", response_model=PortfolioItemOut)
async def toggle_visibility(
    item_id: uuid.UUID,
    is_public: bool,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PortfolioItem).where(PortfolioItem.id == item_id, PortfolioItem.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Portfolio item not found")
    item.is_public = is_public
    await db.commit()
    await db.refresh(item)
    return item
