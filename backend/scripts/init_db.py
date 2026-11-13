import os
import sys
import json
import pymysql
import bcrypt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        (settings.DB_NAME, table_name),
    )
    return cursor.fetchone()[0] > 0


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (settings.DB_NAME, table_name, column_name),
    )
    return cursor.fetchone()[0] > 0


def _index_exists(cursor, table_name: str, index_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s
        """,
        (settings.DB_NAME, table_name, index_name),
    )
    return cursor.fetchone()[0] > 0


def _constraint_exists(cursor, table_name: str, constraint_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s
        """,
        (settings.DB_NAME, table_name, constraint_name),
    )
    return cursor.fetchone()[0] > 0


def ensure_projects_table(cursor) -> None:
    """Tạo bảng projects nếu chưa có, rồi bổ sung raw_json_data mà không xóa dữ liệu cũ."""
    if not _table_exists(cursor, "projects"):
        cursor.execute(
            """
            CREATE TABLE projects (
                id INT AUTO_INCREMENT PRIMARY KEY,
                raw_json_data JSON NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
        )
        print("Table 'projects' created.")
    else:
        print("Table 'projects' already exists. Existing columns were left unchanged.")

    if not _column_exists(cursor, "projects", "raw_json_data"):
        cursor.execute("ALTER TABLE projects ADD COLUMN raw_json_data JSON NULL;")
        print("Column 'projects.raw_json_data' added.")
    else:
        print("Column 'projects.raw_json_data' already exists.")


def ensure_generations_table(cursor) -> None:
    if not _table_exists(cursor, "generations"):
        cursor.execute(
            """
            CREATE TABLE generations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                project_id INT NOT NULL,
                prompt TEXT NOT NULL,
                response_json JSON NULL,
                status VARCHAR(20) NOT NULL,
                error_message TEXT NULL,
                created_at DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
                INDEX ix_generations_project_id (project_id),
                CONSTRAINT fk_generations_project_id
                    FOREIGN KEY (project_id) REFERENCES projects (id)
                    ON DELETE CASCADE,
                CONSTRAINT chk_generations_status
                    CHECK (status IN ('pending', 'success', 'failed'))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
        )
        print("Table 'generations' created.")
        return

    print("Table 'generations' already exists. Checking missing columns and constraints.")
    additions = [
        ("project_id", "ALTER TABLE generations ADD COLUMN project_id INT NULL"),
        ("prompt", "ALTER TABLE generations ADD COLUMN prompt TEXT NULL"),
        ("response_json", "ALTER TABLE generations ADD COLUMN response_json JSON NULL"),
        ("status", "ALTER TABLE generations ADD COLUMN status VARCHAR(20) NULL"),
        ("error_message", "ALTER TABLE generations ADD COLUMN error_message TEXT NULL"),
        (
            "created_at",
            "ALTER TABLE generations ADD COLUMN created_at DATETIME NULL DEFAULT (UTC_TIMESTAMP())",
        ),
    ]
    for column_name, statement in additions:
        if not _column_exists(cursor, "generations", column_name):
            cursor.execute(statement)
            print(f"Column 'generations.{column_name}' added.")

    if not _index_exists(cursor, "generations", "ix_generations_project_id"):
        cursor.execute(
            "ALTER TABLE generations ADD INDEX ix_generations_project_id (project_id);"
        )
        print("Index 'ix_generations_project_id' added.")

    if not _constraint_exists(cursor, "generations", "fk_generations_project_id"):
        cursor.execute(
            """
            ALTER TABLE generations
            ADD CONSTRAINT fk_generations_project_id
            FOREIGN KEY (project_id) REFERENCES projects (id)
            ON DELETE CASCADE;
            """
        )
        print("Foreign key 'fk_generations_project_id' added.")

    if not _constraint_exists(cursor, "generations", "chk_generations_status"):
        cursor.execute(
            """
            ALTER TABLE generations
            ADD CONSTRAINT chk_generations_status
            CHECK (status IN ('pending', 'success', 'failed'));
            """
        )
        print("Check constraint 'chk_generations_status' added.")


