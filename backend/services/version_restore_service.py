"""Service khôi phục phiên bản Landing Page lên dự án và website.

Endpoint ``POST /api/v1/projects/{project_id}/versions/{version_id}/restore``
dùng service này để:

1. Đọc snapshot ``json_content`` của phiên bản cũ.
2. Áp dụng lại các cột nội dung được phép vào bảng ``projects``.
3. Render lại HTML từ dữ liệu vừa khôi phục.
4. Push commit mới lên GitHub Pages (nếu dự án đã có ``repo_url``).
5. Tạo một version mới (Append-only) với commit SHA mới.

Service được tách riêng khỏi ``api/versions.py`` và ``services/version_service.py``
để giảm xung đột khi merge, đồng thời cho phép test luồng restore độc lập.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from services import github_service, template_service
from services.version_service import create_version, get_version_detail

logger = logging.getLogger(__name__)

# Chỉ khôi phục các cột nội dung người dùng có thể sửa. Không đụng tới
# user_id, status, repo_url, github_pages_url, deleted_at... để tránh làm
# hỏng liên kết GitHub Pages hiện tại của dự án.
RESTORABLE_FIELDS: tuple[str, ...] = (
    "template_id",
    "campaign_name",
    "product_name",
    "product_description",
    "price",
    "image_url",
    "color_theme",
    "messenger_link",
    "tiktok_shop_link",
    "zalo_link",
    "instagram_link",
    "hotline",
    "facebook_url",
    "tiktok_url",
    "instagram_url",
    "raw_json_data",
)

# Hai cột NOT NULL trong bảng projects: không bao giờ ghi đè bằng None/rỗng.
REQUIRED_FIELDS = {"campaign_name", "product_name"}


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


def _load_json_content(version: dict) -> dict[str, Any] | None:
    """Đọc ``json_content`` của version, trả None nếu không phải object JSON."""
    raw = version.get("json_content")
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return raw if isinstance(raw, dict) else None


def _build_update_data(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Lọc snapshot thành dữ liệu cập nhật hợp lệ cho bảng ``projects``."""
    update_data: dict[str, Any] = {}

    for field in RESTORABLE_FIELDS:
        if field not in snapshot:
            continue

        value = snapshot[field]

        if field in REQUIRED_FIELDS and (value is None or not str(value).strip()):
            continue

        if field == "price" and value is not None:
            try:
                value = Decimal(str(value))
            except (InvalidOperation, ValueError):
                continue

        if field == "raw_json_data":
            value = _parse_raw_json(value)
            if value is not None and not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)

        update_data[field] = value

    return update_data


def _apply_update_data(
    db: Session,
    project_id: int,
    update_data: dict[str, Any],
) -> None:
    """Cập nhật các cột nội dung của project trong một transaction."""
    if not update_data:
        return

    set_clauses = ", ".join(f"{column} = :{column}" for column in update_data)
    db.execute(
        text(
            f"UPDATE projects SET {set_clauses}, updated_at = NOW() "
            "WHERE id = :id AND deleted_at IS NULL"
        ),
        {**update_data, "id": project_id},
    )
    db.commit()


