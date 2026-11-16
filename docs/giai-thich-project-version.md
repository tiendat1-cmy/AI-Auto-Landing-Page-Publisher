# Giải thích các file liên quan `projects` & `project_versions` (backend)

Tài liệu này giải thích từng file trong `backend/` có liên quan tới **project** và **project_version**: chúng làm gì, nằm ở tầng nào, ai gọi ai, và những điểm cần lưu ý.

## 1. Sơ đồ tổng quan

```
Client (Swagger / frontend)
        │  HTTP JSON
        ▼
backend/api/versions.py          ← Router, validate đầu vào, map lỗi → HTTP status
        │  gọi hàm Python
        ▼
backend/services/version_service.py   ← Nghiệp vụ + câu lệnh SQL (PyMySQL)
        │  pymysql
        ▼
MySQL: projects  ◄──FK──  project_versions
        ▲
        │  tạo bảng
backend/scripts/init_db.py       ← Migration + seed

backend/schemas/version.py       ← "Hợp đồng" dữ liệu request/response (Pydantic)
backend/models/version.py        ← Model SQLAlchemy (hiện CHƯA được dùng)
backend/main.py                  ← Đăng ký router vào FastAPI app
```

## 2. Bảng tóm tắt file

| File | Tầng | Vai trò | Có dùng thực tế? |
|---|---|---|---|
| `api/versions.py` | Controller | 4 endpoint REST cho version | ✅ |
| `services/version_service.py` | Service / DAO | Toàn bộ logic + SQL | ✅ |
| `schemas/version.py` | Validation | Pydantic request/response | ✅ |
| `models/version.py` | ORM | Model SQLAlchemy `ProjectVersion` | ❌ (chưa nối) |
| `scripts/init_db.py` | Migration | Tạo DB/bảng + seed user | ✅ |
| `main.py` | Bootstrap | include router | ✅ |
| `core/config.py` | Config | Đọc `.env` (DB_HOST, DB_NAME…) | ✅ |
| `services/template_service.py`, `github_service.py`, `gemini_service.py` | — | File rỗng (0 byte), chưa có code | ❌ |

> **Lưu ý lớn:** không có file nào tên `project.py`. Bảng `projects` hiện **không có model, không có schema, không có API**. Nó chỉ được tạo trong `init_db.py` và được truy vấn thô trong `version_service.py`. Mọi thao tác CRUD project hiện phải làm bằng SQL tay.

## 3. Chi tiết từng file

### 3.1 `backend/scripts/init_db.py` — tạo cấu trúc DB

Kết nối MySQL bằng tài khoản trong `core/config.py`, sau đó chạy lần lượt 5 bước:

| Bước | Bảng | Ghi chú |
|---|---|---|
| 1 | `CREATE DATABASE` + `USE` | `utf8mb4_unicode_ci` |
| 2 | `users` | email UNIQUE, mật khẩu bcrypt |
| 3 | `templates` → `projects` | `projects` FK tới `users`, `templates` |
| 4 | `project_versions` | FK tới `projects`, `users` |
| 5 | Seed 3 user | `INSERT IGNORE` nên chạy lại không nhân đôi |

Hai điểm quan trọng:

- **Thứ tự bắt buộc**: `project_versions` phải tạo **sau** `projects`, vì có `FOREIGN KEY (project_id) REFERENCES projects(id)`. Đảo thứ tự → MySQL báo lỗi `(1824) Failed to open the referenced table 'projects'` hoặc `(1215) Cannot add foreign key constraint`.
- Hàm `hash_password()` cắt mật khẩu theo **72 byte UTF-8** (không phải 72 ký tự), vì bcrypt giới hạn 72 byte.

Script này **idempotent** nhờ `CREATE TABLE IF NOT EXISTS`, nhưng **không** alter bảng đã tồn tại — nếu schema đổi, phải drop database hoặc viết migration mới.

