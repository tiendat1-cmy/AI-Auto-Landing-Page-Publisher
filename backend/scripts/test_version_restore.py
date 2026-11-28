"""Kiểm thử luồng khôi phục phiên bản Landing Page.

Script chạy hoàn toàn offline với SQLite in-memory:

  1. Service áp dụng lại ``json_content`` của version cũ lên bảng ``projects``.
  2. Chỉ các cột nội dung được phép thay đổi; không đụng ``repo_url``/``status``.
  3. HTML được render lại và push GitHub với commit SHA mới.
  4. Version mới được tạo theo cơ chế Append-only.
  5. Snapshot thiếu JSON hoặc dự án chưa có ``repo_url`` trả về warnings.
  6. Endpoint restore trả đúng các trường mới (commit_sha, warnings, ...).

Chạy:
    python backend/scripts/test_version_restore.py
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# SQLite không hỗ trợ kiểu Decimal của MySQL; adapter này chỉ dùng cho test offline.
sqlite3.register_adapter(Decimal, lambda value: float(value))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import services.version_restore_service as restore_service
from core.database import get_db
from core.security import get_current_user, get_owned_project
from main import app

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, full_name TEXT);
CREATE TABLE templates (id INTEGER PRIMARY KEY, name TEXT, file_path TEXT);
CREATE TABLE projects (
    id INTEGER PRIMARY KEY, user_id INTEGER, template_id INTEGER,
    campaign_name TEXT, product_name TEXT, product_description TEXT,
    price NUMERIC, status TEXT, color_theme TEXT, image_url TEXT,
    messenger_link TEXT, tiktok_shop_link TEXT, zalo_link TEXT,
    instagram_link TEXT, hotline TEXT,
    facebook_url TEXT, tiktok_url TEXT, instagram_url TEXT,
    raw_json_data TEXT, github_pages_url TEXT, repo_url TEXT,
    deleted_at DATETIME, created_at DATETIME, updated_at DATETIME
);
CREATE TABLE project_versions (
    id INTEGER PRIMARY KEY, project_id INTEGER, version_number INTEGER,
    html_snapshot TEXT, json_content TEXT, commit_sha TEXT,
    change_summary TEXT, created_by INTEGER, created_at DATETIME
);
"""

NOW = datetime(2026, 11, 27, 10, 0, 0)


def check(name: str, condition: bool, detail: str) -> None:
    if not condition:
        raise AssertionError(f"FAILED [{name}]: {detail}")
    print(f"PASSED [{name}]: {detail}")


