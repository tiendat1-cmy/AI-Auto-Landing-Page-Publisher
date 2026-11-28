import json
import logging
import re
import unicodedata
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, get_owned_project
from models import STATUS_SUCCESS
from schemas.project import ProjectCreate, ProjectUpdate
from services import github_service, template_service
from services.generation_service import ProjectNotFoundError, generate_content_for_project
from services.github_service import (
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubRepoDuplicateError,
    create_github_repo,
    enable_github_pages,
    get_github_pages_build_status,
    push_landing_page_assets,
    wait_for_github_pages_built,
)
from services.version_service import create_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])

DEFAULT_CHANGE_SUMMARY = "Cập nhật landing page: text, giá, link social"


def _error_detail(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message, "details": []}}


def _slugify_vietnamese(value: str) -> str:
    """Chuyển chuỗi tiếng Việt có dấu thành slug không dấu chuẩn tên repo GitHub."""
    text_val = (value or "").replace("đ", "d").replace("Đ", "D")
    text_val = unicodedata.normalize("NFKD", text_val).encode("ascii", "ignore").decode("ascii")
    text_val = re.sub(r"[^a-zA-Z0-9]+", "-", text_val.lower()).strip("-")
    return text_val or "landing-page"


# ── Helpers ──────────────────────────────────────────────────────────
def _json_safe(value: Any) -> Any:
    """Chuyển Decimal/datetime/bytes sang kiểu JSON-serializable."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _parse_raw_json(value: Any) -> Any:
    """raw_json_data có thể là dict hoặc chuỗi JSON tuỳ driver."""
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _serialize_project(row: Any) -> dict:
    project = _json_safe(dict(row))
    project["raw_json_data"] = _json_safe(_parse_raw_json(project.get("raw_json_data")))
    return project


def _split_payload(payload: ProjectUpdate) -> tuple[dict, str, str | None]:
    """Tách payload thành (dữ liệu cập nhật DB, change_summary, commit_message)."""
    update_data = payload.model_dump(exclude_unset=True)
    change_summary = (update_data.pop("change_summary", None) or DEFAULT_CHANGE_SUMMARY).strip()
    commit_message = update_data.pop("commit_message", None)

    if "raw_json_data" in update_data and update_data["raw_json_data"] is not None:
        raw_value = update_data["raw_json_data"]
        update_data["raw_json_data"] = (
            raw_value if isinstance(raw_value, str) else json.dumps(raw_value, ensure_ascii=False)
        )

    return update_data, change_summary, commit_message


def _fetch_project(db: Session, project_id: int) -> Any:
    row = (
        db.execute(text("SELECT * FROM projects WHERE id = :id"), {"id": project_id})
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Landing page không tồn tại.")
    return row


# ── Endpoints ────────────────────────────────────────────────────────
@router.get("")
async def list_my_projects(
    page: int = 1,
    page_size: int = 10,
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Danh sach project cua nguoi dang nhap, phan trang + loc status."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1
    elif page_size > 100:
        page_size = 100

    offset = (page - 1) * page_size

    where = "user_id = :user_id AND deleted_at IS NULL"
    params: dict = {"user_id": current_user["id"]}

    if status_filter:
        where += " AND status = :status"
        params["status"] = status_filter

    count_row = db.execute(
        text(f"SELECT COUNT(*) AS cnt FROM projects WHERE {where}"),
        params,
    ).mappings().first()
    total = int(count_row["cnt"]) if count_row else 0

    rows = (
        db.execute(
            text(
                f"SELECT * FROM projects WHERE {where} "
                "ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": offset},
        )
        .mappings()
        .all()
    )

    return {
        "success": True,
        "data": {
            "items": [_serialize_project(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/stats")
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Thống kê tổng quan cho Dashboard (chỉ tính dữ liệu của người dùng hiện tại)."""
    user_params = {"user_id": current_user["id"]}

    project_row = (
        db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END), 0) AS drafts,
                    COALESCE(SUM(CASE WHEN status = 'deploying' THEN 1 ELSE 0 END), 0) AS deploying,
                    COALESCE(SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END), 0) AS published,
                    COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS failed
                FROM projects
                WHERE user_id = :user_id AND deleted_at IS NULL
                """
            ),
            user_params,
        )
        .mappings()
        .first()
    )

    generation_row = (
        db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(CASE WHEN g.status = 'success' THEN 1 ELSE 0 END), 0) AS successful
                FROM generations g
                JOIN projects p ON p.id = g.project_id
                WHERE p.user_id = :user_id AND p.deleted_at IS NULL
                """
            ),
            user_params,
        )
        .mappings()
        .first()
    )

    deployment_row = (
        db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(CASE WHEN d.status = 'Success' THEN 1 ELSE 0 END), 0) AS successful,
                    COALESCE(SUM(CASE WHEN d.status = 'Failed' THEN 1 ELSE 0 END), 0) AS failed
                FROM deployments d
                JOIN projects p ON p.id = d.project_id
                WHERE p.user_id = :user_id AND p.deleted_at IS NULL
                """
            ),
            user_params,
        )
        .mappings()
        .first()
    )

    template_row = db.execute(text("SELECT COUNT(*) AS total FROM templates")).mappings().first()

    recent_rows = (
        db.execute(
            text(
                """
                SELECT id, campaign_name, product_name, status, github_pages_url,
                       color_theme, created_at, updated_at
                FROM projects
                WHERE user_id = :user_id AND deleted_at IS NULL
                ORDER BY updated_at DESC
                LIMIT 5
                """
            ),
            user_params,
        )
        .mappings()
        .all()
    )

    def _int(row, key: str) -> int:
        return int(row[key] or 0) if row else 0

    return {
        "success": True,
        "data": {
            "total_projects": _int(project_row, "total"),
            "draft_projects": _int(project_row, "drafts"),
            "deploying_projects": _int(project_row, "deploying"),
            "published_projects": _int(project_row, "published"),
            "failed_projects": _int(project_row, "failed"),
            "total_generations": _int(generation_row, "total"),
            "successful_generations": _int(generation_row, "successful"),
            "total_deployments": _int(deployment_row, "total"),
            "successful_deployments": _int(deployment_row, "successful"),
            "failed_deployments": _int(deployment_row, "failed"),
            "total_templates": _int(template_row, "total"),
            "recent_projects": [_json_safe(dict(row)) for row in recent_rows],
        },
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = db.execute(
        text("SELECT id FROM templates WHERE id = :id"), {"id": payload.template_id}
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template khong ton tai")

    result = db.execute(
        text(
            """
            INSERT INTO projects
            (user_id, template_id, campaign_name, product_name, product_description,
             price, image_url, color_theme, messenger_link, tiktok_shop_link, zalo_link, instagram_link, hotline,
             facebook_url, tiktok_url, instagram_url, status)
            VALUES
            (:user_id, :template_id, :campaign_name, :product_name, :product_description,
             :price, :image_url, :color_theme, :messenger_link, :tiktok_shop_link, :zalo_link, :instagram_link, :hotline,
             :facebook_url, :tiktok_url, :instagram_url, 'draft')
            """
        ),
        {**payload.model_dump(), "user_id": current_user["id"]},
    )
    db.commit()

    row = (
        db.execute(text("SELECT * FROM projects WHERE id = :id"), {"id": result.lastrowid})
        .mappings()
        .one()
    )
    return {"success": True, "data": _serialize_project(row)}


@router.get("/{project_id}")
async def get_project_detail(
    project: dict = Depends(get_owned_project),
):
    """Chi tiet project. Tra 404 neu khong ton tai, da xoa mem HOAC thuoc nguoi khac."""
    return {"success": True, "data": _serialize_project(project)}


@router.post("/{project_id}/generate", status_code=status.HTTP_201_CREATED)
def generate_project_content(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """Sinh nội dung landing page bằng Gemini API và lưu kết quả JSON vào Database."""
    try:
        generation = generate_content_for_project(db=db, project_id=project["id"])
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail("PROJECT_NOT_FOUND", "Landing page không tồn tại."),
        )
    except Exception:
        logger.exception("Lỗi khi sinh/lưu nội dung cho project %s", project["id"])
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_error_detail("DATABASE_ERROR", "Lỗi hệ thống khi lưu dữ liệu sinh nội dung."),
        )

    if generation.status != STATUS_SUCCESS or generation.response_json is None:
        error_code = getattr(generation, "_error_code", None) or "GEMINI_ERROR"
        status_map = {
            "GEMINI_QUOTA_EXCEEDED": status.HTTP_429_TOO_MANY_REQUESTS,
            "GEMINI_TIMEOUT": status.HTTP_504_GATEWAY_TIMEOUT,
            "GEMINI_CONFIG_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
            "GEMINI_INVALID_RESPONSE": status.HTTP_502_BAD_GATEWAY,
        }
        http_status = status_map.get(error_code, status.HTTP_502_BAD_GATEWAY)
        friendly_message = (
            generation.error_message
            or "Không thể tạo nội dung lúc này. Vui lòng thử lại sau."
        )
        raise HTTPException(
            status_code=http_status,
            detail=_error_detail(error_code, friendly_message),
        )

    refreshed_row = _fetch_project(db, project["id"])
    project_dict = _serialize_project(refreshed_row)
    rendered_html = template_service.render_landing_page(project_dict)

    return {
        "success": True,
        "rendered_html": rendered_html,
        "data": {
            "id": generation.id,
            "project_id": generation.project_id,
            "status": generation.status,
            "raw_json_data": generation.response_json,
            "response_json": generation.response_json,
            "rendered_html": rendered_html,
            "created_at": generation.created_at.isoformat() if generation.created_at else None,
        },
    }


@router.post("/{project_id}/preview")
async def preview_project(
    payload: ProjectUpdate,
    project: dict = Depends(get_owned_project),
):
    """Render xem trước HTML với dữ liệu đang chỉnh sửa, KHÔNG lưu vào database."""
    update_data, _, _ = _split_payload(payload)
    merged = {**project, **update_data}
    merged["raw_json_data"] = _parse_raw_json(merged.get("raw_json_data"))

    rendered_html = template_service.render_landing_page(merged)

    return {
        "success": True,
        "rendered_html": rendered_html,
        "product_name": merged.get("product_name") or "",
        "price": _json_safe(merged.get("price")),
    }


@router.put("/{project_id}")
@router.patch("/{project_id}")
async def update_project(
    payload: ProjectUpdate,
    project: dict = Depends(get_owned_project),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """[BE] API cập nhật landing page.

    1. Cập nhật text / giá / link social / màu sắc / ảnh vào bảng ``projects``.
    2. Render lại toàn bộ HTML qua ``template_service.render_landing_page``.
    3. Push commit mới lên GitHub (fallback SHA mô phỏng khi offline).
    4. Lưu snapshot Append-only vào ``project_versions`` (version_number tự tăng).
    """
    update_data, change_summary, commit_message = _split_payload(payload)

    if not update_data:
        logger.info("Payload rỗng cho project %s, chỉ render lại HTML", project["id"])

    if "template_id" in update_data and update_data["template_id"] is not None:
        template = db.execute(
            text("SELECT id FROM templates WHERE id = :id"),
            {"id": update_data["template_id"]},
        ).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template khong ton tai")

    if update_data:
        set_clauses = ", ".join(f"{col} = :{col}" for col in update_data.keys())
        db.execute(
            text(
                f"UPDATE projects SET {set_clauses}, updated_at = NOW() WHERE id = :id"
            ),
            {**update_data, "id": project["id"]},
        )
        db.commit()

    row = _fetch_project(db, project["id"])
    project_dict = _serialize_project(row)

    rendered_html = template_service.render_landing_page(project_dict)

    warnings: list[str] = []
    repo_url = project_dict.get("repo_url")

    commit_sha = None
    try:
        commit_sha = github_service.push_landing_page_commit(
            repo_url=repo_url,
            html_content=rendered_html,
            commit_message=commit_message
            or f"Cập nhật landing page: {project_dict.get('campaign_name') or project_dict.get('product_name')}",
            file_path="index.html",
        )
    except Exception as exc:  # pragma: no cover - lỗi mạng/hạ tầng
        logger.exception("Push GitHub thất bại cho project %s", project["id"])
        warnings.append(f"Không push được commit GitHub: {exc}")

    version: dict | None = None
    try:
        version = create_version(
            project_id=project_dict["id"],
            html_snapshot=rendered_html,
            json_content=_json_safe(project_dict),
            commit_sha=commit_sha,
            change_summary=change_summary,
            created_by=current_user.get("id") if current_user else None,
        )
    except Exception as exc:  # pragma: no cover - lỗi DB phiên bản
        logger.exception("Không lưu được version cho project %s", project["id"])
        warnings.append(f"Không lưu được phiên bản mới: {exc}")

    version_number = version.get("version_number") if version else None
    version_id = version.get("id") if version else None

    if version_number is not None:
        message = f"Cập nhật landing page thành công! Đã tạo phiên bản v{version_number}."
    else:
        message = "Cập nhật landing page thành công!"

    return {
        "success": True,
        "message": message,
        "data": project_dict,
        "project": project_dict,
        "commit_sha": commit_sha,
        "version_id": version_id,
        "version_number": version_number,
        "rendered_html": rendered_html,
        "github_pages_url": project_dict.get("github_pages_url"),
        "repo_url": repo_url,
        "warnings": warnings,
    }


@router.delete("/{project_id}")
async def delete_project(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """[BE] API xóa landing page.

    - Chỉ chủ sở hữu mới được xóa (đã chặn bởi ``get_owned_project``).
    - Gọi GitHub API xóa repository tương ứng nếu project có ``repo_url``.
    - Xóa mềm trong DB bằng cách set ``deleted_at`` + ``status = 'deleted'``
      để bảo toàn lịch sử phiên bản và dữ liệu liên quan.
    """
    warnings: list[str] = []
    repo_url = (project.get("repo_url") or "").strip()
    github_status = "skipped"
    github_deleted = False

    if repo_url:
        try:
            result = github_service.delete_github_repo(repo_url)
            github_status = result.get("status") or "skipped"
            github_deleted = bool(result.get("deleted"))
            if github_status == "not_found":
                warnings.append(result.get("reason") or "GitHub repository đã không còn tồn tại.")
            elif github_status == "skipped":
                warnings.append(result.get("reason") or "Bỏ qua bước xóa GitHub repository.")
        except Exception as exc:  # pragma: no cover - lỗi mạng/hạ tầng/token
            logger.exception("Xóa GitHub repo thất bại cho project %s", project["id"])
            github_status = "failed"
            warnings.append(f"Không xóa được GitHub repository: {exc}")
    else:
        warnings.append("Dự án chưa có repo_url nên bỏ qua bước xóa GitHub repository.")

    db.execute(
        text(
            """
            UPDATE projects
            SET deleted_at = NOW(), status = 'deleted', updated_at = NOW()
            WHERE id = :id AND deleted_at IS NULL
            """
        ),
        {"id": project["id"]},
    )
    db.commit()

    return {
        "success": True,
        "message": "Đã xóa landing page thành công.",
        "data": {
            "project_id": project["id"],
            "deleted": True,
            "github_repo_deleted": github_deleted,
            "github_status": github_status,
        },
        "warnings": warnings,
    }


def _render_project_html(db: Session, project: dict) -> str:
    """Render nội dung index.html đầy đủ giao diện Tailwind từ snapshot hoặc template_service."""
    latest_version = db.execute(
        text(
            "SELECT html_snapshot FROM project_versions "
            "WHERE project_id = :pid ORDER BY version_number DESC LIMIT 1"
        ),
        {"pid": project["id"]},
    ).first()
    if latest_version and latest_version[0]:
        return latest_version[0]

    project_dict = _serialize_project(project)
    return template_service.render_landing_page(project_dict)


MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
IMAGE_CHUNK_SIZE = 64 * 1024  # 64 KB


@router.post("/{project_id}/image")
async def upload_project_image(
    file: UploadFile = File(...),
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """
    POST /projects/{id}/image
    Upload ảnh sản phẩm cho landing page (multipart/form-data, trường 'file').
    Giới hạn 5 MB, chỉ chấp nhận JPG, PNG, WebP.
    """
    content_type = (file.content_type or "").split(";")[0].lower().strip()
    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Định dạng file không được hỗ trợ. Chỉ chấp nhận JPG, PNG, WebP.",
        )

    first_chunk = await file.read(IMAGE_CHUNK_SIZE)
    if not first_chunk:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File rỗng. Vui lòng chọn file ảnh hợp lệ.",
        )

    detected_ext = None
    if first_chunk.startswith(b"\xff\xd8\xff"):
        detected_ext = ".jpg"
    elif first_chunk.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_ext = ".png"
    elif (
        len(first_chunk) >= 12
        and first_chunk[:4] == b"RIFF"
        and first_chunk[8:12] == b"WEBP"
    ):
        detected_ext = ".webp"

    expected_ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    if not detected_ext or detected_ext != expected_ext_map.get(content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Nội dung file không đúng định dạng ảnh hoặc không khớp với content-type.",
        )

    uploads_dir = Path(__file__).resolve().parent.parent / "static" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{detected_ext}"
    file_path = uploads_dir / filename
    total_size = len(first_chunk)

    try:
        with open(file_path, "wb") as f:
            f.write(first_chunk)
            while True:
                chunk = await file.read(IMAGE_CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_IMAGE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Kích thước file vượt quá giới hạn 5 MB.",
                    )
                f.write(chunk)
    except HTTPException:
        if file_path.is_file():
            try:
                file_path.unlink()
            except OSError:
                pass
        raise
    except Exception as exc:
        if file_path.is_file():
            try:
                file_path.unlink()
            except OSError:
                pass
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu file ảnh: {exc}")
    finally:
        await file.close()

    new_image_url = f"/static/uploads/{filename}"
    db.execute(
        text(
            """
            UPDATE projects
            SET image_url = :image_url, updated_at = NOW()
            WHERE id = :id
            """
        ),
        {"image_url": new_image_url, "id": project["id"]},
    )
    db.commit()

    old_image_url = project.get("image_url") or ""
    if isinstance(old_image_url, str) and old_image_url.startswith("/static/uploads/"):
        old_filename = Path(old_image_url).name
        if old_filename and old_filename != filename:
            old_file_path = uploads_dir / old_filename
            if old_file_path.is_file():
                try:
                    old_file_path.unlink()
                except OSError:
                    pass

    return {
        "success": True,
        "data": {
            "image_url": new_image_url,
            "size": total_size,
        },
    }


@router.post("/{project_id}/deploy")
def deploy_project(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """
    POST /projects/{id}/deploy
    Luồng xuất bản: render -> tạo repo (nếu chưa có) -> push -> bật Pages -> đợi build xong -> ghi log deployments.
    """
    now = datetime.utcnow()
    insert_res = db.execute(
        text(
            """
            INSERT INTO deployments (project_id, commit_sha, status, start_time)
            VALUES (:project_id, :commit_sha, :status, :start_time)
            """
        ),
        {
            "project_id": project["id"],
            "commit_sha": "pending",
            "status": "Rendering",
            "start_time": now,
        },
    )
    db.commit()
    deployment_id = insert_res.lastrowid

    db.execute(
        text("UPDATE projects SET status = 'deploying' WHERE id = :id"),
        {"id": project["id"]},
    )
    db.commit()

    try:
        html_content = _render_project_html(db, project)

        db.execute(
            text("UPDATE deployments SET status = :status WHERE id = :id"),
            {"status": "Creating Repo", "id": deployment_id},
        )
        db.commit()

        repo_url = project.get("repo_url")
        repo_info_parsed = github_service.parse_repo_info(repo_url) if repo_url else None
        if repo_info_parsed:
            owner, repo_name = repo_info_parsed
        else:
            raw_title = project.get("campaign_name") or project.get("product_name") or ""
            slug = _slugify_vietnamese(raw_title)
            repo_name = f"lp-{project['id']}-{slug}"[:60].rstrip("-") or f"landing-page-{project['id']}"
            repo_info = create_github_repo(repo_name=repo_name)
            owner = repo_info["full_name"].split("/")[0]
            repo_url = repo_info["html_url"]

            db.execute(
                text("UPDATE projects SET repo_url = :repo_url WHERE id = :id"),
                {"repo_url": repo_url, "id": project["id"]},
            )
            db.commit()

        db.execute(
            text("UPDATE deployments SET status = :status WHERE id = :id"),
            {"status": "Pushing Code", "id": deployment_id},
        )
        db.commit()

        # Đóng gói ảnh upload nội bộ (nếu có) để hiển thị được trên GitHub Pages
        deploy_images: list[dict] = []
        image_url = project.get("image_url") or ""
        if isinstance(image_url, str) and "/static/uploads/" in image_url:
            upload_filename = Path(image_url.split("?", 1)[0]).name
            local_img_path = Path(__file__).resolve().parent.parent / "static" / "uploads" / upload_filename
            if upload_filename and local_img_path.is_file():
                deploy_images.append({
                    "path": f"images/{upload_filename}",
                    "content": local_img_path.read_bytes(),
                })
                html_content = re.sub(
                    rf"(?:https?://[^/\"']+)?/static/uploads/{re.escape(upload_filename)}",
                    f"images/{upload_filename}",
                    html_content,
                )

        push_result = push_landing_page_assets(
            owner=owner,
            repo_name=repo_name,
            html_content=html_content,
            images=deploy_images or None,
        )
        commit_sha = push_result.get("commit_sha") or "latest"

        db.execute(
            text("UPDATE deployments SET status = :status, commit_sha = :sha WHERE id = :id"),
            {"status": "Enabling Pages", "sha": commit_sha, "id": deployment_id},
        )
        db.commit()

        enable_github_pages(owner=owner, repo_name=repo_name)

        # Đồng bộ trạng thái build GitHub Pages: chỉ đánh dấu Success khi đã build xong
        db.execute(
            text("UPDATE deployments SET status = :status WHERE id = :id"),
            {"status": "Building", "id": deployment_id},
        )
        db.commit()

        build_info = wait_for_github_pages_built(owner=owner, repo_name=repo_name)
        github_pages_url = build_info.get("html_url") or f"https://{owner.lower()}.github.io/{repo_name}/"

        end_time = datetime.utcnow()
        db.execute(
            text(
                """
                UPDATE deployments
                SET status = 'Success', github_pages_url = :url, end_time = :end_time
                WHERE id = :id
                """
            ),
            {"url": github_pages_url, "end_time": end_time, "id": deployment_id},
        )
        db.execute(
            text("UPDATE projects SET status = 'published', github_pages_url = :url WHERE id = :id"),
            {"url": github_pages_url, "id": project["id"]},
        )
        db.commit()

        return {
            "success": True,
            "message": "Deploy landing page thành công!",
            "data": {
                "deployment_id": deployment_id,
                "project_id": project["id"],
                "repo_url": repo_url,
                "github_pages_url": github_pages_url,
                "commit_sha": commit_sha,
                "status": "Success",
            },
        }

    except GitHubAuthError as exc:
        db.rollback()
        db.execute(
            text(
                """
                UPDATE deployments
                SET status = 'Failed', error_message = :err, end_time = :end_time
                WHERE id = :id
                """
            ),
            {"err": str(exc), "end_time": datetime.utcnow(), "id": deployment_id},
        )
        db.execute(
            text("UPDATE projects SET status = 'failed' WHERE id = :id"),
            {"id": project["id"]},
        )
        db.commit()
        # Dùng 503 thay vì 401 để frontend không nhầm với JWT hết hạn → không redirect login
        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers={"X-GitHub-Error": "auth"},
        )
    except GitHubRateLimitError as exc:
        db.rollback()
        db.execute(
            text(
                """
                UPDATE deployments
                SET status = 'Failed', error_message = :err, end_time = :end_time
                WHERE id = :id
                """
            ),
            {"err": str(exc), "end_time": datetime.utcnow(), "id": deployment_id},
        )
        db.execute(
            text("UPDATE projects SET status = 'failed' WHERE id = :id"),
            {"id": project["id"]},
        )
        db.commit()
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        )
    except GitHubRepoDuplicateError as exc:
        db.rollback()
        db.execute(
            text(
                """
                UPDATE deployments
                SET status = 'Failed', error_message = :err, end_time = :end_time
                WHERE id = :id
                """
            ),
            {"err": str(exc), "end_time": datetime.utcnow(), "id": deployment_id},
        )
        db.execute(
            text("UPDATE projects SET status = 'failed' WHERE id = :id"),
            {"id": project["id"]},
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )
    except Exception as exc:
        db.rollback()
        db.execute(
            text(
                """
                UPDATE deployments
                SET status = 'Failed', error_message = :err, end_time = :end_time
                WHERE id = :id
                """
            ),
            {"err": str(exc), "end_time": datetime.utcnow(), "id": deployment_id},
        )
        db.execute(
            text("UPDATE projects SET status = 'failed' WHERE id = :id"),
            {"id": project["id"]},
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"Deploy thất bại: {exc}")


@router.get("/{project_id}/deploy-status")
async def get_project_deploy_status(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    """
    GET /projects/{id}/deploy-status
    Kiểm tra trạng thái build GitHub Pages thực tế và chỉ trả link truy cập khi đã build xong.
    """
    latest_dep = (
        db.execute(
            text(
                """
                SELECT id, status, commit_sha, error_message, start_time, end_time
                FROM deployments
                WHERE project_id = :project_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"project_id": project["id"]},
        )
        .mappings()
        .first()
    )

    repo_url = project.get("repo_url")
    if not repo_url:
        return {
            "success": True,
            "data": {
                "project_id": project["id"],
                "deploy_status": latest_dep["status"] if latest_dep else "NotDeployed",
                "pages_build_status": "not_configured",
                "is_built": False,
                "github_pages_url": None,
                "error_message": latest_dep["error_message"] if latest_dep else None,
            },
        }

    parts = repo_url.rstrip("/").split("/")
    owner, repo_name = parts[-2], parts[-1]
    build_info = get_github_pages_build_status(owner=owner, repo_name=repo_name)
    build_status = (build_info.get("status") or "building").lower()
    is_built = build_status == "built"

    if latest_dep and latest_dep["status"] not in ("Success", "Failed"):
        if is_built:
            pages_url = build_info.get("html_url") or f"https://{owner.lower()}.github.io/{repo_name}/"
            db.execute(
                text(
                    """
                    UPDATE deployments
                    SET status = 'Success', github_pages_url = :url, end_time = :now
                    WHERE id = :id
                    """
                ),
                {"url": pages_url, "now": datetime.utcnow(), "id": latest_dep["id"]},
            )
            db.execute(
                text("UPDATE projects SET status = 'published', github_pages_url = :url WHERE id = :id"),
                {"url": pages_url, "id": project["id"]},
            )
            db.commit()
        elif build_status == "errored":
            db.execute(
                text(
                    """
                    UPDATE deployments
                    SET status = 'Failed', error_message = :err, end_time = :now
                    WHERE id = :id
                    """
                ),
                {"err": build_info.get("error"), "now": datetime.utcnow(), "id": latest_dep["id"]},
            )
            db.commit()

    return {
        "success": True,
        "data": {
            "project_id": project["id"],
            "deploy_status": "Success" if is_built else (latest_dep["status"] if latest_dep else "Building"),
            "pages_build_status": build_status,
            "is_built": is_built,
            "github_pages_url": build_info.get("html_url") if is_built else None,
            "error_message": build_info.get("error"),
        },
    }