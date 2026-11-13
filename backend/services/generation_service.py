"""Lưu lịch sử sinh nội dung. Chưa gọi Gemini.

gemini_service.py hiện chưa có luồng sinh. Service này chỉ ghi database
để API generate sau này gọi vào, thay vì tự viết client Gemini.
"""

import copy
from typing import Any, Callable

from sqlalchemy.orm import Session

from models import STATUS_FAILED, STATUS_PENDING, STATUS_SUCCESS, Generation, Project


class ProjectNotFoundError(Exception):
    pass


class GenerationNotFoundError(Exception):
    pass


class InvalidGenerationResultError(Exception):
    pass


def _require_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError("Project không tồn tại")
    return project


def _require_structured_json(response_json: Any) -> Any:
    if not isinstance(response_json, (dict, list)):
        raise InvalidGenerationResultError(
            "Kết quả sinh nội dung phải là JSON object hoặc array"
        )
    return copy.deepcopy(response_json)


def create_pending_generation(db: Session, project_id: int, prompt: str) -> Generation:
    if prompt is None or not str(prompt).strip():
        raise ValueError("Prompt không được để trống")

    _require_project(db, project_id)
    generation = Generation(
        project_id=project_id,
        prompt=prompt,
        response_json=None,
        status=STATUS_PENDING,
        error_message=None,
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)
    return generation


def mark_generation_success(
    db: Session,
    generation_id: int,
    response_json: Any,
) -> Generation:
    payload = _require_structured_json(response_json)
    generation = db.get(Generation, generation_id)
    if generation is None:
        raise GenerationNotFoundError("Generation không tồn tại")

    project = _require_project(db, generation.project_id)
    generation.response_json = payload
    generation.status = STATUS_SUCCESS
    generation.error_message = None
    project.raw_json_data = copy.deepcopy(payload)
    db.commit()
    db.refresh(generation)
    return generation


def mark_generation_failed(
    db: Session,
    generation_id: int,
    error_message: str,
) -> Generation:
    generation = db.get(Generation, generation_id)
    if generation is None:
        raise GenerationNotFoundError("Generation không tồn tại")

    generation.status = STATUS_FAILED
    generation.error_message = error_message
    db.commit()
    db.refresh(generation)
    return generation


def execute_generation(
    db: Session,
    project_id: int,
    prompt: str,
    generate_fn: Callable[[], Any],
) -> Generation:
    """Tạo bản ghi pending, gọi hàm sinh, rồi đóng trạng thái success hoặc failed.

    generate_fn là chỗ gắn Gemini sau này. Nếu hàm đó ném lỗi, bản ghi
    không được để ở pending. raw_json_data của project chỉ đổi khi thành công.
    """
    generation = create_pending_generation(db, project_id, prompt)
    try:
        result = generate_fn()
        return mark_generation_success(db, generation.id, result)
    except Exception as exc:
        db.rollback()
        return mark_generation_failed(db, generation.id, str(exc))