def build_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite không có NOW(); đăng ký hàm tương đương để dùng lại SQL của MySQL.
    def _register_now(dbapi_connection, _connection_record):
        dbapi_connection.create_function(
            "NOW",
            0,
            lambda: datetime.now().isoformat(" "),
        )

    event.listen(engine, "connect", _register_now)

    with engine.begin() as conn:
        for statement in SCHEMA.strip().split(";"):
            if statement.strip():
                conn.execute(text(statement))

        conn.execute(
            text(
                "INSERT INTO users (id, email, full_name) "
                "VALUES (1, 'hoang@example.com', 'Nguyễn Khánh Hoàng')"
            )
        )
        conn.execute(text("INSERT INTO templates (id, name) VALUES (1, 'SaaS')"))
        conn.execute(
            text(
                """
                INSERT INTO projects
                (id, user_id, template_id, campaign_name, product_name,
                 product_description, price, status, color_theme, image_url,
                 messenger_link, raw_json_data, github_pages_url, repo_url,
                 deleted_at, created_at, updated_at)
                VALUES
                (1, 1, 1, 'Bản hiện tại', 'Sản phẩm hiện tại', 'Mô tả hiện tại',
                 100000, 'published', '#111111', NULL, 'm.me/current',
                 '{"headline": "Hiện tại"}',
                 'https://tester.github.io/lp-1', 'https://github.com/tester/lp-1',
                 NULL, :now, :now),
                (2, 1, 1, 'Chưa xuất bản', 'Sản phẩm nháp', 'Mô tả nháp',
                 50000, 'draft', '#222222', NULL, NULL,
                 NULL, NULL, NULL, NULL, :now, :now),
                (3, 1, 1, 'API hiện tại', 'Sản phẩm API hiện tại', 'Mô tả API',
                 70000, 'published', '#333333', NULL, 'm.me/api',
                 '{"headline": "API hiện tại"}',
                 'https://tester.github.io/lp-3', 'https://github.com/tester/lp-3',
                 NULL, :now, :now)
                """
            ),
            {"now": NOW},
        )

        old_snapshot = {
            "id": 1,
            "user_id": 999,  # Không được phép khôi phục
            "template_id": 1,
            "campaign_name": "Bản cũ",
            "product_name": "Sản phẩm khôi phục",
            "product_description": "Mô tả cũ",
            "price": 250000,
            "color_theme": "#ABCDEF",
            "image_url": "https://cdn.example.com/old.png",
            "messenger_link": "m.me/old",
            "raw_json_data": {"headline": "Tiêu đề khôi phục"},
            "status": "deleted",  # Không được phép khôi phục
            "repo_url": "https://github.com/ke-gian/evil",  # Không được phép khôi phục
            "github_pages_url": "https://evil.example.com",  # Không được phép khôi phục
            "deleted_at": "2026-01-01T00:00:00",  # Không được phép khôi phục
        }
        api_snapshot = {
            "template_id": 1,
            "campaign_name": "API cũ",
            "product_name": "Sản phẩm API khôi phục",
            "product_description": "Mô tả API cũ",
            "price": 99000,
            "color_theme": "#FEDCBA",
            "raw_json_data": {"headline": "API khôi phục"},
        }

        conn.execute(
            text(
                """
                INSERT INTO project_versions
                (id, project_id, version_number, html_snapshot, json_content,
                 commit_sha, change_summary, created_by, created_at)
                VALUES
                (10, 1, 2, '<html><body>old snapshot</body></html>', :json1,
                 'oldsha111', 'Bản cũ', 1, :t1),
                (20, 2, 1, '<html><body>only old html</body></html>', NULL,
                 NULL, 'Chỉ có HTML', 1, :t2),
                (30, 3, 1, '<html><body>api old snapshot</body></html>', :json3,
                 'apisha111', 'API cũ', 1, :t3)
                """
            ),
            {
                "json1": json.dumps(old_snapshot, ensure_ascii=False),
                "json3": json.dumps(api_snapshot, ensure_ascii=False),
                "t1": NOW - timedelta(days=2),
                "t2": NOW - timedelta(days=1),
                "t3": NOW - timedelta(hours=2),
            },
        )

    return engine


def fake_new_version(**kwargs):
    return {
        "id": 99,
        "project_id": kwargs["project_id"],
        "version_number": 3,
        "json_content": kwargs.get("json_content"),
        "html_snapshot": kwargs["html_snapshot"],
        "commit_sha": kwargs.get("commit_sha"),
        "change_summary": kwargs.get("change_summary"),
        "created_by": kwargs.get("created_by"),
        "created_by_name": "Nguyễn Khánh Hoàng",
        "created_by_email": "hoang@example.com",
        "created_at": NOW,
    }


