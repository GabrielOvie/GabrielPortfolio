import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Enum, DateTime, Integer, Float, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base


class RunStatus(str, enum.Enum):
    queued = "queued"
    provisioning = "provisioning"
    running = "running"
    grading = "grading"
    completed = "completed"
    failed = "failed"
    timeout = "timeout"
    cancelled = "cancelled"


class ChallengeRun(Base):
    __tablename__ = "challenge_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    lab_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("labs.id"), nullable=False, index=True)
    lab_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lab_versions.id"), nullable=False)

    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.queued, nullable=False, index=True)

    # Orchestrator-side identifiers
    orchestrator_run_id: Mapped[str] = mapped_column(String(128), nullable=True, index=True)
    # SSH/access credentials injected into the run (encrypted at rest)
    access_credentials: Mapped[dict] = mapped_column(JSON, nullable=True)
    # e.g. {"ssh_host": "...", "ssh_port": 2222, "ssh_user": "...", "ssh_password": "..."}

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    timeout_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)

    # User activity
    command_count: Mapped[int] = mapped_column(Integer, default=0)
    restart_count: Mapped[int] = mapped_column(Integer, default=0)

    # Outcome
    final_score: Mapped[float] = mapped_column(Float, nullable=True)
    passed: Mapped[bool] = mapped_column(nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=True)

    # Artifact storage
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="runs")
    lab: Mapped["Lab"] = relationship("Lab", back_populates="runs")
    lab_version: Mapped["LabVersion"] = relationship("LabVersion", back_populates="runs")
    scoring_result: Mapped["ScoringResult"] = relationship("ScoringResult", back_populates="run", uselist=False)
    portfolio_item: Mapped["PortfolioItem"] = relationship("PortfolioItem", back_populates="run", uselist=False)
