import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Float, Boolean, Integer, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base


class ScoringResult(Base):
    """Final graded outcome for a challenge run.

    Score breakdown:
      correctness  60% — did the environment reach goal state?
      safety       25% — did the user avoid destructive / over-privileged actions?
      efficiency   15% — how fast, how cleanly?
    """
    __tablename__ = "scoring_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("challenge_runs.id"), unique=True, nullable=False)

    # Weighted final score 0–100
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Layer scores 0–100
    correctness_score: Mapped[float] = mapped_column(Float, nullable=False)
    safety_score: Mapped[float] = mapped_column(Float, nullable=False)
    efficiency_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Weights used (snapshot from lab version at time of grading)
    weight_correctness: Mapped[float] = mapped_column(Float, nullable=False)
    weight_safety: Mapped[float] = mapped_column(Float, nullable=False)
    weight_efficiency: Mapped[float] = mapped_column(Float, nullable=False)

    # Human-readable summary for portfolio cards
    summary: Mapped[str] = mapped_column(Text, nullable=True)

    # Full check results as JSON array
    check_results: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # [{
    #   "check_id": "service_active",
    #   "layer": "correctness",
    #   "description": "nginx.service is active",
    #   "passed": true,
    #   "weight": 0.2,
    #   "detail": "Active: active (running)"
    # }]

    graded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped["ChallengeRun"] = relationship("ChallengeRun", back_populates="scoring_result")


class ScoreBreakdown(Base):
    """Individual check result — kept separate for query/reporting."""
    __tablename__ = "score_breakdowns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scoring_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scoring_results.id"), nullable=False, index=True)
    check_id: Mapped[str] = mapped_column(String(128), nullable=False)
    layer: Mapped[str] = mapped_column(String(32), nullable=False)  # correctness / safety / efficiency
    description: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=True)
    points_earned: Mapped[float] = mapped_column(Float, nullable=False)
    points_possible: Mapped[float] = mapped_column(Float, nullable=False)


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon_url: Mapped[str] = mapped_column(String(512), nullable=True)
    # Criteria stored as JSON: {"type": "lab_pass", "lab_slug": "linux-service-outage", "min_score": 80}
    criteria: Mapped[dict] = mapped_column(JSON, nullable=False)


class UserBadge(Base):
    __tablename__ = "user_badges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    badge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("badges.id"), nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("challenge_runs.id"), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="badges")
    badge: Mapped["Badge"] = relationship("Badge")
