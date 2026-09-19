import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


PHONE_PATTERN = re.compile(r"^1\d{10}$")


class UserBase(BaseModel):
    phone: str = Field(..., min_length=11, max_length=11)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not PHONE_PATTERN.match(value):
            raise ValueError("手机号格式不正确")
        return value


class RegisterRequest(UserBase):
    nickname: str = Field(..., min_length=1, max_length=16)
    password: str = Field(..., min_length=6, max_length=32)
    sms_code: str = Field(..., min_length=6, max_length=6)

    @field_validator("sms_code")
    @classmethod
    def validate_sms_code(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("验证码输入错误，请重新输入")
        return value


class LoginRequest(UserBase):
    password: str = Field(..., min_length=6, max_length=32)


class ForgotPasswordRequest(UserBase):
    new_password: str = Field(..., min_length=6, max_length=32)
    sms_code: str = Field(..., min_length=6, max_length=6)

    @field_validator("sms_code")
    @classmethod
    def validate_sms_code(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("验证码输入错误，请重新输入")
        return value


class SendSmsRequest(UserBase):
    scene: str = Field(..., min_length=1, max_length=32)


class UserResponse(BaseModel):
    id: int
    phone: str
    nickname: str
    avatar_path: str | None = None
    bio: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
