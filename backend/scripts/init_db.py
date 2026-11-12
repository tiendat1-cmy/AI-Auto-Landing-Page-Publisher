import sys
import os
import pymysql
from passlib.context import CryptContext

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
            
            # 3. Seed tài khoản mẫu
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