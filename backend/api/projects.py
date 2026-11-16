import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, get_owned_project
from schemas.project import ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("")
async def list_my_projects(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            text("SELECT * FROM projects WHERE user_id = :user_id ORDER BY updated_at DESC"),
            {"user_id": current_user["id"]},
        )
        .mappings()
        .all()
    )
    return {"success": True, "data": [dict(r) for r in rows]}


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
    return {"success": True, "data": dict(row)}


@router.get("/{project_id}")
async def get_project_detail(
    project: dict = Depends(get_owned_project),
):
    return {"success": True, "data": project}


@router.put("/{project_id}")
@router.patch("/{project_id}")
async def update_project(
    payload: ProjectUpdate,
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return {"success": True, "data": project}

    if "template_id" in update_data and update_data["template_id"] is not None:
        template = db.execute(
            text("SELECT id FROM templates WHERE id = :id"),
            {"id": update_data["template_id"]},
        ).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template khong ton tai")

    if "raw_json_data" in update_data and update_data["raw_json_data"] is not None:
        update_data["raw_json_data"] = json.dumps(update_data["raw_json_data"], ensure_ascii=False)

    set_clauses = ", ".join(f"{col} = :{col}" for col in update_data.keys())
    update_data["id"] = project["id"]

    db.execute(
        text(f"UPDATE projects SET {set_clauses} WHERE id = :id"),
        update_data,
    )
    db.commit()

    row = (
        db.execute(text("SELECT * FROM projects WHERE id = :id"), {"id": project["id"]})
        .mappings()
        .one()
    )
    return {"success": True, "data": dict(row)}


@router.delete("/{project_id}")
async def delete_project(
    project: dict = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    db.execute(text("DELETE FROM projects WHERE id = :id"), {"id": project["id"]})
    db.commit()
    return {"success": True, "message": "Đã xóa landing page thành công."}


@router.post("/{project_id}/deploy")
async def deploy_project_guard(
    project: dict = Depends(get_owned_project),
):
    """
    Endpoint deploy đã được khóa bằng get_owned_project (chỉ chủ sở hữu mới được deploy).
    Sẽ nối với github_service khi hoàn thiện luồng xuất bản.
    """
    return {
        "success": True,
        "message": "Xác thực quyền sở hữu hợp lệ để triển khai landing page.",
        "data": {"project_id": project["id"], "status": project["status"]},
    }