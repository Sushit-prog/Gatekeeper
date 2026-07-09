"""SQLAlchemy models for dashboard-specific tables."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class DashboardBase(DeclarativeBase):
    pass


class HumanReview(DashboardBase):
    __tablename__ = "human_reviews"

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    audit_id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), index=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    marked_fp: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
