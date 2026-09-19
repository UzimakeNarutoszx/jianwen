from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import create_access_token
from app.crud.user import authenticate_user, create_user, get_user_by_phone, reset_password
from app.schemas.user import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    SendSmsRequest,
)
from app.services.sms import SmsServiceError, check_sms_code, send_sms


router = APIRouter()


def _verify_sms_code(phone: str, code: str) -> None:
    try:
        if check_sms_code(phone, code):
            return
    except SmsServiceError as exc:
        message = str(exc)
        if "验证码" in message:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码输入错误，请重新输入") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码输入错误，请重新输入")


@router.post("/send-sms", response_model=MessageResponse)
def send_sms_code(payload: SendSmsRequest, db: Session = Depends(get_db)) -> MessageResponse:
    user = get_user_by_phone(db, payload.phone)
    if payload.scene in ("register", "register_login") and user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已注册")
    if payload.scene == "reset_password" and not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="手机号未注册")

    try:
        send_sms(payload.phone, payload.scene)
    except SmsServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    from app.core.config import settings

    if settings.SMS_PROVIDER == "local":
        return MessageResponse(message=f"开发验证码：{settings.SMS_DEV_CODE}")

    return MessageResponse(message="验证码已发送")


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    if get_user_by_phone(db, payload.phone):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已注册")

    _verify_sms_code(payload.phone, payload.sms_code)

    user = create_user(db, phone=payload.phone, nickname=payload.nickname, password=payload.password)
    return AuthResponse(access_token=create_access_token(user.id), user=user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = authenticate_user(db, payload.phone, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="密码错误，请重新输入")

    return AuthResponse(access_token=create_access_token(user.id), user=user)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    user = get_user_by_phone(db, payload.phone)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="手机号未注册")

    _verify_sms_code(payload.phone, payload.sms_code)

    reset_password(db, user, payload.new_password)
    return MessageResponse(message="密码已重置，请重新登录")
