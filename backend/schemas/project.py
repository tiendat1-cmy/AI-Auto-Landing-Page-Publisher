"""Pydantic Schemas cho API quản lý và cập nhật Landing Page Project.

Bao gồm:
  - ProjectUpdateRequest: Dữ liệu gửi lên khi cập nhật landing page (PUT /projects/{id})
  - ProjectResponse: Thông tin chi tiết của Project
  - ProjectUpdateResponse: Kết quả sau khi cập nhật thành công (render HTML, commit SHA, phiên bản mới)
  - ProjectPreviewResponse: Kết quả render xem trước (HTML) mà không ghi DB
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectUpdateRequest(BaseModel):
    """Payload gửi lên endpoint PUT /projects/{id}."""

    campaign_name: Optional[str] = Field(None, max_length=255, description="Tên chiến dịch")
    product_name: Optional[str] = Field(None, max_length=255, description="Tên sản phẩm")
    product_description: Optional[str] = Field(None, description="Mô tả chi tiết sản phẩm")
    price: Optional[float] = Field(None, ge=0, description="Giá sản phẩm (VND)")
    image_url: Optional[str] = Field(None, max_length=500, description="Link ảnh sản phẩm")
    color_theme: Optional[str] = Field(None, max_length=50, description="Mã màu chủ đạo (vd: #6366f1)")
    facebook_url: Optional[str] = Field(None, max_length=500, description="Link trang Facebook")
    tiktok_url: Optional[str] = Field(None, max_length=500, description="Link kênh TikTok")
    instagram_url: Optional[str] = Field(None, max_length=500, description="Link Instagram")
    repo_url: Optional[str] = Field(None, max_length=500, description="Repository GitHub của landing page")
    github_pages_url: Optional[str] = Field(None, max_length=500, description="URL GitHub Pages")
    raw_json_data: Optional[dict[str, Any]] = Field(None, description="Dữ liệu JSON mở rộng (headline, cta, features...)")
    change_summary: Optional[str] = Field(
        "Cập nhật landing page: text, giá, link social",
        max_length=255,
        description="Ghi chú tóm tắt thay đổi để lưu vào lịch sử phiên bản",
    )
    commit_message: Optional[str] = Field(
        None,
        max_length=255,
        description="Thông điệp commit gửi lên GitHub",
    )

    model_config = ConfigDict(extra="ignore")


class ProjectResponse(BaseModel):
    """Thông tin chi tiết một dự án landing page."""

    id: int
    user_id: int
    template_id: int
    campaign_name: str
    product_name: str
    product_description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    color_theme: Optional[str] = None
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    instagram_url: Optional[str] = None
    repo_url: Optional[str] = None
    github_pages_url: Optional[str] = None
    raw_json_data: Optional[dict[str, Any]] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectUpdateResponse(BaseModel):
    """Response trả về sau khi PUT /projects/{id} hoàn thành."""

    message: str
    project: ProjectResponse
    commit_sha: Optional[str] = Field(None, description="SHA commit vừa tạo trên GitHub")
    version_id: Optional[int] = Field(None, description="ID của bản ghi project_versions mới")
    version_number: Optional[int] = Field(None, description="Số thứ tự phiên bản mới vừa tạo")
    rendered_html: str = Field(..., description="Mã HTML landing page vừa được render và lưu")


class ProjectPreviewResponse(BaseModel):
    """Response trả về khi yêu cầu render xem trước HTML (không lưu DB)."""

    rendered_html: str
    campaign_name: str
    product_name: str
    price: Optional[float] = None
