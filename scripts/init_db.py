import os
import sys
from passlib.context import CryptContext
import pymysql

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings

# Cấu hình passlib sử dụng bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
  # Đảm bảo password là chuỗi thuần túy và không vượt quá 72 ký tự
  clean_pwd = str(password)[:72]
  return pwd_context.hash(clean_pwd)


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
          f"CREATE DATABASE IF NOT EXISTS {settings.DB_NAME} CHARACTER SET"
          " utf8mb4 COLLATE utf8mb4_unicode_ci;"
      )
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

      # 3. Seed tài khoản mẫu vào users
      sample_users = [
          (
              "Tiến Đạt (Admin)",
              "tiendat.admin@example.com",
              hash_password("Admin123@"),
          ),
          ("Member One", "member1@example.com", hash_password("Password123!")),
          ("Member Two", "member2@example.com", hash_password("Password123!")),
      ]

      seed_users_query = """
            INSERT IGNORE INTO users (full_name, email, hashed_password)
            VALUES (%s, %s, %s);
            """
      cursor.executemany(seed_users_query, sample_users)
      print(f"Seeded sample users into 'users' table.")

      # 4. Tạo bảng templates (Task của bạn)
      create_templates_table_query = """
            CREATE TABLE IF NOT EXISTS templates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT NULL,
                thumbnail_url VARCHAR(255) NOT NULL,
                file_path VARCHAR(255) NOT NULL,
                placeholders JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
      cursor.execute(create_templates_table_query)
      print("Table 'templates' created or already exists.")

      # 5. Seed 3 mẫu Landing Page vào templates (Task của bạn)
      sample_templates = [
          (
              "Modern Tech Gadget",
              (
                  "Giao diện tối giản phong cách Dark-mode hiện đại, chuyên dùng"
                  " cho sản phẩm công nghệ."
              ),
              "/static/thumbnails/modern_tech.jpg",
              "templates/modern_tech.html",
              '["headline", "subheadline", "hero_image_url", "primary_color",'
              ' "feature_1_title", "feature_1_desc", "feature_2_title",'
              ' "feature_2_desc", "feature_3_title", "feature_3_desc", "price",'
              ' "cta_text", "social_facebook", "social_zalo", "social_tiktok"]',
          ),
          (
              "Elegant Beauty & Care",
              (
                  "Phong cách thanh lịch, tông màu pastel nhẹ nhàng cho mỹ"
                  " phẩm và spa."
              ),
              "/static/thumbnails/elegant_beauty.jpg",
              "templates/elegant_beauty.html",
              '["headline", "subheadline", "hero_image_url", "primary_color",'
              ' "ingredients_list", "benefits_text", "original_price",'
              ' "discounted_price", "cta_text", "social_facebook",'
              ' "social_instagram", "hotline_number"]',
          ),
          (
              "Luxury Real Estate",
              (
                  "Giao diện sang trọng, không gian mở cho các dự án bất động"
                  " sản cao cấp."
              ),
              "/static/thumbnails/luxury_estate.jpg",
              "templates/luxury_estate.html",
              '["project_name", "short_description", "hero_image_url",'
              ' "primary_color", "location_text", "area_size", "price",'
              ' "amenities_list", "contact_name", "contact_phone",'
              ' "social_zalo"]',
          ),
      ]

      seed_templates_query = """
            INSERT INTO templates (name, description, thumbnail_url, file_path, placeholders)
            VALUES (%s, %s, %s, %s, %s);
            """
      for template in sample_templates:
        try:
          cursor.execute(seed_templates_query, template)
        except Exception:
          pass  # Bỏ qua nếu đã tồn tại mẫu trùng tên

      print("Seeded 3 sample templates into 'templates' table.")
      print("Database migration & seeding completed successfully!")

  except Exception as e:
    print(f"Error initializing database: {e}")
  finally:
    connection.close()


if __name__ == "__main__":
  init_database()