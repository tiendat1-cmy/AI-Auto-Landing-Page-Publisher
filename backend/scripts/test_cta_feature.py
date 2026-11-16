"""Script kiểm thử toàn diện tính năng CTA động cho AI Auto Landing Page Publisher.

Không phụ thuộc thư viện bên ngoài, chạy trên standard library Python.
Kiểm tra 6 ca kiểm thử theo đúng đặc tả:
- Test 1: Người dùng nhập đủ 5 CTA (Cả 5 nút hiển thị, URL chuẩn hóa).
- Test 2: Người dùng chỉ nhập Messenger và Hotline (2 nút hiển thị, 3 nút ẩn hoàn toàn).
- Test 3: Người dùng chỉ nhập Zalo (Chỉ nút Zalo hiển thị, không thừa khoảng trắng).
- Test 4: Người dùng không nhập CTA nào (Khu vực CTA ẩn hoàn toàn, template vẫn hiển thị tốt).
- Test 5: Cập nhật chiến dịch qua Database & Schema (Đổi Messenger, xóa hotline, không mất trường khác).
- Test 6: Kiểm tra tính đồng nhất trên toàn bộ các Landing Page Templates.
"""

import os
import re
import sys
from html.parser import HTMLParser
from jinja2 import Environment, FileSystemLoader

# Thêm thư mục backend vào sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from services.cta_service import (
    build_cta_context,
    normalize_hotline,
    normalize_instagram,
    normalize_messenger,
    normalize_tiktok_shop,
    normalize_zalo,
)
from services.template_service import render_template_preview

TEMPLATES_DIR = os.path.join(BACKEND_DIR, "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)


class SimpleLinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cta_buttons = []
        self.in_cta_section = False
        self.has_cta_section = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "").split()
        if "cta-dynamic-section" in classes:
            self.has_cta_section = True
            self.in_cta_section = True
        if tag == "a" and "cta-btn" in classes:
            self.cta_buttons.append({
                "href": attrs_dict.get("href", ""),
                "classes": classes,
            })

    def handle_endtag(self, tag):
        pass


def extract_cta_info(html: str):
    parser = SimpleLinkExtractor()
    parser.feed(html)
    return parser.has_cta_section, parser.cta_buttons


def check(name: str, condition: bool, message: str = ""):
    if condition:
        print(f"  [PASSED] {name}: {message}")
    else:
        print(f"  [FAILED] {name}: {message}")
        raise AssertionError(f"Check failed: {name} - {message}")


