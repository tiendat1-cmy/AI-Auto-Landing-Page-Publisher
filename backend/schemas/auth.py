from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Tên hiển thị")
    email: EmailStr = Field(..., description="Email đăng ký")
    password: str = Field(..., min_length=8, description="Mật khẩu tối thiểu 8 ký tự")

class UserRegisterResponse(BaseModel):
    id: int
    full_name: str
    email: str
    message: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    full_name: Optional[str] = None
    email: EmailStr
    created_at: Optional[datetime] = None