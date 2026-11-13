"""Service xử lý nghiệp vụ quản lý phiên bản Landing Page.

Sử dụng PyMySQL trực tiếp (nhất quán với api/auth.py trên nhánh main).
Đáp ứng 3 User Story:
  US-06  Lưu phiên bản mới
  US-07  Xem danh sách & chi tiết phiên bản
  US-08  Khôi phục phiên bản cũ (Append-only)
"""

from __future__ import annotations

import json
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from core.config import settings


# ── Helpers ──────────────────────────────────────────────────────────
def _get_connection(autocommit: bool = False) -> pymysql.Connection:
    """Tạo kết nối PyMySQL tới database đã cấu hình."""
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


def _next_version_number(cursor: DictCursor, project_id: int) -> int:
    """Tính version_number tiếp theo cho một project (MAX + 1)."""
    cursor.execute(
        "SELECT COALESCE(MAX(version_number), 0) AS max_ver "
        "FROM project_versions WHERE project_id = %s FOR UPDATE",
        (project_id,),
    )
    row = cursor.fetchone()
    return row["max_ver"] + 1


def _require_project(cursor: DictCursor, project_id: int) -> dict:
    """Trả về project row hoặc raise ValueError nếu không tồn tại."""
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    if project is None:
        raise ValueError(f"Project {project_id} không tồn tại")
    return project


# ── US-06: Lưu phiên bản mới ────────────────────────────────────────
def create_version(
    project_id: int,
    html_snapshot: str,
    json_content: dict[str, Any] | None = None,
    commit_sha: str | None = None,
    change_summary: str | None = None,
    created_by: int | None = None,
) -> dict:
    """Tạo một version mới (Append-only) trong transaction.

    1. Kiểm tra project tồn tại.
    2. Tính version_number tiếp theo (dùng SELECT … FOR UPDATE để tránh race).
    3. INSERT version mới.
    4. Commit toàn bộ.

    Returns:
        dict chứa thông tin version vừa tạo.

    Raises:
        ValueError  – project không tồn tại hoặc html_snapshot rỗng.
        pymysql.IntegrityError – trùng (project_id, version_number).
    """
    if not html_snapshot or not html_snapshot.strip():
        raise ValueError("html_snapshot không được để trống")

    conn = _get_connection(autocommit=False)
    try:
        with conn.cursor() as cursor:
            _require_project(cursor, project_id)

            next_ver = _next_version_number(cursor, project_id)

            json_str = json.dumps(json_content, ensure_ascii=False) if json_content else None

            cursor.execute(
                """
                INSERT INTO project_versions
                    (project_id, version_number, json_content, html_snapshot,
                     commit_sha, change_summary, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    project_id,
                    next_ver,
                    json_str,
                    html_snapshot,
                    commit_sha,
                    change_summary,
                    created_by,
                ),
            )
            new_id = cursor.lastrowid

        conn.commit()

        # Đọc lại bản ghi vừa tạo
        return get_version_detail(project_id, new_id)

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── US-07: Danh sách phiên bản (payload rút gọn) ────────────────────
def list_versions(project_id: int) -> list[dict]:
    """Trả về danh sách version sắp xếp giảm dần theo version_number.

    Không tải html_snapshot để tối ưu dung lượng mạng.
    """
    conn = _get_connection(autocommit=True)
    try:
        with conn.cursor() as cursor:
            _require_project(cursor, project_id)

            cursor.execute(
                """
                SELECT id, version_number, change_summary, commit_sha,
                       created_by, created_at
                FROM project_versions
                WHERE project_id = %s
                ORDER BY version_number DESC
                """,
                (project_id,),
            )
            return cursor.fetchall()
    finally:
        conn.close()


# ── US-07: Chi tiết một phiên bản ───────────────────────────────────
def get_version_detail(project_id: int, version_id: int) -> dict | None:
    """Trả về đầy đủ thông tin version (bao gồm HTML & JSON).

    Returns None nếu version không tồn tại hoặc không thuộc project.
    """
    conn = _get_connection(autocommit=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, project_id, version_number, json_content,
                       html_snapshot, commit_sha, change_summary,
                       created_by, created_at
                FROM project_versions
                WHERE id = %s AND project_id = %s
                """,
                (version_id, project_id),
            )
            row = cursor.fetchone()
            if row and isinstance(row.get("json_content"), str):
                try:
                    row["json_content"] = json.loads(row["json_content"])
                except (json.JSONDecodeError, TypeError):
                    pass
            return row
    finally:
        conn.close()


# ── US-08: Khôi phục phiên bản cũ (Append-only) ────────────────────
def restore_version(
    project_id: int,
    version_id: int,
    created_by: int | None = None,
) -> dict:
    """Khôi phục phiên bản cũ bằng cách tạo version mới sao chép snapshot.

    Cơ chế Append-only: không xoá hay sửa bản ghi cũ mà tạo bản ghi mới
    với nội dung giống version_id cũ, change_summary ghi rõ nguồn gốc.

    Returns:
        dict chứa thông tin version mới (đã khôi phục).

    Raises:
        ValueError – version không tồn tại hoặc không thuộc project.
    """
    # 1. Lấy snapshot cũ
    old_version = get_version_detail(project_id, version_id)
    if old_version is None:
        raise ValueError(
            f"Version {version_id} không tồn tại hoặc không thuộc project {project_id}"
        )

    old_ver_num = old_version["version_number"]

    # 2. Tạo version mới với dữ liệu copy từ version cũ
    return create_version(
        project_id=project_id,
        html_snapshot=old_version["html_snapshot"],
        json_content=old_version.get("json_content"),
        commit_sha=old_version.get("commit_sha"),
        change_summary=f"Khôi phục từ phiên bản {old_ver_num}",
        created_by=created_by,
    )
