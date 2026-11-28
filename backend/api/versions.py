"""API Router cho quản lý phiên bản Landing Page.

Endpoints:
  POST   /api/v1/projects/{project_id}/versions                       – Lưu version mới (US-06)
  GET    /api/v1/projects/{project_id}/versions                       – Danh sách versions (US-07)
  GET    /api/v1/projects/{project_id}/versions/{version_id}          – Chi tiết version (US-07)
  POST   /api/v1/projects/{project_id}/versions/{version_id}/restore  – Khôi phục version (US-08)
"""

import pymysql
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, get_owned_project
from schemas.version import (
    VersionCreateRequest,
    VersionDetailResponse,
    VersionListItemResponse,
    VersionRestoreResponse,
)
from services.version_restore_service import restore_project_version
from services.version_service import (
    create_version,
    get_version_detail,
    list_versions,
)

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Project Versions"],
)


# ── US-06: Lưu phiên bản mới ────────────────────────────────────────
@router.post(
    "/{project_id}/versions",
    status_code=status.HTTP_201_CREATED,
    response_model=VersionDetailResponse,
    summary="Lưu phiên bản mới cho dự án",
)
async def api_create_version(
    project_id: int,
    payload: VersionCreateRequest,
    project: dict = Depends(get_owned_project),
    current_user: dict = Depends(get_current_user),
):
    """Tạo một snapshot phiên bản mới (version_number tự tăng).

    - **AC1**: Lưu thành công, trả về version vừa tạo.
    - **AC2**: Trả 422 nếu thiếu hoặc rỗng `html_snapshot`.
    - **AC3**: Transaction nguyên tử – rollback toàn bộ nếu có lỗi.
    - **AC4**: Trả 409 nếu trùng (project_id, version_number).
    """
    try:
        version = create_version(
            project_id=project["id"],
            html_snapshot=payload.html_snapshot,
            json_content=payload.json_content,
            commit_sha=payload.commit_sha,
            change_summary=payload.change_summary,
            created_by=current_user.get("id"),
        )
        return version

    except ValueError as exc:
        # Project không tồn tại hoặc html_snapshot rỗng
        if "không tồn tại" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    except pymysql.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trùng lặp version_number. Vui lòng thử lại.",
        )


# ── US-07: Danh sách phiên bản ──────────────────────────────────────
@router.get(
    "/{project_id}/versions",
    response_model=list[VersionListItemResponse],
    summary="Xem danh sách phiên bản (sắp xếp mới nhất trước)",
)
async def api_list_versions(
    project_id: int,
    project: dict = Depends(get_owned_project),
):
    """Trả về danh sách version giảm dần theo version_number.

    Payload rút gọn – không tải html_snapshot để tối ưu dung lượng.

    - **AC1**: Danh sách sắp xếp giảm dần.
    """
    try:
        versions = list_versions(project["id"])
        return versions
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ── US-07: Chi tiết một phiên bản ───────────────────────────────────
@router.get(
    "/{project_id}/versions/{version_id}",
    response_model=VersionDetailResponse,
    summary="Xem chi tiết một phiên bản (bao gồm HTML & JSON)",
)
async def api_get_version(
    project_id: int,
    version_id: int,
    project: dict = Depends(get_owned_project),
):
    """Trả về đầy đủ thông tin version (HTML + JSON).

    - **AC2**: Trả về chi tiết version.
    - **AC3**: Trả 404 nếu version không thuộc project.
    """
    version = get_version_detail(project["id"], version_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} không tồn tại hoặc không thuộc project {project_id}",
        )
    return version


# ── US-08: Khôi phục phiên bản cũ ───────────────────────────────────
@router.post(
    "/{project_id}/versions/{version_id}/restore",
    status_code=status.HTTP_201_CREATED,
    response_model=VersionRestoreResponse,
    summary="Khôi phục phiên bản cũ (Append-only)",
)
async def api_restore_version(
    project_id: int,
    version_id: int,
    project: dict = Depends(get_owned_project),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Khôi phục phiên bản cũ lên dự án hiện tại và website GitHub Pages.

    Luồng xử lý:

    1. Đọc snapshot ``json_content`` của version cũ.
    2. Áp dụng lại các cột nội dung vào bảng ``projects``.
    3. Render lại HTML từ dữ liệu vừa khôi phục.
    4. Push commit mới lên GitHub (nếu dự án đã có ``repo_url``).
    5. Tạo version mới (Append-only), giữ nguyên toàn bộ lịch sử cũ.

    - **AC1**: Giữ nguyên lịch sử cũ.
    - **AC2**: Tạo version mới với commit SHA mới (nếu push thành công).
    - **AC3**: Trả về ``warnings`` nếu không thể cập nhật GitHub/website.
    """
    try:
        result = restore_project_version(
            db=db,
            project=project,
            version_id=version_id,
            created_by=current_user.get("id"),
        )
        new_version = result["new_version"]
        action = (
            "Đã khôi phục nội dung"
            if result.get("applied_to_project")
            else "Đã tạo phiên bản khôi phục"
        )
        return VersionRestoreResponse(
            message=(
                f"{action} từ phiên bản {result['restored_from_version']}, "
                f"tạo phiên bản v{new_version['version_number']}."
            ),
            restored_from_version=result["restored_from_version"],
            new_version=VersionListItemResponse.model_validate(new_version),
            commit_sha=result.get("commit_sha"),
            github_pages_url=result.get("github_pages_url"),
            warnings=result.get("warnings") or [],
            restored_fields=result.get("restored_fields") or [],
            applied_to_project=bool(result.get("applied_to_project")),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    except pymysql.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trùng lặp version_number khi khôi phục. Vui lòng thử lại.",
        )
