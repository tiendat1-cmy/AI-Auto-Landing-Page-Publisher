import sys
import os
import pymysql
from passlib.context import CryptContext

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings

# Cấu hình passlib sử dụng bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    # bcrypt chỉ xử lý tối đa 72 byte, nên cắt theo byte UTF-8
    # (cắt theo ký tự có thể vượt 72 byte với tiếng Việt/emoji)
    clean_pwd = str(password).encode("utf-8")[:72].decode("utf-8", "ignore")
    return pwd_context.hash(clean_pwd)

def init_database():
    print(f"Connecting to MySQL database: {settings.DB_NAME}...")
    
    connection = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        charset="utf8mb4",
        autocommit=True
    )
    
    try:
        with connection.cursor() as cursor:
            # 1. Tạo Database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {settings.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute(f"USE {settings.DB_NAME};")
            
            # 2. Tạo bảng users
            create_users_table_query = """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(150) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_users_table_query)
            print("Table 'users' created or already exists.")
            
            # 3. Tạo bảng templates và projects
            create_templates_table_query = """
            CREATE TABLE IF NOT EXISTS templates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_templates_table_query)
            print("Table 'templates' created or already exists.")

            create_projects_table_query = """
            CREATE TABLE IF NOT EXISTS projects (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                template_id INT NOT NULL,
                campaign_name VARCHAR(255) NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                product_description TEXT,
                price DECIMAL(12,2),
                image_url VARCHAR(500),
                color_theme VARCHAR(50),
                facebook_url VARCHAR(500),
                tiktok_url VARCHAR(500),
                instagram_url VARCHAR(500),
                repo_url VARCHAR(500),
                github_pages_url VARCHAR(500),
                raw_json_data JSON,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_projects_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_projects_template FOREIGN KEY (template_id) REFERENCES templates(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_projects_table_query)
            print("Table 'projects' created or already exists.")

            # 4. Tạo bảng project_versions (lưu lịch sử phiên bản Landing Page)
            #    Phải tạo sau bảng projects vì có khóa ngoại trỏ tới projects(id)
            create_project_versions_table_query = """
            CREATE TABLE IF NOT EXISTS project_versions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                project_id INT NOT NULL,
                version_number INT NOT NULL,
                json_content JSON NULL,
                html_snapshot LONGTEXT NOT NULL,
                commit_sha VARCHAR(40) NULL,
                change_summary VARCHAR(255) NULL,
                created_by INT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_project_versions_project_id (project_id),
                CONSTRAINT uq_project_version UNIQUE (project_id, version_number),
                CONSTRAINT fk_versions_project FOREIGN KEY (project_id)
                    REFERENCES projects(id) ON DELETE CASCADE,
                CONSTRAINT fk_versions_user FOREIGN KEY (created_by)
                    REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_project_versions_table_query)
            print("Table 'project_versions' created or already exists.")

            # 5. Seed tài khoản mẫu
            sample_users = [
                ("Tiến Đạt (Admin)", "tiendat.admin@example.com", hash_password("Admin123@")),
                ("Member One", "member1@example.com", hash_password("Password123!")),
                ("Member Two", "member2@example.com", hash_password("Password123!"))
            ]
            
            seed_query = """
            INSERT IGNORE INTO users (full_name, email, hashed_password)
            VALUES (%s, %s, %s);
            """
            cursor.executemany(seed_query, sample_users)
            print(f"Seeded {cursor.rowcount} sample users into 'users' table.")

            print("Database migration & seeding completed successfully!")
            
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    init_database()
