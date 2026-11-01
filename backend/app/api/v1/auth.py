from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.ratelimit import (
    LOGIN_IP,
    LOGIN_PHONE_FAILURE,
    LOGIN_PHONE_LOCK,
    SMS_IP,
    SMS_PHONE_DAILY,
    SMS_PHONE_INTERVAL,
    client_ip,
    limiter,
    login_failure_key,
    login_ip_key,
    login_lock_key,
    sms_ip_key,
    sms_phone_daily_key,
    sms_phone_key,
)
from app.core.security import create_access_token
from app.crud.user import (
    PhoneAlreadyRegistered,
    authenticate_user,
    create_user,
    get_user_by_phone,
    reset_password,
)
from app.schemas.user import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    SendSmsRequest,
)
from app.services.sms import (
    CODE_ATTEMPTS_EXCEEDED,
    CODE_PURPOSE_MISMATCH,
    PURPOSE_REGISTER,
    PURPOSE_RESET,
    SmsServiceError,
    record_code_issued,
    send_sms,
    verify_code_for_purpose,
)


router = APIRouter()

# One message for every failed login: wrong password, unknown phone and
# disabled account must be indistinguishable, otherwise the endpoint can be
# used to enumerate registered phone numbers.
LOGIN_FAILED_DETAIL = "手机号或密码错误"
CODE_REJECTED_DETAIL = "验证码输入错误，请重新输入"
TOO_MANY_ATTEMPTS_DETAIL = "尝试次数过多，请 15 分钟后再试"
SMS_TOO_FREQUENT_DETAIL = "验证码发送太频繁，请稍后再试"
SMS_IP_LIMITED_DETAIL = "当前网络请求过于频繁，请稍后再试"


def _too_many_requests(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


def _verify_sms_code(db: Session, phone: str, code: str, purpose: str) -> None:
    try:
        if verify_code_for_purpose(db, phone, code, purpose):
            return
    except SmsServiceError as exc:
        if exc.code == CODE_ATTEMPTS_EXCEEDED:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
            ) from exc
        if exc.code == CODE_PURPOSE_MISMATCH or "验证码" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=CODE_REJECTED_DETAIL
            ) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=CODE_REJECTED_DETAIL)


@router.post("/send-sms", response_model=MessageResponse)
def send_sms_code(
    payload: SendSmsRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = get_user_by_phone(db, payload.phone)
    if payload.scene in ("register", "register_login") and user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已注册")
    if payload.scene == "reset_password" and not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="手机号未注册")

    ip = client_ip(request)
    if limiter.is_limited(sms_ip_key(ip), SMS_IP):
        raise _too_many_requests(SMS_IP_LIMITED_DETAIL)
    if limiter.is_limited(sms_phone_key(payload.phone), SMS_PHONE_INTERVAL):
        raise _too_many_requests(SMS_TOO_FREQUENT_DETAIL)
    if limiter.is_limited(sms_phone_daily_key(payload.phone), SMS_PHONE_DAILY):
        raise _too_many_requests("今日验证码发送次数已达上限，请明天再试")

    try:
        send_sms(payload.phone, payload.scene)
    except SmsServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    record_code_issued(db, payload.phone, payload.scene)

    limiter.record(sms_ip_key(ip), SMS_IP)
    limiter.record(sms_phone_key(payload.phone), SMS_PHONE_INTERVAL)
    limiter.record(sms_phone_daily_key(payload.phone), SMS_PHONE_DAILY)

    if settings.is_development and settings.SMS_PROVIDER == "local":
        return MessageResponse(message=f"开发验证码：{settings.SMS_DEV_CODE}")

    return MessageResponse(message="验证码已发送")


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    if get_user_by_phone(db, payload.phone):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已注册")

    _verify_sms_code(db, payload.phone, payload.sms_code, PURPOSE_REGISTER)

    try:
        user = create_user(db, phone=payload.phone, nickname=payload.nickname, password=payload.password)
    except PhoneAlreadyRegistered as exc:
        # Lost the race against a concurrent registration for the same phone.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已注册") from exc

    return AuthResponse(access_token=create_access_token(user.id, user.token_version), user=user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    ip = client_ip(request)
    phone = payload.phone
    failure_key = login_failure_key(phone)
    lock_key = login_lock_key(phone)
    ip_key = login_ip_key(ip)

    if limiter.is_limited(ip_key, LOGIN_IP):
        raise _too_many_requests("当前网络登录请求过于频繁，请稍后再试")
    if limiter.is_limited(lock_key, LOGIN_PHONE_LOCK):
        raise _too_many_requests(TOO_MANY_ATTEMPTS_DETAIL)

    limiter.record(ip_key, LOGIN_IP)

    user = authenticate_user(db, phone, payload.password)
    if not user:
        # Every failure looks the same to the caller, so the response cannot be
        # used to tell "unknown phone" from "wrong password".
        if limiter.record(failure_key, LOGIN_PHONE_FAILURE) >= LOGIN_PHONE_FAILURE.limit:
            limiter.record(lock_key, LOGIN_PHONE_LOCK)
            limiter.reset(failure_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILED_DETAIL)

    limiter.reset(failure_key)
    limiter.reset(lock_key)
    return AuthResponse(access_token=create_access_token(user.id, user.token_version), user=user)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    user = get_user_by_phone(db, payload.phone)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="手机号未注册")

    _verify_sms_code(db, payload.phone, payload.sms_code, PURPOSE_RESET)

    reset_password(db, user, payload.new_password)
    return MessageResponse(message="密码已重置，请重新登录")
