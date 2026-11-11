import os
from dotenv import load_dotenv

# Tải biến môi trường từ file .env
load_dotenv()

class Settings:
    PROJECT_NAME: str = "AI Landing Page Publisher"
    
    # Cấu hình Database MySQL
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", 3306))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "landing_page_db")
    
    # Third-party API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

settings = Settings()