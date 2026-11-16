# fix(db): sửa thứ tự tạo bảng trong `init_db.py` để chạy được migration

## Tóm tắt

`backend/scripts/init_db.py` tạo bảng `project_versions` **trước** khi bảng `projects` tồn tại, trong khi `project_versions` có khóa ngoại `project_id → projects(id)`. MySQL từ chối câu lệnh `CREATE TABLE` và toàn bộ quá trình khởi tạo DB thất bại. PR này bổ sung bước tạo `templates` + `projects` và đưa `project_versions` xuống sau đó.

## Vấn đề

Chạy `python backend/scripts/init_db.py` trên database trống:

```
Error initializing database: (1824, "Failed to open the referenced table 'projects'")
```

hoặc:

```
Error initializing database: (1215, 'Cannot add foreign key constraint')
```

Nguyên nhân:

1. Script chỉ tạo `users`, rồi tạo ngay `project_versions` có:
   ```sql
   CONSTRAINT fk_versions_project FOREIGN KEY (project_id)
       REFERENCES projects(id) ON DELETE CASCADE
   ```
2. Bảng `projects` **chưa hề được tạo** trong script (schema hiện có ở nhánh `feature/T02BC41-init-templates-projects` nhưng chưa merge vào nhánh này).
3. Do đó không chỉ sai thứ tự — bảng được tham chiếu còn không tồn tại.

Kết quả: `project_versions` không được tạo, các API `/api/v1/projects/{id}/versions` trả lỗi 500 (`Table 'landing_page_db.project_versions' doesn't exist`) dù server chạy bình thường.

## Thay đổi

File: `backend/scripts/init_db.py`

### 1. Bổ sung bước tạo `templates` và `projects`

Lấy đúng schema từ nhánh `origin/feature/T02BC41-init-templates-projects` để tránh lệch cấu trúc giữa các nhánh:

```sql
CREATE TABLE IF NOT EXISTS templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ...;

CREATE TABLE IF NOT EXISTS projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    template_id INT NOT NULL,
    campaign_name VARCHAR(255) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    ...
    CONSTRAINT fk_projects_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_projects_template FOREIGN KEY (template_id) REFERENCES templates(id)
) ...;
```

### 2. Đưa `project_versions` xuống sau `projects`

Thứ tự thực thi mới:

| Bước | Nội dung | Phụ thuộc |
|---|---|---|
| 1 | `CREATE DATABASE` / `USE` | — |
| 2 | `users` | — |
| 3 | `templates` → `projects` | `users`, `templates` |
| 4 | `project_versions` | `projects`, `users` |
| 5 | Seed tài khoản mẫu | `users` |

Thêm comment tại bước 4 để người sau không di chuyển lại:

```python
# 4. Tạo bảng project_versions (lưu lịch sử phiên bản Landing Page)
#    Phải tạo sau bảng projects vì có khóa ngoại trỏ tới projects(id)
```

### 3. Sửa `hash_password` cắt mật khẩu theo byte thay vì ký tự

bcrypt giới hạn **72 byte**, không phải 72 ký tự. Cách cũ `str(password)[:72]` có thể vượt 72 byte với tiếng Việt/emoji và gây lỗi `password cannot be longer than 72 bytes` khi dùng bcrypt 4.x/5.x.

```python
# Trước
clean_pwd = str(password)[:72]

# Sau
clean_pwd = str(password).encode("utf-8")[:72].decode("utf-8", "ignore")
```

## Cách kiểm thử

```bash
# 1. Xoá database cũ (tuỳ chọn, để test từ đầu)
mysql -u root -p -e "DROP DATABASE IF EXISTS landing_page_db;"

# 2. Chạy migration
cd backend
../.venv/Scripts/python.exe scripts/init_db.py
```

Kết quả mong đợi:

```
Table 'users' created or already exists.
Table 'templates' created or already exists.
Table 'projects' created or already exists.
Table 'project_versions' created or already exists.
Seeded 3 sample users into 'users' table.
Database migration & seeding completed successfully!
```

Kiểm tra khóa ngoại:

```sql
SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'landing_page_db'
  AND REFERENCED_TABLE_NAME IS NOT NULL;
```

Kỳ vọng: `projects → users`, `projects → templates`, `project_versions → projects`, `project_versions → users`.

Kiểm tra API (sau khi tạo ít nhất 1 project):

```bash
curl http://127.0.0.1:8000/api/v1/projects/1/versions
# -> 200 []
```

Đã test thực tế: chạy lại script trên DB trống tạo đủ 4 bảng, seed 3 user, `GET /api/v1/projects/1/versions` trả `200` với `[]`.

## Tính idempotent

Mọi câu lệnh đều dùng `CREATE TABLE IF NOT EXISTS`, seed dùng `INSERT IGNORE`, nên chạy lại script nhiều lần không lỗi và không nhân đôi dữ liệu. Lưu ý: nếu DB đã có bảng `projects` với schema khác (do nhánh `T02BC41` tạo trước), script **không** ghi đè — cấu trúc cũ được giữ nguyên.

## Ảnh hưởng / rủi ro

- Chỉ thay đổi script migration, không đụng code API.
- Không có migration ngược (drop table); cần chạy lại từ DB trống nếu muốn reset.
- Phụ thuộc schema `projects`/`templates` của nhánh `T02BC41`. Nếu nhánh đó đổi cột, cần đồng bộ lại — nên cân nhắc chuyển sang Alembic khi schema tiếp tục mở rộng.
- `raw_json_data JSON` yêu cầu MySQL ≥ 5.7.

## Checklist

- [x] `python -m py_compile backend/scripts/init_db.py` không lỗi
- [x] Chạy `init_db.py` trên DB trống tạo đủ 4 bảng
- [x] Khóa ngoại `project_versions → projects` tạo thành công
- [x] `hash_password` hoạt động với mật khẩu dài/nhiều dấu tiếng Việt
- [x] API versions trả 200 sau khi migration
- [ ] Review lại schema `projects` với nhánh `T02BC41`

## Ghi chú cho reviewer

- **Không** commit `backend/core/config.py` — file này đang bị sửa cục bộ và chứa mật khẩu DB thật (`DB_PASSWORD`). Giá trị mặc định trong repo nên là chuỗi rỗng, mật khẩu đặt qua `.env` (đã có trong `.gitignore`).
- Cần dùng Python của `.venv` để chạy script: `passlib 1.7.4` không tương thích `bcrypt ≥ 4.1` (lỗi `password cannot be longer than 72 bytes` + cảnh báo `error reading bcrypt version`).