def test_service_restore(engine):
    print("\n── Service: khôi phục đầy đủ JSON + push GitHub ──")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()

    project = {
        "id": 1,
        "repo_url": "https://github.com/tester/lp-1",
        "github_pages_url": "https://tester.github.io/lp-1",
    }
    snapshot = {
        "id": 10,
        "project_id": 1,
        "version_number": 2,
        "json_content": {
            "template_id": 1,
            "campaign_name": "Bản cũ",
            "product_name": "Sản phẩm khôi phục",
            "product_description": "Mô tả cũ",
            "price": 250000,
            "color_theme": "#ABCDEF",
            "image_url": "https://cdn.example.com/old.png",
            "messenger_link": "m.me/old",
            "raw_json_data": {"headline": "Tiêu đề khôi phục"},
            "user_id": 999,
            "status": "deleted",
            "repo_url": "https://github.com/ke-gian/evil",
            "github_pages_url": "https://evil.example.com",
            "deleted_at": "2026-01-01T00:00:00",
        },
        "html_snapshot": "<html><body>old snapshot</body></html>",
        "commit_sha": "oldsha111",
        "change_summary": "Bản cũ",
        "created_by": 1,
        "created_at": NOW - timedelta(days=2),
    }

    captured = {}

    def fake_push(**kwargs):
        captured["push"] = kwargs
        return "newsha222"

    def capture_create(**kwargs):
        captured["create"] = kwargs
        return fake_new_version(**kwargs)

    with patch.object(restore_service, "get_version_detail", return_value=snapshot), \
         patch.object(restore_service, "create_version", side_effect=capture_create), \
         patch.object(
             restore_service.github_service,
             "push_landing_page_commit",
             side_effect=fake_push,
         ):
        result = restore_service.restore_project_version(
            db=db,
            project=project,
            version_id=10,
            created_by=1,
        )

    check("Append-only version", result["new_version"]["id"] == 99, "đã tạo version mới")
    check(
        "Áp dụng nội dung",
        result["applied_to_project"] is True,
        f"restored_fields={result['restored_fields']}",
    )
    check(
        "Không khôi phục cột hệ thống",
        not {"user_id", "status", "repo_url", "github_pages_url", "deleted_at"}
        & set(result["restored_fields"]),
        "chỉ các cột nội dung được phép",
    )
    check(
        "Push GitHub",
        captured["push"]["repo_url"] == "https://github.com/tester/lp-1"
        and "Sản phẩm khôi phục" in captured["push"]["html_content"],
        "HTML đã render lại và push đúng repo",
    )
    check(
        "Commit SHA mới",
        result["commit_sha"] == "newsha222"
        and captured["create"]["commit_sha"] == "newsha222",
        "version mới lưu commit SHA mới",
    )
    check(
        "Change summary",
        captured["create"]["change_summary"] == "Khôi phục từ phiên bản 2",
        captured["create"]["change_summary"],
    )

    row = db.execute(
        text(
            "SELECT campaign_name, product_name, price, color_theme, image_url, "
            "messenger_link, raw_json_data, user_id, status, repo_url, "
            "github_pages_url, deleted_at FROM projects WHERE id = 1"
        )
    ).mappings().first()

    check(
        "DB project được cập nhật",
        row["campaign_name"] == "Bản cũ"
        and row["product_name"] == "Sản phẩm khôi phục"
        and float(row["price"]) == 250000
        and row["color_theme"] == "#ABCDEF"
        and row["image_url"] == "https://cdn.example.com/old.png"
        and row["messenger_link"] == "m.me/old",
        "text/giá/link/ảnh đã khôi phục",
    )
    check(
        "Cột hệ thống giữ nguyên",
        row["user_id"] == 1
        and row["status"] == "published"
        and row["repo_url"] == "https://github.com/tester/lp-1"
        and row["github_pages_url"] == "https://tester.github.io/lp-1"
        and row["deleted_at"] is None,
        "không bị snapshot cũ ghi đè",
    )
    check(
        "raw_json_data khôi phục",
        "Tiêu đề khôi phục" in (row["raw_json_data"] or ""),
        row["raw_json_data"],
    )

    db.close()


def test_service_fallback(engine):
    print("\n── Service: snapshot thiếu JSON / dự án chưa xuất bản ──")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()

    project = {"id": 2, "repo_url": None, "github_pages_url": None}
    snapshot = {
        "id": 20,
        "project_id": 2,
        "version_number": 1,
        "json_content": None,
        "html_snapshot": "<html><body>only old html</body></html>",
        "commit_sha": None,
        "change_summary": "Chỉ có HTML",
        "created_by": 1,
        "created_at": NOW - timedelta(days=1),
    }

    captured = {}

    def capture_create(**kwargs):
        captured["create"] = kwargs
        return fake_new_version(**kwargs)

    with patch.object(restore_service, "get_version_detail", return_value=snapshot), \
         patch.object(restore_service, "create_version", side_effect=capture_create), \
         patch.object(
             restore_service.github_service,
             "push_landing_page_commit",
         ) as push_mock:
        result = restore_service.restore_project_version(
            db=db,
            project=project,
            version_id=20,
            created_by=1,
        )

    check(
        "Fallback HTML snapshot",
        captured["create"]["html_snapshot"] == "<html><body>only old html</body></html>",
        "dùng lại HTML cũ khi không có JSON",
    )
    check(
        "Không push khi chưa có repo",
        push_mock.called is False and result["commit_sha"] is None,
        "bỏ qua GitHub, commit_sha=None",
    )
    check(
        "Có warnings",
        any("JSON nội dung" in warning for warning in result["warnings"])
        and any("repo_url" in warning for warning in result["warnings"]),
        f"{len(result['warnings'])} cảnh báo",
    )
    check(
        "Không đánh dấu áp dụng",
        result["applied_to_project"] is False,
        "project giữ nguyên",
    )

    db.close()