### 3.2 `backend/schemas/version.py` — hợp đồng dữ liệu

Chỉ khai báo Pydantic, không chứa logic:

| Class | Dùng cho | Trường chính |
|---|---|---|
| `VersionCreateRequest` | Body của POST | `html_snapshot` (bắt buộc, `min_length=1`), `json_content`, `commit_sha` (≤40), `change_summary` (≤255) |
| `VersionListItemResponse` | Item trong GET list | `id`, `version_number`, `change_summary`, `commit_sha`, `created_by`, `created_at` |
| `VersionDetailResponse` | GET detail + POST response | Kế thừa trên, thêm `project_id`, `json_content`, `html_snapshot` |
| `VersionRestoreResponse` | POST restore | `message`, `restored_from_version`, `new_version` |

Vai trò thực tế: FastAPI dùng các class này để **validate body** và **lọc bớt field** khi trả về (nhờ `response_model`). Ví dụ `GET list` không trả `html_snapshot` dù service có thể lấy được — đây là chủ ý để giảm payload.

Điểm nhỏ: `class Config: from_attributes = True` là cú pháp Pydantic v1-style; với Pydantic v2 nên là `model_config = ConfigDict(from_attributes=True)`. Hiện không lỗi vì response được build từ `dict`, không phải ORM object.

### 3.3 `backend/services/version_service.py` — nơi chứa toàn bộ nghiệp vụ

Đây là file quan trọng nhất. Dùng **PyMySQL trực tiếp** (không ORM), cursor dạng `DictCursor` nên kết quả là `dict` thay vì tuple.

**Hàm phụ (private):**

- `_get_connection(autocommit)` — mở kết nối tới DB trong `settings`. Ghi (INSERT) dùng `autocommit=False` để transaction hoạt động.
- `_require_project(cursor, project_id)` — `SELECT * FROM projects WHERE id = %s`; không có thì `raise ValueError("Project X không tồn tại")`. Đây chính là lý do API trả **404** khi `project_id` sai.
- `_next_version_number(cursor, project_id)` — `SELECT COALESCE(MAX(version_number),0) ... FOR UPDATE`, trả `MAX + 1`.

**Hàm nghiệp vụ (map đúng 3 user story):**

| Hàm | US | Việc làm |
|---|---|---|
| `create_version(...)` | US-06 | Kiểm tra project → tính `version_number` → `INSERT` → commit → đọc lại bản ghi vừa tạo |
| `list_versions(project_id)` | US-07 | Kiểm tra project → `SELECT` các cột rút gọn, `ORDER BY version_number DESC` |
| `get_version_detail(project_id, version_id)` | US-07 | `SELECT` đầy đủ theo `id` **và** `project_id`; trả `None` nếu không khớp |
| `restore_version(project_id, version_id, created_by)` | US-08 | Lấy version cũ → tạo version **mới** copy `html_snapshot` / `json_content`, `change_summary = "Khôi phục từ phiên bản X"` |

**Cơ chế Append-only:** không có `UPDATE`/`DELETE` nào trên `project_versions`. "Khôi phục" = thêm bản ghi mới, lịch sử cũ giữ nguyên. Nhờ vậy luôn truy vết được.

**Chống trùng `version_number`:** ràng buộc kép
1. `UNIQUE (project_id, version_number)` ở DB (`uq_project_version`)
2. `SELECT ... FOR UPDATE` khi tính số kế tiếp

Nếu hai request đồng thời lọt qua, request sau sẽ bị `pymysql.IntegrityError` → API map thành **409**.

### 3.4 `backend/api/versions.py` — router HTTP

`APIRouter(prefix="/api/v1/projects", tags=["Project Versions"])`, khai báo 4 endpoint:

