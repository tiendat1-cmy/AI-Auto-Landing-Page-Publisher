"""Session SQLAlchemy dùng chung cho các model.

Auth vẫn giữ kết nối PyMySQL riêng trong api/auth.py.
Engine này trỏ vào đúng MySQL đã cấu hình trong core.config.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
