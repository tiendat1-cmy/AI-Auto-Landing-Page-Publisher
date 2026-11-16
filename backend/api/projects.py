"""API Router cho cập nhật và quản lý Landing Page Project.

Đáp ứng yêu cầu:
  PUT /projects/{id}: sửa text, giá, link social -> render lại HTML -> push commit mới lên GitHub -> lưu phiên bản mới.
  GET /projects/{id}: lấy dữ liệu cũ để điền vào form chỉnh sửa.
  POST /projects/{id}/preview: xem trước HTML trước khi lưu.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from schemas.project import (
    ProjectPreviewResponse,
    ProjectResponse,
    ProjectUpdateRequest,
    ProjectUpdateResponse,
)
from services.project_service import get_project, list_projects, update_landing_page
from services.template_service import render_landing_page

router = APIRouter(
    tags=["Projects & Landing Page"],
)


# ── GET /projects & /api/v1/projects: Danh sách dự án ───────────────
@router.get(
    "/api/v1/projects",
    response_model=list[ProjectResponse],
    summary="Lấy danh sách tất cả các dự án",
)
@router.get(
    "/projects",
    response_model=list[ProjectResponse],
    include_in_schema=False,
)
async def api_list_projects():
    """Trả về danh sách tất cả các dự án landing page."""
    return list_projects()


# ── GET /projects/{id} & /api/v1/projects/{id}: Chi tiết để điền sẵn Form
@router.get(
    "/api/v1/projects/{project_id}",
    response_model=ProjectResponse,
    summary="Lấy thông tin chi tiết dự án (điền sẵn vào form)",
)
@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    include_in_schema=False,
)
async def api_get_project(project_id: int):
    """Lấy dữ liệu dự án hiện tại để điền sẵn vào form chỉnh sửa (FE)."""
    try:
        return get_project(project_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ── POST /projects/{id}/preview & /api/v1/projects/{id}/preview: Xem trước
@router.post(
    "/api/v1/projects/{project_id}/preview",
    response_model=ProjectPreviewResponse,
    summary="Xem trước mã HTML đã render từ dữ liệu đang sửa (chưa lưu)",
)
@router.post(
    "/projects/{project_id}/preview",
    response_model=ProjectPreviewResponse,
    include_in_schema=False,
)
async def api_preview_landing_page(project_id: int, payload: ProjectUpdateRequest):
    """Render mã HTML tức thì từ các trường đang nhập mà không ghi DB hay push GitHub."""
    try:
        current = get_project(project_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # Gộp dữ liệu hiện tại với dữ liệu đang xem trước
    preview_data = dict(current)
    if payload.campaign_name is not None:
        preview_data["campaign_name"] = payload.campaign_name
    if payload.product_name is not None:
        preview_data["product_name"] = payload.product_name
    if payload.product_description is not None:
        preview_data["product_description"] = payload.product_description
    if payload.price is not None:
        preview_data["price"] = payload.price
    if payload.image_url is not None:
        preview_data["image_url"] = payload.image_url
    if payload.color_theme is not None:
        preview_data["color_theme"] = payload.color_theme
    if payload.facebook_url is not None:
        preview_data["facebook_url"] = payload.facebook_url
    if payload.tiktok_url is not None:
        preview_data["tiktok_url"] = payload.tiktok_url
    if payload.instagram_url is not None:
        preview_data["instagram_url"] = payload.instagram_url
    if payload.raw_json_data is not None:
        preview_data["raw_json_data"] = payload.raw_json_data

    html_code = render_landing_page(preview_data)

    return ProjectPreviewResponse(
        rendered_html=html_code,
        campaign_name=preview_data.get("campaign_name", ""),
        product_name=preview_data.get("product_name", ""),
        price=preview_data.get("price"),
    )


# ── PUT /projects/{id} & /api/v1/projects/{id}: Cập nhật Landing Page 
@router.put(
    "/api/v1/projects/{project_id}",
    response_model=ProjectUpdateResponse,
    summary="Cập nhật landing page: sửa text, giá, link social -> render lại HTML -> push GitHub -> lưu phiên bản",
)
@router.put(
    "/projects/{project_id}",
    response_model=ProjectUpdateResponse,
    include_in_schema=False,
)
async def api_update_landing_page(project_id: int, payload: ProjectUpdateRequest):
    """Thực hiện chu trình cập nhật landing page đầy đủ:

    1. Sửa text, giá, link social và thông tin liên quan trong DB.
    2. Render lại HTML đầy đủ.
    3. Push commit mới lên GitHub (tạo commit_sha).
    4. Lưu phiên bản mới vào bảng project_versions (Append-only).
    """
    try:
        result = update_landing_page(
            project_id=project_id,
            payload=payload,
            user_id=None,  # Có thể tích hợp auth sau khi merge nhánh login
        )
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi cập nhật landing page: {str(exc)}",
        )
