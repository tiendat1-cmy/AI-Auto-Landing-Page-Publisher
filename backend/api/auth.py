import pymysql
from fastapi import APIRouter, HTTPException, status, Depends
from passlib.context import CryptContext
from schemas.auth import UserRegisterRequest, UserRegisterResponse, LoginRequest, UserResponse
from core.config import settings
from core.security import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

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

# 1. Đăng ký
@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserRegisterResponse)
async def register_user(payload: UserRegisterRequest):
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu phải có tối thiểu 8 ký tự"
        )

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email = %s", (payload.email,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email này đã được sử dụng trên hệ thống"
                )

            clean_pwd = str(payload.password)[:72]
            hashed_pwd = pwd_context.hash(clean_pwd)

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

# 2. Đăng nhập trả JWT access token
@router.post("/login", status_code=status.HTTP_200_OK)
async def login(payload: LoginRequest):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, email, hashed_password FROM users WHERE email = %s",
                (payload.email,)
            )
            user = cursor.fetchone()

            clean_pwd = str(payload.password)[:72]
            if not user or not pwd_context.verify(clean_pwd, user["hashed_password"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "success": False,
                        "error": {
                            "code": "INVALID_CREDENTIALS",
                            "message": "Email hoặc mật khẩu không chính xác",
                            "details": []
                        }
                    }
                )

            access_token = create_access_token(data={"sub": str(user["id"]), "email": user["email"]})
            return {
                "success": True,
                "data": {
                    "access_token": access_token,
                    "token_type": "bearer"
                }
            }
    finally:
        connection.close()

# 3. Lấy thông tin cá nhân qua dependency dùng chung get_current_user
@router.get("/me", status_code=status.HTTP_200_OK)
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "data": UserResponse(**current_user).model_dump()
    }