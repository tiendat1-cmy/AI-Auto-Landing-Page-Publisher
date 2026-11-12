"""API Router cho quản lý phiên bản Landing Page.

Endpoints:
  POST   /api/v1/projects/{project_id}/versions                       – Lưu version mới (US-06)
  GET    /api/v1/projects/{project_id}/versions                       – Danh sách versions (US-07)
  GET    /api/v1/projects/{project_id}/versions/{version_id}          – Chi tiết version (US-07)
  POST   /api/v1/projects/{project_id}/versions/{version_id}/restore  – Khôi phục version (US-08)
"""

import pymysql
from fastapi import APIRouter, HTTPException, status

from schemas.version import (
    VersionCreateRequest,
    VersionDetailResponse,
    VersionListItemResponse,
    VersionRestoreResponse,
)
from services.version_service import (
    create_version,
    get_version_detail,
    list_versions,
    restore_version,
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
async def api_create_version(project_id: int, payload: VersionCreateRequest):
    """Tạo một snapshot phiên bản mới (version_number tự tăng).

    - **AC1**: Lưu thành công, trả về version vừa tạo.
    - **AC2**: Trả 422 nếu thiếu hoặc rỗng `html_snapshot`.
    - **AC3**: Transaction nguyên tử – rollback toàn bộ nếu có lỗi.
    - **AC4**: Trả 409 nếu trùng (project_id, version_number).
    """
    try:
        version = create_version(
            project_id=project_id,
            html_snapshot=payload.html_snapshot,
            json_content=payload.json_content,
            commit_sha=payload.commit_sha,
            change_summary=payload.change_summary,
            created_by=None,  # TODO: lấy từ get_current_user khi merge nhánh auth
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
async def api_list_versions(project_id: int):
    """Trả về danh sách version giảm dần theo version_number.

    Payload rút gọn – không tải html_snapshot để tối ưu dung lượng.

    - **AC1**: Danh sách sắp xếp giảm dần.
    """
    try:
        versions = list_versions(project_id)
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
async def api_get_version(project_id: int, version_id: int):
    """Trả về đầy đủ thông tin version (HTML + JSON).

    - **AC2**: Trả về chi tiết version.
    - **AC3**: Trả 404 nếu version không thuộc project.
    """
    version = get_version_detail(project_id, version_id)
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
async def api_restore_version(project_id: int, version_id: int):
    """Khôi phục phiên bản cũ bằng cách tạo version mới copy snapshot.

    Lịch sử cũ được giữ nguyên (Append-only). Version mới ghi rõ
    ``change_summary = "Khôi phục từ phiên bản X"``.

    - **AC1**: Giữ nguyên lịch sử cũ.
    - **AC2**: Tạo version mới sao chép nội dung.
    """
    try:
        old_version = get_version_detail(project_id, version_id)
        if old_version is None:
            raise ValueError(
                f"Version {version_id} không tồn tại hoặc không thuộc project {project_id}"
            )

        old_ver_num = old_version["version_number"]

        new_version = restore_version(
            project_id=project_id,
            version_id=version_id,
            created_by=None,  # TODO: lấy từ get_current_user khi merge nhánh auth
        )
        return VersionRestoreResponse(
            message=f"Đã khôi phục thành công từ phiên bản {old_ver_num}",
            restored_from_version=old_ver_num,
            new_version=VersionListItemResponse(**{
                "id": new_version["id"],
                "version_number": new_version["version_number"],
                "change_summary": new_version.get("change_summary"),
                "commit_sha": new_version.get("commit_sha"),
                "created_by": new_version.get("created_by"),
                "created_at": new_version["created_at"],
            }),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