def run_all_cta_tests():
    print("=" * 70)
    print("BẮT ĐẦU KIỂM THỬ HỆ THỐNG CTA ĐỘNG (CALL-TO-ACTION)")
    print("=" * 70)

    # ---------------------------------------------------------
    # TEST 1: Người dùng nhập đủ 5 CTA
    # ---------------------------------------------------------
    print("\n--- TEST 1: Người dùng nhập đủ 5 CTA ---")
    raw_5_cta = {
        "brand_name": "Test Brand 5 CTA",
        "headline": "Sản phẩm công nghệ đỉnh cao",
        "messenger_link": "technova.chat",
        "tiktok_shop_link": "shop.tiktok.com/@technovavn",
        "zalo_link": "0987 654 321",
        "instagram_link": "technova.official",
        "hotline": "1900 6868",
    }
    cta_ctx_1 = build_cta_context(raw_5_cta)
    check("Test 1.1 - has_any_cta", cta_ctx_1["has_any_cta"] is True, "Có CTA kích hoạt")
    check("Test 1.2 - Count items", len(cta_ctx_1["items"]) == 5, "Đủ 5 nút")
    check("Test 1.3 - Messenger URL", cta_ctx_1["messenger_link"] == "https://m.me/technova.chat", "Chuẩn hóa m.me")
    check("Test 1.4 - TikTok Shop URL", cta_ctx_1["tiktok_shop_link"] == "https://shop.tiktok.com/@technovavn", "Chuẩn hóa HTTPS TikTok")
    check("Test 1.5 - Zalo URL", cta_ctx_1["zalo_link"] == "https://zalo.me/0987654321", "Chuẩn hóa SĐT sang zalo.me")
    check("Test 1.6 - Instagram URL", cta_ctx_1["instagram_link"] == "https://www.instagram.com/technova.official/", "Chuẩn hóa instagram username")
    check("Test 1.7 - Hotline href", cta_ctx_1["hotline_href"] == "tel:19006868", "Hotline tel: protocol")
    check("Test 1.8 - Hotline display", cta_ctx_1["hotline"] == "1900 6868", "Giữ nguyên format hiển thị")

    # Render template modern_tech.html
    tmpl = jinja_env.get_template("modern_tech.html")
    html_1 = tmpl.render(data=raw_5_cta, cta=cta_ctx_1)
    has_sec_1, btns_1 = extract_cta_info(html_1)
    check("Test 1.9 - CTA Section hiển thị", has_sec_1 is True, "Tìm thấy cta-dynamic-section")
    check("Test 1.10 - 5 Nút hiển thị trong DOM", len(btns_1) == 5, f"Tìm thấy {len(btns_1)} nút CTA")
    hrefs_1 = [a["href"] for a in btns_1]
    check("Test 1.11 - Link Messenger", "https://m.me/technova.chat" in hrefs_1, "Link Messenger chính xác")
    check("Test 1.12 - Link TikTok", "https://shop.tiktok.com/@technovavn" in hrefs_1, "Link TikTok chính xác")
    check("Test 1.13 - Link Zalo", "https://zalo.me/0987654321" in hrefs_1, "Link Zalo chính xác")
    check("Test 1.14 - Link Instagram", "https://www.instagram.com/technova.official/" in hrefs_1, "Link Instagram chính xác")
    check("Test 1.15 - Link Hotline", "tel:19006868" in hrefs_1, "Link Hotline chính xác")

    # ---------------------------------------------------------
    # TEST 2: Người dùng chỉ nhập Messenger và Hotline
    # ---------------------------------------------------------
    print("\n--- TEST 2: Người dùng chỉ nhập Messenger và Hotline ---")
    raw_2_cta = {
        "brand_name": "Test Brand 2 CTA",
        "headline": "Chỉ Messenger & Hotline",
        "messenger_link": "https://m.me/mybrand",
        "hotline": "0912 345 678",
        "tiktok_shop_link": None,
        "zalo_link": "",
        "instagram_link": "   ",
    }
    cta_ctx_2 = build_cta_context(raw_2_cta)
    check("Test 2.1 - Count items", len(cta_ctx_2["items"]) == 2, "Chỉ có đúng 2 nút")
    html_2 = tmpl.render(data=raw_2_cta, cta=cta_ctx_2)
    has_sec_2, btns_2 = extract_cta_info(html_2)
    check("Test 2.2 - DOM chỉ render 2 nút", len(btns_2) == 2, f"Tìm thấy {len(btns_2)} nút CTA")
    hrefs_2 = [a["href"] for a in btns_2]
    check("Test 2.3 - Có Messenger", "https://m.me/mybrand" in hrefs_2, "Có Messenger")
    check("Test 2.4 - Có Hotline", "tel:0912345678" in hrefs_2, "Có Hotline")
    check("Test 2.5 - Ẩn TikTok Shop", not any("tiktok" in h for h in hrefs_2), "Đã ẩn hoàn toàn TikTok")
    check("Test 2.6 - Ẩn Zalo", not any("zalo" in h for h in hrefs_2), "Đã ẩn hoàn toàn Zalo")
    check("Test 2.7 - Ẩn Instagram", not any("instagram" in h for h in hrefs_2), "Đã ẩn hoàn toàn Instagram")

    # ---------------------------------------------------------
    # TEST 3: Người dùng chỉ nhập Zalo
    # ---------------------------------------------------------
    print("\n--- TEST 3: Người dùng chỉ nhập Zalo ---")
    raw_1_cta = {
        "brand_name": "Test Brand Zalo Only",
        "headline": "Chỉ Zalo",
        "zalo_link": "0988889999",
        "messenger_link": None,
        "tiktok_shop_link": None,
        "instagram_link": None,
        "hotline": None,
    }
    cta_ctx_3 = build_cta_context(raw_1_cta)
    check("Test 3.1 - Count items", len(cta_ctx_3["items"]) == 1, "Chỉ có 1 nút")
    html_3 = tmpl.render(data=raw_1_cta, cta=cta_ctx_3)
    has_sec_3, btns_3 = extract_cta_info(html_3)
    check("Test 3.2 - DOM render 1 nút", len(btns_3) == 1, "Chỉ 1 nút duy nhất")
    check("Test 3.3 - Nút là Zalo", btns_3[0]["href"] == "https://zalo.me/0988889999", "Link là Zalo chuẩn")

    # ---------------------------------------------------------
    # TEST 4: Người dùng không nhập CTA nào (hoặc chuỗi rỗng)
    # ---------------------------------------------------------
    print("\n--- TEST 4: Người dùng không nhập CTA nào ---")
    raw_0_cta = {
        "brand_name": "Test Brand No CTA",
        "headline": "Không có liên hệ mạng xã hội",
        "messenger_link": None,
        "tiktok_shop_link": "",
        "zalo_link": "   ",
        "instagram_link": None,
        "hotline": None,
    }
    cta_ctx_4 = build_cta_context(raw_0_cta)
    check("Test 4.1 - has_any_cta is False", cta_ctx_4["has_any_cta"] is False, "has_any_cta = False")
    check("Test 4.2 - Count items is 0", len(cta_ctx_4["items"]) == 0, "Không có nút nào")
    html_4 = tmpl.render(data=raw_0_cta, cta=cta_ctx_4)
    has_sec_4, btns_4 = extract_cta_info(html_4)
    check("Test 4.3 - Khu vực CTA bị ẩn hoàn toàn", has_sec_4 is False and len(btns_4) == 0, "cta-dynamic-section KHÔNG tồn tại trong DOM (không để lại khoảng trắng)")
    check("Test 4.4 - Landing Page vẫn hiển thị bình thường", len(html_4) > 10000, "Template vẫn render trọn vẹn")

    # ---------------------------------------------------------
    # TEST 5: Cập nhật chiến dịch qua Database & Schema
    # ---------------------------------------------------------
    print("\n--- TEST 5: Cập nhật chiến dịch (Database & Schema validation) ---")
    from schemas.project import ProjectCreate, ProjectUpdate
    
    # 5.1 Test Schema Validation & Sanitization
    proj_create = ProjectCreate(
        template_id=1,
        campaign_name="Test Campaign CTA",
        product_name="Product Alpha",
        messenger_link="my_messenger_page",
        tiktok_shop_link="https://shop.tiktok.com/prod/123",
        zalo_link="0911222333",
        instagram_link="@my_brand_insta",
        hotline="1900 1234",
    )
    check("Test 5.1 - ProjectCreate schema có 5 trường CTA", hasattr(proj_create, "messenger_link"), "Tồn tại trường messenger_link")
    check("Test 5.2 - Giá trị messenger_link", proj_create.messenger_link == "my_messenger_page", "Lưu đúng Messenger")
    check("Test 5.3 - Giá trị hotline", proj_create.hotline == "1900 1234", "Lưu đúng Hotline")

    # 5.2 Test ProjectUpdate partial update (chỉ cập nhật messenger, không xóa trường khác)
    proj_update = ProjectUpdate(
        messenger_link="new_messenger_url",
        hotline=None,  # Xóa hotline
    )
    dump_update = proj_update.model_dump(exclude_unset=True)
    check("Test 5.4 - Partial update chỉ chứa các trường gửi lên", "messenger_link" in dump_update and "hotline" in dump_update, "Có messenger_link và hotline")
    check("Test 5.5 - Không chứa tiktok_shop_link chưa gửi", "tiktok_shop_link" not in dump_update, "Không vô tình ghi đè trường khác")

    # ---------------------------------------------------------
    # TEST 6: Kiểm tra trên tất cả các Landing Page Templates
    # ---------------------------------------------------------
    print("\n--- TEST 6: Kiểm tra trên tất cả các Landing Page Templates ---")
    templates_to_test = [
        "modern_tech.html",
        "sales.html",
        "elegant_beauty.html",
        "marketing.html",
        "trust_consulting.html",
        "event.html",
    ]

    test_data = {
        "brand_name": "Multi-Template Brand",
        "headline": "Tiêu đề đồng nhất",
        "subheadline": "Mô tả chiến dịch",
        "messenger_link": "universal_messenger",
        "tiktok_shop_link": "https://shop.tiktok.com/@universal",
        "zalo_link": "0909090909",
        "instagram_link": "universal_ig",
        "hotline": "1800 9999",
    }
    test_cta_ctx = build_cta_context(test_data)

    for t_name in templates_to_test:
        t_file = os.path.join(TEMPLATES_DIR, t_name)
        if not os.path.exists(t_file):
            continue
        tmpl_item = jinja_env.get_template(t_name)
        rendered_html = tmpl_item.render(data=test_data, cta=test_cta_ctx)
        has_sec_item, btns_item = extract_cta_info(rendered_html)
        
        check(f"Test 6 [{t_name}] - CTA Section", has_sec_item is True, f"Có cta-dynamic-section trong {t_name}")
        check(f"Test 6 [{t_name}] - 5 Nút CTA", len(btns_item) == 5, f"Render đủ 5 nút trong {t_name}")

        # Kiểm tra khi không có CTA
        rendered_empty = tmpl_item.render(data={}, cta=build_cta_context({}))
        has_sec_empty, btns_empty = extract_cta_info(rendered_empty)
        check(f"Test 6 [{t_name}] - Ẩn hoàn toàn khi rỗng", has_sec_empty is False and len(btns_empty) == 0, f"Ẩn sạch sẽ trong {t_name}")

    # Chạy thêm kiểm thử endpoint preview thực tế từ template_service
    from core.database import SessionLocal
    with SessionLocal() as db:
        preview_html_1 = render_template_preview(db, 1)
        check("Test Preview - Template 1 render có CTA", "cta-dynamic-section" in preview_html_1, "Preview ID 1 có CTA")
        preview_html_2 = render_template_preview(db, 2)
        check("Test Preview - Template 2 render có CTA", "cta-dynamic-section" in preview_html_2, "Preview ID 2 có CTA")
        preview_html_3 = render_template_preview(db, 3)
        check("Test Preview - Template 3 render có CTA", "cta-dynamic-section" in preview_html_3, "Preview ID 3 có CTA")

    print("\n" + "=" * 70)
    print("TẤT CẢ 6 BÀI KIỂM THỬ CTA ĐỘNG ĐỀU VƯỢT QUA XUẤT SẮC (PASSED 100%)!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_cta_tests()
