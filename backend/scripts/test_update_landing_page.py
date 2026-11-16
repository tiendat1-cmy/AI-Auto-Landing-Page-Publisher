"""Script kiểm thử tự động toàn diện cho:
  [BE] API cập nhật landing page (PUT /projects/{id} và /api/v1/projects/{id})
  - Sửa text, giá, link social
  - Render lại HTML
  - Push commit mới lên GitHub (nhận commit_sha)
  - Lưu phiên bản mới vào project_versions
"""

import asyncio
import os
import sys

# Thêm thư mục backend vào sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import HTTPException
from api.projects import api_get_project, api_preview_landing_page, api_update_landing_page
from schemas.project import ProjectUpdateRequest
from services.version_service import list_versions

async def run_async_tests():
    print("=" * 65)
    print("BẮT ĐẦU KIỂM THỬ: [BE] API CẬP NHẬT LANDING PAGE")
    print("=" * 65)

    project_id = 1

    # 1. Test GET /api/v1/projects/{id} (Điền sẵn dữ liệu cũ cho Form)
    print("\n[TEST 1] GET /api/v1/projects/{id} - Lấy dữ liệu dự án để điền vào Form:")
    project_data = await api_get_project(project_id)
    assert project_data is not None
    print(f" -> OK! Đã lấy project #{project_data['id']}: {project_data['product_name']}")
    print(f"    Giá hiện tại: {project_data.get('price')}")
    print(f"    Chiến dịch: {project_data.get('campaign_name')}")

    # 2. Test POST /api/v1/projects/{id}/preview (Xem trước trước khi lưu)
    print("\n[TEST 2] POST /api/v1/projects/{id}/preview - Xem trước HTML (chưa lưu DB):")
    preview_req = ProjectUpdateRequest(
        campaign_name="Siêu Giảm Giá Mùa Đông",
        product_name="Tai Nghe Không Dây Chống Ồn AI Pro Max",
        product_description="Tai nghe chống ồn chủ động cao cấp thế hệ mới.",
        price=899000,
        color_theme="#059669",
        facebook_url="https://facebook.com/aipro.audio",
        tiktok_url="https://tiktok.com/@aipro.audio",
        instagram_url="https://instagram.com/aipro.audio",
    )
    res_prev = await api_preview_landing_page(project_id, preview_req)
    html_prev = res_prev.rendered_html
    assert "Tai Nghe Không Dây Chống Ồn AI Pro Max" in html_prev
    assert "899.000 ₫" in html_prev
    assert "https://facebook.com/aipro.audio" in html_prev
    assert "https://tiktok.com/@aipro.audio" in html_prev
    assert "https://instagram.com/aipro.audio" in html_prev
    assert "#059669" in html_prev
    print(f" -> OK! Render xem trước HTML thành công ({len(html_prev)} ký tự).")

    # 3. Lấy số lượng versions hiện tại trước khi PUT
    versions_before = list_versions(project_id)
    count_before = len(versions_before)
    print(f"\n[INFO] Số phiên bản hiện tại của project #{project_id}: {count_before}")

    # 4. Test PUT /api/v1/projects/{id} (Sửa text, giá, link social -> render HTML -> push GitHub -> lưu version mới)
    print("\n[TEST 3] PUT /api/v1/projects/{id} - Thực hiện quy trình cập nhật:")
    update_req = ProjectUpdateRequest(
        campaign_name="Flash Sale Ngày Nhà Giáo 2026",
        product_name="Smart Watch AI Ultra Edition",
        product_description="Đồng hồ thông minh theo dõi sức khỏe và giấc ngủ với trợ lý AI.",
        price=1250000,
        color_theme="#e11d48",
        image_url="https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800",
        facebook_url="https://facebook.com/smartwatch.ultra",
        tiktok_url="https://tiktok.com/@smartwatch.ultra",
        instagram_url="https://instagram.com/smartwatch.ultra",
        repo_url="https://github.com/tiendat1-cmy/demo-landing-page",
        github_pages_url="https://tiendat1-cmy.github.io/demo-landing-page/",
        change_summary="Cập nhật giá 1.250.000đ, đổi text Smart Watch và thêm social links",
        commit_message="feat: update landing page text, price, and social links",
    )

    put_data = await api_update_landing_page(project_id, update_req)

    print(" -> OK! Phản hồi từ PUT /projects/{id}:")
    print(f"    Message: {put_data['message']}")
    print(f"    Version mới: v{put_data['version_number']} (version_id: {put_data['version_id']})")
    print(f"    Commit SHA: {put_data['commit_sha']}")
    print(f"    Độ dài HTML rendered: {len(put_data['rendered_html'])} ký tự")

    # Kiểm tra tính chính xác của dữ liệu đã lưu
    proj_updated = put_data["project"]
    assert proj_updated["product_name"] == "Smart Watch AI Ultra Edition"
    assert proj_updated["campaign_name"] == "Flash Sale Ngày Nhà Giáo 2026"
    assert float(proj_updated["price"]) == 1250000.0
    assert proj_updated["facebook_url"] == "https://facebook.com/smartwatch.ultra"
    assert proj_updated["tiktok_url"] == "https://tiktok.com/@smartwatch.ultra"
    assert proj_updated["instagram_url"] == "https://instagram.com/smartwatch.ultra"
    assert proj_updated["color_theme"] == "#e11d48"

    # Kiểm tra HTML rendered chứa đúng text, giá và link social
    rendered_html = put_data["rendered_html"]
    assert "Smart Watch AI Ultra Edition" in rendered_html
    assert "Flash Sale Ngày Nhà Giáo 2026" in rendered_html
    assert "1.250.000 ₫" in rendered_html
    assert "https://facebook.com/smartwatch.ultra" in rendered_html
    assert "https://tiktok.com/@smartwatch.ultra" in rendered_html
    assert "https://instagram.com/smartwatch.ultra" in rendered_html
    assert "#e11d48" in rendered_html

    # 5. Kiểm tra danh sách versions tăng lên và lưu đúng commit_sha
    print("\n[TEST 4] Kiểm tra bảng project_versions có phiên bản mới:")
    versions_after = list_versions(project_id)
    assert len(versions_after) == count_before + 1, f"Expected {count_before + 1} versions, got {len(versions_after)}"
    latest_ver = versions_after[0]
    print(f" -> OK! Version mới nhất: v{latest_ver['version_number']}")
    print(f"    Commit SHA: {latest_ver['commit_sha']}")
    print(f"    Ghi chú: {latest_ver['change_summary']}")
    assert latest_ver["version_number"] == put_data["version_number"]
    assert latest_ver["commit_sha"] == put_data["commit_sha"]

    # 6. Test cập nhật lần tiếp theo với giá khác
    print("\n[TEST 5] Kiểm tra cập nhật lần 2:")
    second_req = ProjectUpdateRequest(
        price=1190000,
        change_summary="Giảm giá đặc biệt cuối tuần còn 1.190.000đ",
    )
    second_res = await api_update_landing_page(project_id, second_req)
    print(f" -> OK! Version mới: v{second_res['version_number']}, Giá mới: {second_res['project']['price']}")
    assert float(second_res["project"]["price"]) == 1190000.0
    assert "1.190.000 ₫" in second_res["rendered_html"]

    # 7. Test project không tồn tại -> 404
    print("\n[TEST 6] Kiểm tra lỗi 404 khi project không tồn tại:")
    try:
        await api_update_landing_page(999999, ProjectUpdateRequest(product_name="Fake"))
        raise AssertionError("Phải raise HTTPException 404")
    except HTTPException as exc:
        assert exc.status_code == 404
        print(f" -> OK! Trả về đúng HTTP {exc.status_code} ({exc.detail})")

    print("\n" + "=" * 65)
    print("TẤT CẢ CÁC BÀI TEST ĐÃ VƯỢT QUA XUẤT SẮC (ALL PASSED)!")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(run_async_tests())