| Method + Path | Hàm | Status thành công |
|---|---|---|
| `POST /{project_id}/versions` | `api_create_version` | 201 |
| `GET /{project_id}/versions` | `api_list_versions` | 200 |
| `GET /{project_id}/versions/{version_id}` | `api_get_version` | 200 |
| `POST /{project_id}/versions/{version_id}/restore` | `api_restore_version` | 201 |

Cách map lỗi:

| Tình huống | Xử lý |
|---|---|
| Project không tồn tại | `ValueError` có chuỗi `"không tồn tại"` → **404** |
| `html_snapshot` rỗng | `ValueError` khác → **422** |
| Trùng `version_number` | `pymysql.IntegrityError` → **409** |
| Lỗi DB khác (sai mật khẩu, mất bảng…) | Không bắt → **500** |

Hai điểm đáng chú ý:

- `created_by=None` hard-code kèm `# TODO: lấy từ get_current_user khi merge nhánh auth` → hiện mọi version đều không có người tạo.
- Việc phân biệt 404/422 dựa vào **so khớp chuỗi** `if "không tồn tại" in str(exc)` — khá mong manh, nên đổi sang exception riêng (vd. `ProjectNotFoundError`).

### 3.5 `backend/models/version.py` — model SQLAlchemy (chưa hoạt động)

Định nghĩa `class ProjectVersion(Base)` với `__tablename__ = "project_versions"`, đầy đủ cột + `UniqueConstraint` + `Index`, khớp DDL trong `init_db.py`.

Nhưng file này **hiện không được import ở đâu cả**. Lý do:

- Nó cần `from core.database import Base`, mà `core/database.py` **chưa tồn tại**, nên rơi vào nhánh `except ImportError` và tự tạo `Base` stub.
- Docstring của file ghi rõ: *"Hiện tại API vẫn dùng PyMySQL trực tiếp"*.

→ Đây là code chuẩn bị cho tương lai. Đừng sửa DDL ở `init_db.py` mà quên file này (và ngược lại), nếu không hai bên sẽ lệch schema.

**Một điểm lệch hiện tại:** model khai báo `html_snapshot` là `Text` (tối đa 64 KB), còn DB là `LONGTEXT` (4 GB). Nếu chuyển sang dùng ORM, nên đổi thành `LONGTEXT`/`Text(length=2**32-1)` cho khớp.

### 3.6 `backend/main.py` — nơi nối mọi thứ

```python
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(versions_router)
```

Chỉ 3 dòng này khiến các endpoint ở trên xuất hiện trong Swagger `/docs`. File cũng serve `GET /` bằng Jinja2 (`templates/index.html`).

### 3.7 `backend/core/config.py` — cấu hình

