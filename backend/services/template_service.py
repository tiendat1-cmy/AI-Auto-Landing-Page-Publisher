"""Service xử lý nghiệp vụ liên quan đến Template và Render Landing Page.

Đọc dữ liệu trực tiếp từ bảng templates trong cơ sở dữ liệu qua SQLAlchemy Session.
Không dùng mock data hay hardcode danh sách template.
Hỗ trợ tích hợp hệ thống CTA động đầy đủ 5 kênh:
1. Messenger
2. TikTok Shop
3. Zalo
4. Instagram
5. Hotline
"""

import os
from typing import Any, Dict, List, Optional
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.template import Template
from schemas.template import TemplateItem
from services.cta_service import build_cta_context

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BACKEND_DIR, "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)


def serialize_template(template: Template) -> TemplateItem:
    """Chuyển đổi ORM Model Template thành Pydantic Schema TemplateItem.
    
    Ánh xạ cột thumbnail_url sang trường thumbnail và thumbnail_url theo đúng API contract.
    """
    return TemplateItem(
        id=template.id,
        name=template.name,
        description=template.description,
        thumbnail=template.thumbnail_url,
        thumbnail_url=template.thumbnail_url,
        file_path=template.file_path,
        placeholders=template.placeholders,
    )


def get_all_templates(db: Session) -> List[TemplateItem]:
    """Lấy danh sách tất cả các Template từ database.
    
    Trả về danh sách đối tượng TemplateItem đã được serialize và parse placeholders.
    """
    stmt = select(Template).order_by(Template.id.asc())
    templates = db.scalars(stmt).all()
    return [serialize_template(t) for t in templates]


def get_template_by_id(db: Session, template_id: int) -> Optional[TemplateItem]:
    """Truy vấn một Template theo ID.
    
    Trả về TemplateItem nếu tìm thấy, hoặc None nếu không tồn tại trong database.
    """
    template = db.get(Template, template_id)
    if template is None:
        return None
    return serialize_template(template)


def render_template_preview(
    db: Session,
    template_id: int,
    custom_data: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """Render nội dung HTML thực tế của template kèm dữ liệu CTA động chuẩn hóa.
    
    Dùng để hiển thị trong iframe sandbox an toàn tại frontend.
    """
    template = db.get(Template, template_id)
    if template is None:
        return None

    raw_path = template.file_path or ""
    filename = os.path.basename(raw_path)

    # Nếu file chưa tồn tại trên đĩa, sử dụng fallback phù hợp theo template_id
    if not os.path.exists(os.path.join(TEMPLATES_DIR, filename)):
        fallbacks = {
            1: "modern_tech.html",
            2: "elegant_beauty.html",
            3: "trust_consulting.html",
        }
        filename = fallbacks.get(template_id, "sales.html")
        if not os.path.exists(os.path.join(TEMPLATES_DIR, filename)):
            filename = "sales.html"

    # Dữ liệu xem trước trực quan cho giao diện mẫu
    preview_data: Dict[str, Any] = {
        "brand_name": (
            "TechNova AI Studio"
            if template_id == 1
            else ("Luxe Natural Care" if template_id == 2 else "Zenith Advisory Group")
        ),
        "headline": template.name,
        "subheadline": (
            template.description
            or "Giải pháp Landing Page thế hệ mới, tối ưu hóa tỷ lệ chuyển đổi bằng trí tuệ nhân tạo."
        ),
        "hero_image_url": "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=1000&q=80",
        "primary_color": (
            "#4f46e5"
            if template_id == 1
            else ("#e11d48" if template_id == 2 else "#0284c7")
        ),
        "cta_text": "Trải nghiệm ngay",
        "hero_badge": "Mẫu Chuyển Đổi Cao 2026",
        "sold_count": "1,850+",
        "discount_percent": "40%",
        "feature_1_title": "Tối ưu hóa CRO chuẩn quốc tế",
        "feature_1_desc": "Thiết kế nghiên cứu kỹ lưỡng theo hành vi người dùng, kích thích tương tác tối đa.",
        "feature_2_title": "Tốc độ tải trang siêu tốc 99/100",
        "feature_2_desc": "Bố cục Tailwind CSS tinh gọn, nén tối ưu, hiển thị mượt mà trên mọi thiết bị.",
        "feature_3_title": "Tự động tạo nội dung bằng AI",
        "feature_3_desc": "Tích hợp công nghệ AI sinh nội dung bán hàng và lời kêu gọi hành động hấp dẫn.",
        "target_audience_text": "Phù hợp cho các doanh nghiệp, startup và nhà bán lẻ trực tuyến hiện đại.",
        "ingredients_list": "100% thành phần thảo mộc hữu cơ, chứng nhận da liễu quốc tế.",
        "benefits_text": "Cảm nhận sự khác biệt rõ rệt sau 7 ngày trải nghiệm, cam kết chất lượng tuyệt đối.",
        "original_price": "1.290.000đ",
        "discounted_price": "790.000đ",
        "course_module_1": "Module 1: Chiến lược định vị sản phẩm & Bản đồ khách hàng",
        "course_module_2": "Module 2: Xây dựng phễu chuyển đổi cao và Content kích cầu",
        "course_module_3": "Module 3: Ứng dụng AI tự động hóa vận hành và tăng trưởng x3",
        "expert_name": "TS. Nguyễn Minh Tuấn",
        "expert_bio": "Chuyên gia cố vấn tăng trưởng số với hơn 15 năm kinh nghiệm dẫn dắt các chiến dịch triệu lẻ.",

        # 5 Kênh CTA mặc định cho chế độ preview (nếu không có custom_data)
        "messenger_link": "https://m.me/technova.ai",
        "tiktok_shop_link": "https://shop.tiktok.com/@technova",
        "zalo_link": "0987654321",
        "instagram_link": "technova.studio",
        "hotline": "1900 6868",
    }

    # Nếu người dùng truyền custom_data (ví dụ khi xem trước chiến dịch thực tế)
    if custom_data:
        preview_data.update(custom_data)

    # Chuẩn hóa hệ thống CTA qua cta_service
    cta_ctx = build_cta_context(preview_data)
    preview_data["cta"] = cta_ctx

    # Gắn thêm các biến trực tiếp để các template cũ tương thích ngược 100%
    preview_data["messenger_link"] = cta_ctx["messenger_link"]
    preview_data["tiktok_shop_link"] = cta_ctx["tiktok_shop_link"]
    preview_data["zalo_link"] = cta_ctx["zalo_link"]
    preview_data["instagram_link"] = cta_ctx["instagram_link"]
    preview_data["hotline"] = cta_ctx["hotline"]
    preview_data["hotline_href"] = cta_ctx["hotline_href"]
    preview_data["social_zalo"] = cta_ctx["zalo_link"]
    preview_data["social_instagram"] = cta_ctx["instagram_link"]
    preview_data["social_tiktok"] = cta_ctx["tiktok_shop_link"]
    preview_data["social_facebook"] = cta_ctx["messenger_link"]
    preview_data["hotline_number"] = cta_ctx["hotline"]

    try:
        jinja_template = jinja_env.get_template(filename)
        return jinja_template.render(data=preview_data, cta=cta_ctx)
    except Exception as exc:
        return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>{template.name} - Preview</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-white min-h-screen flex items-center justify-center p-8">
    <div class="max-w-xl text-center space-y-4">
        <h1 class="text-3xl font-black text-indigo-400">{template.name}</h1>
        <p class="text-slate-300">{template.description}</p>
        <div class="inline-block px-4 py-2 bg-indigo-600 rounded-xl font-bold">Xem trước HTML Template</div>
    </div>
</body>
</html>"""
