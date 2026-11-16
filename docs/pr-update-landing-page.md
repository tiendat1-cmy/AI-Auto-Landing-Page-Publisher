# Pull Request: [BE] API cập nhật landing page & [FE] Form chỉnh sửa landing page

## 1. Tổng quan công việc
Thực hiện trọn vẹn 2 yêu cầu trong sprint:
1. **[BE] API cập nhật landing page**:
   - `PUT /projects/{id}` và `PUT /api/v1/projects/{id}`: Nhận dữ liệu chỉnh sửa text, giá sản phẩm, liên kết mạng xã hội (Facebook, TikTok, Instagram), màu chủ đạo, link ảnh.
   - Render lại mã nguồn HTML hoàn chỉnh dựa trên dữ liệu cập nhật (`services/template_service.py`).
   - Push commit mới lên GitHub (gọi GitHub Contents API qua `services/github_service.py` để lấy SHA file cũ và tạo commit mới, trả về `commit_sha`).
   - Lưu phiên bản mới vào bảng `project_versions` (Append-only) với `commit_sha` và `change_summary`.
   - Cung cấp thêm API `GET /api/v1/projects/{id}` để điền dữ liệu cũ vào Form và `POST /api/v1/projects/{id}/preview` để render xem trước tức thì mà không lưu vào DB.
2. **[FE] Form chỉnh sửa landing page**:
   - Giao diện form (`frontend/pages/edit-project.html` & `frontend/index.html`) thiết kế hiện đại, chia đôi màn hình (Split-screen) với Tailwind CSS.
   - Tự động gọi API lấy và điền sẵn dữ liệu cũ của dự án vào các ô nhập liệu.
   - Tính năng **Xem trước trực tiếp (Live Preview)**: tự động cập nhật bản render trong iframe ngay khi người dùng gõ / chỉnh sửa (hỗ trợ chuyển đổi giao diện Desktop, Tablet, Mobile).
   - Nút **"Lưu & Cập nhật Website"**: gửi PUT request, hiển thị trạng thái loading, và mở modal thông báo thành công hiển thị số phiên bản mới (`v...`), `commit_sha`, link tới GitHub Pages và lịch sử versions.

---

## 2. Chi tiết các file thay đổi & tạo mới

### Backend:
| File | Loại | Mô tả |
|---|---|---|
| `backend/api/projects.py` | Tạo mới | Định nghĩa router cho các endpoints: `GET /projects/{id}`, `PUT /projects/{id}`, `POST /projects/{id}/preview`, `GET /projects` |
| `backend/schemas/project.py` | Tạo mới | Các Pydantic schema: `ProjectUpdateRequest`, `ProjectResponse`, `ProjectUpdateResponse`, `ProjectPreviewResponse` |
| `backend/services/project_service.py` | Tạo mới | Nghiệp vụ cập nhật DB `projects`, kích hoạt render HTML, gọi push commit GitHub và ghi bản ghi `project_versions` |
| `backend/services/template_service.py` | Tạo mới | Render toàn bộ cấu trúc HTML landing page với Tailwind CSS, responsive, tối ưu chuyển đổi |
| `backend/services/github_service.py` | Tạo mới | Tương tác GitHub REST API (v3) tạo/cập nhật file `index.html` và sinh commit SHA |
| `backend/main.py` | Cập nhật | Nhúng `projects_router`, cấu hình CORS middleware và mount thư mục `frontend` static files |
| `backend/scripts/test_update_landing_page.py` | Tạo mới | Bộ test tự động kiểm thử toàn bộ luồng GET, POST preview, PUT cập nhật, kiểm tra phiên bản và mã lỗi 404 |

### Frontend:
| File | Loại | Mô tả |
|---|---|---|
| `frontend/pages/edit-project.html` | Tạo mới | Giao diện Form chỉnh sửa landing page kèm khung Live Preview xem trước trực tiếp |
| `frontend/js/edit-project.js` | Tạo mới | Script xử lý gọi API lấy dữ liệu cũ, debounce live preview, thay đổi viewport thiết bị, gửi PUT request và hiển thị kết quả |
| `frontend/css/style.css` | Tạo mới | CSS tùy biến giao diện xem trước theo thiết bị (Desktop, Tablet, Mobile) |
| `frontend/index.html` | Cập nhật | Trang chủ hiển thị danh sách các dự án với liên kết nhanh tới Form chỉnh sửa |

---

## 3. Kết quả kiểm thử (Test Results)

Chạy script kiểm thử:
```bash
python backend/scripts/test_update_landing_page.py
```

Kết quả:
```text
=================================================================
BẮT ĐẦU KIỂM THỬ: [BE] API CẬP NHẬT LANDING PAGE
=================================================================

[TEST 1] GET /api/v1/projects/{id} - Lấy dữ liệu dự án để điền vào Form:
 -> OK! Đã lấy project #1: Demo Product
[TEST 2] POST /api/v1/projects/{id}/preview - Xem trước HTML (chưa lưu DB):
 -> OK! Render xem trước HTML thành công (13221 ký tự).
[TEST 3] PUT /api/v1/projects/{id} - Thực hiện quy trình cập nhật:
 -> OK! Phản hồi từ PUT /projects/{id}:
    Message: Cập nhật landing page và tạo phiên bản mới thành công!
    Version mới: v2 (version_id: 2)
    Commit SHA: eae657519038e3b8506aa23aabc175436401c8a4
[TEST 4] Kiểm tra bảng project_versions có phiên bản mới:
 -> OK! Version mới nhất: v2
[TEST 5] Kiểm tra cập nhật lần 2:
 -> OK! Version mới: v3, Giá mới: 1190000.0
[TEST 6] Kiểm tra lỗi 404 khi project không tồn tại:
 -> OK! Trả về đúng HTTP 404 (Project 999999 không tồn tại)

=================================================================
TẤT CẢ CÁC BÀI TEST ĐÃ VƯỢT QUA XUẤT SẮC (ALL PASSED)!
=================================================================
```

---

## 4. Hướng dẫn trải nghiệm trực tiếp trên giao diện

1. Khởi động Backend server:
   ```bash
   cd backend
   ..\.venv\Scripts\uvicorn.exe main:app --reload
   ```
2. Truy cập trình duyệt:
   - Form chỉnh sửa Landing Page: `http://127.0.0.1:8000/edit` hoặc `http://127.0.0.1:8000/frontend/pages/edit-project.html?project_id=1`
   - Dashboard danh sách dự án: `http://127.0.0.1:8000/frontend/`
   - Swagger API Documentation: `http://127.0.0.1:8000/docs`
