import os
import sys
import json
import pymysql
import bcrypt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings

def hash_password(password: str) -> str:
    # Mã hóa chuỗi sang bytes và cắt chuẩn tối đa 72 bytes theo đúng giới hạn của bcrypt
    pwd_bytes = str(password).encode('utf-8')[:72]
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')

def init_database():
    db_password = settings.DB_PASSWORD if settings.DB_PASSWORD else "@Phamquocanh15072007"
    
    print(f"Connecting to MySQL database: {settings.DB_NAME}...")
    connection = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=db_password,
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
                        "cta_text", "social_facebook", "social_zalo", "social_tiktok"
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
                        "cta_text", "social_facebook", "social_instagram", "hotline_number"
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
                        "expert_name", "expert_bio", "cta_text", "social_facebook", "social_zalo"
                    ]),
                ),
            ]
            
            seed_templates_query = """
            REPLACE INTO templates (name, description, thumbnail_url, file_path, placeholders)
            VALUES (%s, %s, %s, %s, %s);
            """
            cursor.executemany(seed_templates_query, sample_templates)
            print("Seeded 3 sample templates into 'templates' table.")
            print("Database migration & seeding completed successfully!")

    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    init_database()