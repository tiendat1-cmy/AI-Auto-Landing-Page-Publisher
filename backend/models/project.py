from typing import Any

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Project(Base):
    """Project hiện tại. Chỉ map các cột task này sở hữu.

    Bảng projects có thể đã có thêm cột khác. Những cột đó không bị
    model này ghi đè. raw_json_data là JSON landing page đang dùng.
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    raw_json_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    generations: Mapped[list["Generation"]] = relationship(
        "Generation",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