def test_api_restore(engine):
    print("\n── API: POST /versions/{id}/restore ──")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    project = {
        "id": 3,
        "user_id": 1,
        "repo_url": "https://github.com/tester/lp-3",
        "github_pages_url": "https://tester.github.io/lp-3",
    }
    snapshot = {
        "id": 30,
        "project_id": 3,
        "version_number": 1,
        "json_content": {
            "template_id": 1,
            "campaign_name": "API cũ",
            "product_name": "Sản phẩm API khôi phục",
            "product_description": "Mô tả API cũ",
            "price": 99000,
            "color_theme": "#FEDCBA",
            "raw_json_data": {"headline": "API khôi phục"},
        },
        "html_snapshot": "<html><body>api old snapshot</body></html>",
        "commit_sha": "apisha111",
        "change_summary": "API cũ",
        "created_by": 1,
        "created_at": NOW - timedelta(hours=2),
    }

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "email": "hoang@example.com",
        "full_name": "Nguyễn Khánh Hoàng",
    }
    app.dependency_overrides[get_owned_project] = lambda: project

    client = TestClient(app)

    try:
        with patch.object(restore_service, "get_version_detail", return_value=snapshot), \
             patch.object(
                 restore_service,
                 "create_version",
                 side_effect=fake_new_version,
             ), \
             patch.object(
                 restore_service.github_service,
                 "push_landing_page_commit",
                 return_value="apinewsha",
             ):
            response = client.post("/api/v1/projects/3/versions/30/restore")

        check("HTTP 201", response.status_code == 201, f"HTTP {response.status_code}")
        payload = response.json()
        check(
            "Response schema",
            payload["restored_from_version"] == 1
            and payload["new_version"]["version_number"] == 3
            and payload["commit_sha"] == "apinewsha"
            and payload["applied_to_project"] is True
            and isinstance(payload["warnings"], list)
            and payload["new_version"]["created_by_name"] == "Nguyễn Khánh Hoàng",
            "đủ commit_sha/warnings/created_by_name",
        )

        with patch.object(restore_service, "get_version_detail", return_value=None):
            missing = client.post("/api/v1/projects/3/versions/999/restore")
        check(
            "Version không tồn tại",
            missing.status_code == 404,
            f"HTTP {missing.status_code}",
        )
    finally:
        app.dependency_overrides.clear()

    db = Session()
    row = db.execute(
        text("SELECT product_name, repo_url FROM projects WHERE id = 3")
    ).mappings().first()
    check(
        "API cập nhật project",
        row["product_name"] == "Sản phẩm API khôi phục"
        and row["repo_url"] == "https://github.com/tester/lp-3",
        "nội dung khôi phục, repo giữ nguyên",
    )
    db.close()


def run() -> None:
    print("=" * 70)
    print("[VERSION RESTORE] KIỂM THỬ KHÔI PHỤC PHIÊN BẢN")
    print("=" * 70)

    engine = build_engine()
    test_service_restore(engine)
    test_service_fallback(engine)
    test_api_restore(engine)

    print("\n" + "=" * 70)
    print("TẤT CẢ KIỂM THỬ KHÔI PHỤC PHIÊN BẢN ĐỀU PASS")
    print("=" * 70)


if __name__ == "__main__":
    run()
