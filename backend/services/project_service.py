"""Service xử lý nghiệp vụ cho Project Landing Page.

Đảm nhiệm quy trình theo yêu cầu:
  sửa text, giá, link social -> render lại HTML -> push commit mới lên GitHub -> lưu phiên bản mới.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from core.config import settings
from schemas.project import ProjectUpdateRequest
from services.github_service import push_landing_page_commit
from services.template_service import render_landing_page
from services.version_service import create_version


def _get_connection(autocommit: bool = False) -> pymysql.Connection:
    """Tạo kết nối PyMySQL tới database."""
    return pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=autocommit,
    )


def _serialize_project_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Chuyển đổi Decimal và JSON string sang kiểu dữ liệu Python tương ứng."""
    if not row:
        return None
    res = dict(row)
    if isinstance(res.get("price"), Decimal):
        res["price"] = float(res["price"])
    raw_json = res.get("raw_json_data")
    if isinstance(raw_json, str):
        try:
            res["raw_json_data"] = json.loads(raw_json)
        except Exception:
            pass
    return res


def get_project(project_id: int) -> dict[str, Any]:
    """Lấy thông tin chi tiết của một project theo ID.

    Raises:
        ValueError: Nếu project_id không tồn tại.
    """
    conn = _get_connection(autocommit=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Project {project_id} không tồn tại")
            return _serialize_project_row(row)
    finally:
        conn.close()


def list_projects() -> list[dict[str, Any]]:
    """Lấy danh sách tất cả các projects."""
    conn = _get_connection(autocommit=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM projects ORDER BY id DESC")
            rows = cursor.fetchall()
            return [_serialize_project_row(r) for r in rows]
    finally:
        conn.close()


def update_landing_page(
    project_id: int,
    payload: ProjectUpdateRequest,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Cập nhật thông tin Landing Page, render HTML, push GitHub commit, và lưu version mới.

    Các bước thực hiện:
      1. Tìm và khoá bản ghi project hiện tại.
      2. Cập nhật các trường text, giá, link social vào bảng `projects`.
      3. Render lại mã nguồn HTML hoàn chỉnh dựa trên dữ liệu mới.
      4. Tạo commit và push lên GitHub (nhận commit_sha).
      5. Lưu phiên bản mới vào bảng `project_versions` (Append-only).
      6. Commit transaction và trả về kết quả.
    """
    conn = _get_connection(autocommit=False)
    try:
        with conn.cursor() as cursor:
            # 1. Kiểm tra project tồn tại
            cursor.execute("SELECT * FROM projects WHERE id = %s FOR UPDATE", (project_id,))
            current = cursor.fetchone()
            if not current:
                raise ValueError(f"Project {project_id} không tồn tại")

            # 2. Chuẩn bị giá trị cập nhật
            campaign_name = (
                payload.campaign_name if payload.campaign_name is not None else current["campaign_name"]
            )
            product_name = (
                payload.product_name if payload.product_name is not None else current["product_name"]
            )
            product_description = (
                payload.product_description
                if payload.product_description is not None
                else current["product_description"]
            )
            price = payload.price if payload.price is not None else current["price"]
            image_url = payload.image_url if payload.image_url is not None else current["image_url"]
            color_theme = payload.color_theme if payload.color_theme is not None else current["color_theme"]
            facebook_url = (
                payload.facebook_url if payload.facebook_url is not None else current["facebook_url"]
            )
            tiktok_url = payload.tiktok_url if payload.tiktok_url is not None else current["tiktok_url"]
            instagram_url = (
                payload.instagram_url if payload.instagram_url is not None else current["instagram_url"]
            )
            repo_url = payload.repo_url if payload.repo_url is not None else current["repo_url"]
            github_pages_url = (
                payload.github_pages_url
                if payload.github_pages_url is not None
                else current["github_pages_url"]
            )

            # Xử lý raw_json_data
            if payload.raw_json_data is not None:
                new_raw_json = payload.raw_json_data
            else:
                raw_cur = current.get("raw_json_data")
                if isinstance(raw_cur, str):
                    try:
                        new_raw_json = json.loads(raw_cur)
                    except Exception:
                        new_raw_json = None
                else:
                    new_raw_json = raw_cur

            raw_json_str = (
                json.dumps(new_raw_json, ensure_ascii=False) if new_raw_json is not None else None
            )

            # Thực hiện UPDATE bảng projects
            update_sql = """
                UPDATE projects
                SET campaign_name = %s,
                    product_name = %s,
                    product_description = %s,
                    price = %s,
                    image_url = %s,
                    color_theme = %s,
                    facebook_url = %s,
                    tiktok_url = %s,
                    instagram_url = %s,
                    repo_url = %s,
                    github_pages_url = %s,
                    raw_json_data = %s,
                    status = 'published'
                WHERE id = %s
            """
            cursor.execute(
                update_sql,
                (
                    campaign_name,
                    product_name,
                    product_description,
                    price,
                    image_url,
                    color_theme,
                    facebook_url,
                    tiktok_url,
                    instagram_url,
                    repo_url,
                    github_pages_url,
                    raw_json_str,
                    project_id,
                ),
            )

            # Lấy lại bản ghi sau cập nhật
            cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
            updated_row = cursor.fetchone()
            updated_project = _serialize_project_row(updated_row)

            # Commit cập nhật project trước khi tạo version
            conn.commit()

    except Exception:
        conn.rollback()
        conn.close()
        raise
    finally:
        if conn.open:
            conn.close()

    # 3. Render lại HTML từ thông tin đã cập nhật
    rendered_html = render_landing_page(updated_project)

    # 4. Push commit mới lên GitHub
    commit_msg = (
        payload.commit_message
        or f"Cập nhật landing page: {payload.change_summary or 'sửa text, giá, link social'}"
    )
    commit_sha = push_landing_page_commit(
        repo_url=updated_project.get("repo_url"),
        html_content=rendered_html,
        commit_message=commit_msg,
    )

    # 5. Lưu phiên bản mới vào project_versions
    json_snapshot = {
        "campaign_name": updated_project.get("campaign_name"),
        "product_name": updated_project.get("product_name"),
        "product_description": updated_project.get("product_description"),
        "price": updated_project.get("price"),
        "color_theme": updated_project.get("color_theme"),
        "image_url": updated_project.get("image_url"),
        "facebook_url": updated_project.get("facebook_url"),
        "tiktok_url": updated_project.get("tiktok_url"),
        "instagram_url": updated_project.get("instagram_url"),
        "repo_url": updated_project.get("repo_url"),
        "github_pages_url": updated_project.get("github_pages_url"),
        "raw_json_data": updated_project.get("raw_json_data"),
    }

    new_version = create_version(
        project_id=project_id,
        html_snapshot=rendered_html,
        json_content=json_snapshot,
        commit_sha=commit_sha,
        change_summary=payload.change_summary or "Cập nhật landing page: text, giá, link social",
        created_by=user_id,
    )

    return {
        "message": "Cập nhật landing page và tạo phiên bản mới thành công!",
        "project": updated_project,
        "commit_sha": commit_sha,
        "version_id": new_version.get("id"),
        "version_number": new_version.get("version_number"),
        "rendered_html": rendered_html,
    }
