import pymysql
from fastapi import APIRouter, HTTPException, status
from passlib.context import CryptContext
from schemas.auth import UserRegisterRequest, UserRegisterResponse
from core.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

# Cấu hình mã hóa mật khẩu bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db_connection():
    return pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserRegisterResponse)
async def register_user(payload: UserRegisterRequest):
    # 1. Kiểm tra mật khẩu tối thiểu 8 ký tự (đã được Pydantic validate, kiểm tra thêm nếu cần)
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu phải có tối thiểu 8 ký tự"
        )

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 2. Kiểm tra email duy nhất
            cursor.execute("SELECT id FROM users WHERE email = %s", (payload.email,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email này đã được sử dụng trên hệ thống"
                )

            # 3. Băm mật khẩu bằng bcrypt (ép kiểu str và cắt gọn nếu cần)
            clean_pwd = str(payload.password)[:72]
            hashed_pwd = pwd_context.hash(clean_pwd)

            # 4. Lưu người dùng mới vào MySQL
            insert_query = """
            INSERT INTO users (full_name, email, hashed_password)
            VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query, (payload.full_name, payload.email, hashed_pwd))
            new_user_id = cursor.lastrowid

            return UserRegisterResponse(
                id=new_user_id,
                full_name=payload.full_name,
                email=payload.email,
                message="Đăng ký tài khoản thành công!"
            )
    finally:
        connection.close()