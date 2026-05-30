import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Float, Boolean, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base


class PortfolioItem(Base):
    """A single verifiable lab result surfaced on a user's public portfolio.

    This is the thing an employer or recruiter can link to.
    The shareable_slug gives a stable, public, human-readable URL.
    """
    __tablename__ = "portfolio_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("challenge_runs.id"), unique=True, nullable=False)

    # Stable shareable slug, e.g. gabriel-linux-service-outage-2024
    shareable_slug: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)

    # Snapshot data (denormalized at creation time so score is immutable)
    lab_title: Mapped[str] = mapped_column(String(256), nullable=False)
    lab_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    lab_category: Mapped[str] = mapped_column(String(64), nullable=False)
    lab_difficulty: Mapped[str] = mapped_column(String(32), nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    correctness_score: Mapped[float] = mapped_column(Float, nullable=False)
    safety_score: Mapped[float] = mapped_column(Float, nullable=False)
    efficiency_score: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    # Human-readable summary: "Restored broken nginx in 21 min. Passed 17/18 safety checks."
    summary: Mapped[str] = mapped_column(Text, nullable=True)

    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="portfolio_items")
    run: Mapped["ChallengeRun"] = relationship("ChallengeRun", back_populates="portfolio_item")