Đọc `.env` qua `python-dotenv`, cung cấp `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `GEMINI_API_KEY`, `GITHUB_TOKEN`. Cả `init_db.py`, `api/auth.py`, `version_service.py` đều dùng chung object `settings` này — sửa một chỗ là đổi toàn bộ kết nối.

⚠️ Đừng commit mật khẩu thật vào `DB_PASSWORD` mặc định trong file này; hãy để rỗng và dùng `.env`.

## 4. Cấu trúc dữ liệu

### `projects` — "dự án landing page"

| Nhóm cột | Cột |
|---|---|
| Định danh | `id` (PK) |
| Sở hữu | `user_id` → `users(id)` `ON DELETE CASCADE` |
| Mẫu | `template_id` → `templates(id)` |
| Nội dung | `campaign_name`, `product_name`, `product_description`, `price`, `image_url`, `color_theme` |
| Kênh MXH | `facebook_url`, `tiktok_url`, `instagram_url` |
| Deploy | `repo_url`, `github_pages_url`, `status` (mặc định `'draft'`) |
| Dữ liệu gốc | `raw_json_data` (JSON) |
| Thời gian | `created_at`, `updated_at` (auto update) |

### `project_versions` — lịch sử snapshot

| Cột | Ý nghĩa |
|---|---|
| `id` | PK, dùng làm `version_id` trên URL |
| `project_id` | → `projects(id)` `ON DELETE CASCADE` (xoá project là xoá sạch version) |
| `version_number` | Số thứ tự **trong từng project**, bắt đầu từ 1 |
| `json_content` | JSON cấu trúc trang (nullable) |
| `html_snapshot` | HTML đã render (LONGTEXT, bắt buộc) |
| `commit_sha` | SHA commit khi deploy (nullable) |
| `change_summary` | Mô tả thay đổi (≤255) |
| `created_by` | → `users(id)` `ON DELETE SET NULL` (xoá user vẫn giữ lịch sử) |
| `created_at` | Thời điểm tạo bản ghi |

Ràng buộc: `UNIQUE (project_id, version_number)` + index `ix_project_versions_project_id`.

### Quan hệ

```
users (1) ──< (N) projects (1) ──< (N) project_versions (N) >── (1) users
```

- 1 project có nhiều version; 1 version thuộc đúng 1 project.
- 1 version có thể không có `created_by` (NULL).

## 5. Luồng xử lý 4 use case

**US-06 — Lưu version mới** (`POST /api/v1/projects/1/versions`)

```
Pydantic validate body
  → create_version()
    → _require_project()        # 404 nếu project sai
    → _next_version_number()    # MAX+1, có FOR UPDATE
    → INSERT project_versions
    → COMMIT
    → get_version_detail()      # trả bản ghi đầy đủ
  → response_model lọc field → 201
```

**US-07a — Danh sách** (`GET .../versions`): kiểm tra project → `SELECT` cột rút gọn → `ORDER BY version_number DESC` → 200.

**US-07b — Chi tiết** (`GET .../versions/{id}`): `SELECT * WHERE id=? AND project_id=?` → không thấy thì **404** (không phân biệt "không tồn tại" và "thuộc project khác").

**US-08 — Khôi phục** (`POST .../versions/{id}/restore`): lấy version cũ → tạo version mới cùng nội dung → trả `message` + `restored_from_version` + `new_version`. Lịch sử không bị sửa.

## 6. Nợ kỹ thuật / việc nên làm tiếp

| # | Vấn đề | Đề xuất |
|---|---|---|
| 1 | Không có API/model/schema cho `projects` | Thêm `api/projects.py`, `models/project.py`, `schemas/project.py` |
| 2 | `created_by` luôn NULL | Gắn `get_current_user` sau khi merge nhánh auth |
| 3 | Phân biệt 404/422 bằng so khớp chuỗi | Tạo exception class riêng |
| 4 | Lỗi DB trả 500 khó hiểu | Thêm exception handler chung, log rõ ràng |
| 5 | `models/version.py` chưa dùng, `Text` lệch `LONGTEXT` | Nối SQLAlchemy session hoặc xoá file nếu không dùng |
| 6 | Không có migration tool | Cân nhắc Alembic khi schema thay đổi |
| 7 | `restore_version` gọi `get_version_detail` 2 lần | Truyền thẳng dữ liệu đã lấy, tránh query thừa |
| 8 | 3 file service rỗng | Xoá hoặc implement (template/github/gemini) |
| 9 | Không giới hạn kích thước `html_snapshot` | Thêm kiểm tra độ dài ở schema nếu cần |

## 7. Chạy thử nhanh

```powershell
cd backend
..\.venv\Scripts\python.exe scripts\init_db.py                  # tạo DB + bảng
..\.venv\Scripts\python.exe -m uvicorn main:app --reload        # chạy server

# Tạo sẵn 1 project để test (chưa có API tạo project)
# INSERT INTO templates (name) VALUES ('basic');
# INSERT INTO projects (user_id, template_id, campaign_name, product_name)
# VALUES (1, 1, 'Demo', 'San pham');
```

Sau đó mở http://127.0.0.1:8000/docs và thử nhóm **Project Versions** với `project_id` vừa tạo.
