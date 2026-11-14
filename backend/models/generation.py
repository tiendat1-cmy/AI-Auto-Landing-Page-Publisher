from datetime import datetime, timezone
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from core.database import Base

STATUS_PENDING = "pending"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
GENERATION_STATUSES = (STATUS_PENDING, STATUS_SUCCESS, STATUS_FAILED)


def utc_now() -> datetime:
    """Datetime UTC không kèm tzinfo, vì cột DATETIME của MySQL không lưu timezone."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Generation(Base):
    """Một lần yêu cầu Gemini sinh nội dung cho một project."""

    __tablename__ = "generations"
    __table_args__ = (
        Index("ix_generations_project_id", "project_id"),
        CheckConstraint(
            "status IN ('pending', 'success', 'failed')",
            name="chk_generations_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        server_default=text("(UTC_TIMESTAMP())"),
    )

    project: Mapped["Project"] = relationship("Project", back_populates="generations")
