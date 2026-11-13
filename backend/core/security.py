from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import pymysql

from core.config import settings

security_scheme = HTTPBearer(auto_error=False)

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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire_minutes = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=expire_minutes))
    to_encode.update({"exp": expire})
    
    secret_key = getattr(settings, "SECRET_KEY", "super-secret-key-change-in-env")
    algorithm = getattr(settings, "ALGORITHM", "HS256")
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Dict[str, Any]:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Thiếu thông tin xác thực JWT Bearer Token",
                    "details": []
                }
            }
        )

    token = credentials.credentials
    secret_key = getattr(settings, "SECRET_KEY", "super-secret-key-change-in-env")
    algorithm = getattr(settings, "ALGORITHM", "HS256")

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "success": False,
                    "error": {
                        "code": "INVALID_TOKEN",
                        "message": "JWT Token không hợp lệ",
                        "details": []
                    }
                }
            )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "TOKEN_EXPIRED",
                    "message": "JWT Token đã hết hạn",
                    "details": []
                }
            }
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "JWT Token không hợp lệ",
                    "details": []
                }
            }
        )

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, full_name, email, created_at FROM users WHERE id = %s",
                (int(user_id),)
            )
            user = cursor.fetchone()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "success": False,
                        "error": {
                            "code": "INVALID_TOKEN",
                            "message": "Người dùng không tồn tại",
                            "details": []
                        }
                    }
                )
            return user
    finally:
        connection.close()