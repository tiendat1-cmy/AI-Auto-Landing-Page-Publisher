from pydantic import BaseModel, EmailStr, Field

class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Tên hiển thị")
    email: EmailStr = Field(..., description="Email đăng ký")
    password: str = Field(..., min_length=8, description="Mật khẩu tối thiểu 8 ký tự")

class UserRegisterResponse(BaseModel):
    id: int
    full_name: str
    email: str
    message: str