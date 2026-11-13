"""Kiểm tra bảng generations và cột projects.raw_json_data trên MySQL hiện tại.

Chạy từ thư mục backend:
    python scripts/test_generations.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models import STATUS_FAILED, STATUS_PENDING, STATUS_SUCCESS, Generation, Project
from scripts.init_db import init_database
from services.generation_service import (
    ProjectNotFoundError,
    create_pending_generation,
    execute_generation,
    mark_generation_failed,
    mark_generation_success,
)


def check(name: str, condition: bool, detail: str) -> None:
    if not condition:
        raise AssertionError(f"FAIL {name}: {detail}")
    print(f"PASS {name}: {detail}")


def main() -> None:
    init_database()
    db = SessionLocal()
    project_id = None
    try:
        project = Project(raw_json_data=None)
        db.add(project)
        db.commit()
        db.refresh(project)
        project_id = project.id

        check(
            "Test 1",
            project.raw_json_data is None,
            f"project {project.id} mới tạo có raw_json_data = NULL",
        )

        pending = create_pending_generation(db, project.id, "Viết landing page quán cà phê")
        check(
            "Test 2",
            pending.status == STATUS_PENDING
            and pending.response_json is None
            and pending.error_message is None
            and pending.created_at is not None,
            f"generation {pending.id} status=pending, response_json=NULL, created_at={pending.created_at}",
        )
        created_at = pending.created_at
        if created_at.tzinfo is not None:
            created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
        drift = abs(datetime.now(timezone.utc).replace(tzinfo=None) - created_at)
        check(
            "Test 2b",
            drift <= timedelta(minutes=2),
            f"created_at lệch UTC hiện tại {drift}",
        )

        success_payload = {
            "title": "Cà phê Sài Gòn",
            "sections": ["hero", "menu"],
            "published": False,
        }
        succeeded = mark_generation_success(db, pending.id, success_payload)
        db.refresh(project)
        check(
            "Test 3",
            succeeded.status == STATUS_SUCCESS
            and succeeded.response_json == success_payload
            and succeeded.error_message is None
            and project.raw_json_data == success_payload,
            "response_json đã lưu, status=success, raw_json_data được cập nhật",
        )

        previous_json = project.raw_json_data
        failed = execute_generation(
            db,
            project.id,
            "Prompt bị lỗi",
            lambda: (_ for _ in ()).throw(RuntimeError("Gemini timeout")),
        )
        db.refresh(project)
        check(
            "Test 4",
            failed.status == STATUS_FAILED
            and failed.error_message == "Gemini timeout"
            and failed.response_json is None
            and project.raw_json_data == previous_json,
            "status=failed, error_message được lưu, raw_json_data cũ không bị ghi đè",
        )

        second = execute_generation(
            db,
            project.id,
            "Viết lại phần hero",
            lambda: {"title": "Cà phê mới", "sections": ["hero"]},
        )
        history = db.scalars(
            select(Generation)
            .where(Generation.project_id == project.id)
            .order_by(Generation.id)
        ).all()
        db.refresh(project)
        check(
            "Test 5",
            len(history) == 3
            and [item.status for item in history] == [STATUS_SUCCESS, STATUS_FAILED, STATUS_SUCCESS]
            and history[0].response_json == success_payload
            and second.status == STATUS_SUCCESS
            and project.raw_json_data == {"title": "Cà phê mới", "sections": ["hero"]},
            "3 lần sinh vẫn còn trong lịch sử; raw_json_data là kết quả thành công mới nhất",
        )

        orphan = Generation(
            project_id=2_000_000_000,
            prompt="project không tồn tại",
            status=STATUS_PENDING,
        )
        db.add(orphan)
        try:
            db.commit()
            raise AssertionError("FAIL Test 6: khóa ngoại đã cho phép project_id không tồn tại")
        except IntegrityError:
            db.rollback()
            print("PASS Test 6: khóa ngoại từ chối project_id không tồn tại")

        invalid = Generation(
            project_id=project.id,
            prompt="status lạ",
            status="oops",
        )
        db.add(invalid)
        try:
            db.commit()
            raise AssertionError("FAIL Test 6b: status ngoài pending/success/failed vẫn được ghi")
        except (IntegrityError, OperationalError):
            db.rollback()
            print("PASS Test 6b: CHECK chỉ cho phép pending, success, failed")

        stored_id = project.id
        db.execute(text("DELETE FROM projects WHERE id = :id"), {"id": stored_id})
        db.commit()
        db.expire_all()
        remaining = db.scalars(
            select(Generation).where(Generation.project_id == stored_id)
        ).all()
        deleted_project = db.get(Project, stored_id)
        check(
            "Test 7",
            deleted_project is None and remaining == [],
            "xóa project bằng SQL đã cascade xóa toàn bộ generation liên quan",
        )
        project_id = None

        try:
            create_pending_generation(db, stored_id, "project đã xóa")
            raise AssertionError("FAIL: vẫn tạo generation sau khi project bị xóa")
        except ProjectNotFoundError:
            print("PASS Extra: service từ chối project không tồn tại trước khi ghi generation")

        plain_text = execute_generation(
            db,
            _temporary_project(db),
            "không phải json",
            lambda: "chỉ là một chuỗi mô tả",
        )
        plain_project_id = plain_text.project_id
        plain_project = db.get(Project, plain_project_id)
        check(
            "Test JSON",
            plain_text.status == STATUS_FAILED
            and plain_project.raw_json_data is None,
            "chuỗi thường không được ghi vào response_json hay raw_json_data",
        )
        db.execute(text("DELETE FROM projects WHERE id = :id"), {"id": plain_project_id})
        db.commit()

        direct_failed = create_pending_generation(db, _temporary_project(db), "fail thủ công")
        owned_project_id = direct_failed.project_id
        owned_project = db.get(Project, owned_project_id)
        owned_project.raw_json_data = {"keep": True}
        db.commit()
        mark_generation_failed(db, direct_failed.id, "lỗi chủ động")
        db.refresh(owned_project)
        refreshed = db.get(Generation, direct_failed.id)
        check(
            "Test 4b",
            refreshed.status == STATUS_FAILED
            and refreshed.error_message == "lỗi chủ động"
            and owned_project.raw_json_data == {"keep": True},
            "mark_generation_failed không ghi đè raw_json_data",
        )
        db.execute(text("DELETE FROM projects WHERE id = :id"), {"id": owned_project_id})
        db.commit()
    finally:
        if project_id is not None:
            db.rollback()
            db.execute(text("DELETE FROM projects WHERE id = :id"), {"id": project_id})
            db.commit()
        db.close()


def _temporary_project(db) -> int:
    project = Project(raw_json_data=None)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project.id


if __name__ == "__main__":
    main()
