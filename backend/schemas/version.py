"""Pydantic schemas cho Version API (request / response)."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request ──────────────────────────────────────────────────────────
class VersionCreateRequest(BaseModel):
    """Payload khi lưu một phiên bản mới."""

    html_snapshot: str = Field(
        ..., min_length=1, description="Mã HTML đã render, bắt buộc không được rỗng"
    )
    json_content: Optional[dict[str, Any]] = Field(
        None, description="JSON nội dung cấu trúc Landing Page"
    )
    commit_sha: Optional[str] = Field(
        None, max_length=40, description="Git commit SHA khi deploy"
    )
    change_summary: Optional[str] = Field(
        None, max_length=255, description="Tóm tắt thay đổi"
    )


# ── Response ─────────────────────────────────────────────────────────
class VersionListItemResponse(BaseModel):
    """Một mục trong danh sách lịch sử phiên bản (payload rút gọn)."""

    id: int
    version_number: int
    change_summary: Optional[str] = None
    commit_sha: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VersionDetailResponse(VersionListItemResponse):
    """Chi tiết đầy đủ một phiên bản, bao gồm HTML và JSON."""

    project_id: int
    json_content: Optional[Any] = None
    html_snapshot: str


class VersionRestoreResponse(BaseModel):
    """Kết quả sau khi khôi phục phiên bản cũ."""

    message: str
    restored_from_version: int
    new_version: VersionListItemResponse
