"""SQLAlchemy model cho bảng project_versions.

Dùng khi project chuyển sang SQLAlchemy session (xem core/database.py).
Hiện tại API vẫn dùng PyMySQL trực tiếp trong api/versions.py.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

try:
    from core.database import Base
except ImportError:
    # Nếu chưa có database.py trên branch hiện tại, dùng stub
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):
        pass


class ProjectVersion(Base):
    """Một phiên bản snapshot của Landing Page trong dự án.

    Mỗi lần người dùng lưu, deploy, hoặc khôi phục đều tạo một bản ghi mới
    (Append-only). version_number tự tăng trong phạm vi từng project.
    """

    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_project_version"),
        Index("ix_project_versions_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    json_content: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    html_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    change_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
