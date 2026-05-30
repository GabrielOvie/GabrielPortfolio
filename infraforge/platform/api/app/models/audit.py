import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, INET
from app.db import Base


class AuditEvent(Base):
    """Immutable audit log. Never updated, only inserted."""
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Who
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    # What
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # e.g. user.login, lab.launch, run.completed, subscription.upgraded
    resource_type: Mapped[str] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=True)
    # Full event payload
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Network
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