def hash_password(password: str) -> str:
    pwd_bytes = str(password).encode("utf-8")[:72]
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def init_database():
    print(f"Connecting to MySQL database: {settings.DB_NAME}...")
    connection = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            # 1. Tạo Database
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {settings.DB_NAME} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            cursor.execute(f"USE {settings.DB_NAME};")

            # 2. Tạo bảng users
            create_users_table_query = """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_users_table_query)
            print("Table 'users' created or already exists.")

            # 3. Seed tài khoản mẫu vào users
            sample_users = [
                ("Tiến Đạt (Admin)", "tiendat.admin@example.com", hash_password("Admin123@")),
                ("Member One", "member1@example.com", hash_password("Password123!")),
                ("Member Two", "member2@example.com", hash_password("Password123!")),
            ]
            seed_users_query = """
            INSERT IGNORE INTO users (full_name, email, hashed_password)
            VALUES (%s, %s, %s);
            """
            cursor.executemany(seed_users_query, sample_users)
            print("Seeded sample users into 'users' table.")

            # 4. Tạo bảng templates
            create_templates_table_query = """
            CREATE TABLE IF NOT EXISTS templates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT NULL,
                thumbnail_url VARCHAR(255) NOT NULL,
                file_path VARCHAR(255) NOT NULL,
                placeholders JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_templates_table_query)
            print("Table 'templates' created or already exists.")

            # 5. Seed 3 mẫu template chuẩn theo đặc tả
            sample_templates = [
                (
                    "Modern Tech Gadget",
                    "Giao diện Dark-mode hiện đại, tập trung làm nổi bật tính năng sản phẩm công nghệ bằng các khối lưới (Grid) tinh tế.",
                    "/static/thumbnails/modern_tech.jpg",
                    "templates/modern_tech.html",
                    json.dumps([
                        "brand_name", "headline", "subheadline", "hero_image_url", "primary_color",
                        "feature_1_title", "feature_1_desc",
                        "feature_2_title", "feature_2_desc",
                        "feature_3_title", "feature_3_desc",
                        "cta_text", "social_facebook", "social_zalo", "social_tiktok",
                    ]),
                ),
                (
                    "Elegant Beauty & Care",
                    "Phong cách thanh lịch, tông màu pastel với bố cục ảnh lớn, tôn vinh hình ảnh và trải nghiệm cảm xúc của khách hàng.",
                    "/static/thumbnails/elegant_beauty.jpg",
                    "templates/elegant_beauty.html",
                    json.dumps([
                        "headline", "subheadline", "hero_image_url", "primary_color",
                        "ingredients_list", "benefits_text", "original_price", "discounted_price",
                        "cta_text", "social_facebook", "social_instagram", "hotline_number",
                    ]),
                ),
                (
                    "Trust Consulting & Course",
                    "Giao diện chuyên nghiệp, tập trung vào nội dung thuyết phục, có khu vực riêng cho cam kết chất lượng và tiểu sử chuyên gia.",
                    "/static/thumbnails/trust_consulting.jpg",
                    "templates/trust_consulting.html",
                    json.dumps([
                        "headline", "subheadline", "hero_image_url", "primary_color",
                        "target_audience_text", "course_module_1", "course_module_2", "course_module_3",
                        "expert_name", "expert_bio", "cta_text", "social_facebook", "social_zalo",
                    ]),
                ),
            ]
            seed_templates_query = """
            REPLACE INTO templates (name, description, thumbnail_url, file_path, placeholders)
            VALUES (%s, %s, %s, %s, %s);
            """
            cursor.executemany(seed_templates_query, sample_templates)
            print("Seeded 3 sample templates into 'templates' table.")

            # 6. Tạo bảng projects
            create_projects_table_query = """
            CREATE TABLE IF NOT EXISTS projects (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                template_id INT NOT NULL,
                campaign_name VARCHAR(255) NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                product_description TEXT NULL,
                price DECIMAL(12,2) NULL,
                image_url VARCHAR(500) NULL,
                color_theme VARCHAR(50) NULL,
                facebook_url VARCHAR(500) NULL,
                tiktok_url VARCHAR(500) NULL,
                instagram_url VARCHAR(500) NULL,
                repo_url VARCHAR(500) NULL,
                github_pages_url VARCHAR(500) NULL,
                raw_json_data JSON NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_projects_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_projects_template FOREIGN KEY (template_id) REFERENCES templates(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_projects_table_query)
            print("Table 'projects' created or already exists.")

            # 4. Bảng projects (tạo nếu chưa có) và cột raw_json_data
            ensure_projects_table(cursor)

            # 5. Bảng generations, khóa ngoại và index
            ensure_generations_table(cursor)

            print("Database migration & seeding completed successfully!")

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    init_database()