def _fetch_project_dict(db: Session, project_id: int) -> dict[str, Any]:
    """Đọc lại project sau khi cập nhật, chuẩn hoá JSON-safe để render."""
    row = (
        db.execute(
            text("SELECT * FROM projects WHERE id = :id AND deleted_at IS NULL"),
            {"id": project_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError(f"Project {project_id} không tồn tại")

    project = _json_safe(dict(row))
    project["raw_json_data"] = _json_safe(_parse_raw_json(project.get("raw_json_data")))
    return project


def _validate_template(
    db: Session,
    update_data: dict[str, Any],
    warnings: list[str],
) -> None:
    """Bỏ template_id nếu template cũ không còn tồn tại (tránh lỗi FK)."""
    template_id = update_data.get("template_id")
    if template_id is None:
        return

    exists = db.execute(
        text("SELECT id FROM templates WHERE id = :id"),
        {"id": template_id},
    ).first()
    if not exists:
        update_data.pop("template_id", None)
        warnings.append(
            f"Template #{template_id} của phiên bản cũ không còn tồn tại nên được giữ nguyên template hiện tại."
        )


# ── Luồng khôi phục chính ────────────────────────────────────────────
def restore_project_version(
    db: Session,
    project: dict,
    version_id: int,
    created_by: int | None = None,
) -> dict[str, Any]:
    """Khôi phục một version cũ lên project hiện tại và website GitHub Pages.

    Args:
        db: SQLAlchemy session đang dùng cho request.
        project: dict project đã được ``get_owned_project`` xác thực quyền.
        version_id: id của version cần khôi phục.
        created_by: id người dùng thực hiện khôi phục.

    Returns:
        dict gồm ``restored_from_version``, ``new_version``, ``commit_sha``,
        ``github_pages_url``, ``warnings``, ``restored_fields`` và
        ``applied_to_project``.

    Raises:
        ValueError: version không tồn tại/không thuộc project, hoặc snapshot
            không có HTML để khôi phục.
    """
    project_id = project["id"]

    # 1. Lấy snapshot cũ (service version dùng PyMySQL, đã join users).
    old_version = get_version_detail(project_id, version_id)
    if old_version is None:
        raise ValueError(
            f"Version {version_id} không tồn tại hoặc không thuộc project {project_id}"
        )

    old_ver_num = old_version["version_number"]
    warnings: list[str] = []

    # 2. Áp dụng lại dữ liệu nội dung từ snapshot JSON.
    snapshot = _load_json_content(old_version)
    update_data: dict[str, Any] = {}

    if snapshot is None:
        warnings.append(
            "Phiên bản này không có JSON nội dung nên chỉ khôi phục lại HTML snapshot."
        )
    else:
        update_data = _build_update_data(snapshot)
        _validate_template(db, update_data, warnings)
        if not update_data:
            warnings.append(
                "Snapshot không có trường nội dung hợp lệ nào để áp dụng lên dự án."
            )

    applied_to_project = bool(update_data)
    if applied_to_project:
        _apply_update_data(db, project_id, update_data)

    project_dict = _fetch_project_dict(db, project_id)

    # 3. Render lại HTML từ dữ liệu vừa khôi phục; fallback về HTML snapshot.
    rendered_html = ""
    if applied_to_project:
        try:
            rendered_html = template_service.render_landing_page(project_dict)
        except Exception as exc:  # pragma: no cover - lỗi template hiếm gặp
            logger.exception("Render HTML khôi phục thất bại cho project %s", project_id)
            warnings.append(f"Không render lại được HTML, dùng HTML snapshot cũ: {exc}")

    if not rendered_html or not rendered_html.strip():
        rendered_html = old_version.get("html_snapshot") or ""

    if not rendered_html.strip():
        raise ValueError(
            f"Version {version_id} không có HTML snapshot để khôi phục"
        )

    # 4. Push commit mới lên GitHub nếu dự án đã từng xuất bản.
    repo_url = (project_dict.get("repo_url") or "").strip()
    commit_sha: str | None = None

    if repo_url:
        try:
            commit_sha = github_service.push_landing_page_commit(
                repo_url=repo_url,
                html_content=rendered_html,
                commit_message=(
                    f"Khôi phục phiên bản v{old_ver_num}: "
                    f"{project_dict.get('campaign_name') or project_dict.get('product_name') or 'Landing Page'}"
                ),
                file_path="index.html",
            )
        except Exception as exc:  # pragma: no cover - lỗi mạng/hạ tầng
            logger.exception("Push GitHub khôi phục thất bại cho project %s", project_id)
            warnings.append(f"Không push được commit GitHub: {exc}")
    else:
        warnings.append(
            "Dự án chưa có repo_url nên bỏ qua bước cập nhật website GitHub Pages."
        )

    # 5. Append-only: luôn tạo version mới, không sửa/xoá lịch sử cũ.
    new_version = create_version(
        project_id=project_id,
        html_snapshot=rendered_html,
        json_content=_json_safe(project_dict),
        commit_sha=commit_sha,
        change_summary=f"Khôi phục từ phiên bản {old_ver_num}",
        created_by=created_by,
    )

    return {
        "restored_from_version": old_ver_num,
        "new_version": new_version,
        "commit_sha": commit_sha,
        "github_pages_url": project_dict.get("github_pages_url"),
        "warnings": warnings,
        "restored_fields": sorted(update_data.keys()),
        "applied_to_project": applied_to_project,
    }
