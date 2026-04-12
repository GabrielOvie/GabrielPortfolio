import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Enum, Boolean, DateTime, Integer, Float, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.db import Base


class LabDifficulty(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"
    expert = "expert"


class LabCategory(str, enum.Enum):
    linux = "linux"
    networking = "networking"
    cloud_aws = "cloud_aws"
    cloud_gcp = "cloud_gcp"
    cloud_azure = "cloud_azure"
    containers = "containers"
    kubernetes = "kubernetes"
    iac = "iac"
    security = "security"
    observability = "observability"


class LabExecutionModel(str, enum.Enum):
    container = "container"
    vm = "vm"
    hybrid = "hybrid"


class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[LabCategory] = mapped_column(Enum(LabCategory), nullable=False)
    difficulty: Mapped[LabDifficulty] = mapped_column(Enum(LabDifficulty), nullable=False)
    execution_model: Mapped[LabExecutionModel] = mapped_column(Enum(LabExecutionModel), default=LabExecutionModel.container, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    max_runtime_minutes: Mapped[int] = mapped_column(Integer, default=90, nullable=False)

    # Scoring weights
    weight_correctness: Mapped[float] = mapped_column(Float, default=0.60)
    weight_safety: Mapped[float] = mapped_column(Float, default=0.25)
    weight_efficiency: Mapped[float] = mapped_column(Float, default=0.15)

    # Paywall
    is_free: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Stats (denormalised for perf)
    total_runs: Mapped[int] = mapped_column(Integer, default=0)
    avg_completion_minutes: Mapped[float] = mapped_column(Float, nullable=True)
    avg_score: Mapped[float] = mapped_column(Float, nullable=True)
    pass_rate: Mapped[float] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions: Mapped[list["LabVersion"]] = relationship("LabVersion", back_populates="lab", order_by="LabVersion.version_number.desc()")
    runs: Mapped[list["ChallengeRun"]] = relationship("ChallengeRun", back_populates="lab")

    @property
    def active_version(self) -> "LabVersion | None":
        return next((v for v in self.versions if v.is_active), None)


class LabVersion(Base):
    """Immutable snapshot of a lab at a point in time.
    Runs always reference a specific version so scoring is stable."""
    __tablename__ = "lab_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lab_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Template reference — matches a directory in lab-runtime/templates/
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # Orchestrator image tag for the lab environment
    image_tag: Mapped[str] = mapped_column(String(256), nullable=False)
    # Full grading spec as JSON (embedded from grading.yaml at publish time)
    grading_spec: Mapped[dict] = mapped_column(JSON, nullable=False)
    # What users see as the goal/scenario
    scenario_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    change_notes: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lab: Mapped["Lab"] = relationship("Lab", back_populates="versions")
    runs: Mapped[list["ChallengeRun"]] = relationship("ChallengeRun", back_populates="lab_version")
