from datetime import datetime, timedelta
from functools import lru_cache

from alibabacloud_dypnsapi20170525 import models as dypns_models
from alibabacloud_dypnsapi20170525.client import Client as DypnsClient
from alibabacloud_tea_openapi import models as open_api_models
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ratelimit import SMS_CODE_PHONE_ATTEMPTS, limiter, sms_code_attempt_key
from app.models.sms import SmsCodeIssue


SCENE_TEMPLATE_CODES = {
    "register": "100001",
    "login": "100001",
    "register_login": "100001",
    "change_phone": "100002",
    "reset_password": "100003",
    "bind_new_phone": "100004",
    "verify_bound_phone": "100005",
    "verify_bind_phone": "100005",
}

ERROR_MESSAGES = {
    "MOBILE_NUMBER_ILLEGAL": "手机号格式不正确",
    "BUSINESS_LIMIT_CONTROL": "发送次数超限，请明天再试",
    "FREQUENCY_FAIL": "发送太频繁，请稍后再试",
}

# Verification-code purposes. A code issued for one purpose must not be usable
# for another, so a registration code can never reset a password.
PURPOSE_REGISTER = "register"
PURPOSE_RESET = "reset"
PURPOSE_LOGIN = "login"

PURPOSE_BY_SCENE = {
    "register": PURPOSE_REGISTER,
    "register_login": PURPOSE_REGISTER,
    "reset_password": PURPOSE_RESET,
    "login": PURPOSE_LOGIN,
}

CODE_ATTEMPTS_EXCEEDED = "CODE_ATTEMPTS_EXCEEDED"
CODE_PURPOSE_MISMATCH = "CODE_PURPOSE_MISMATCH"


class SmsServiceError(Exception):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


@lru_cache(maxsize=1)
def _get_client() -> DypnsClient:
    config = open_api_models.Config(
        access_key_id=settings.ALIYUN_DYPNS_ACCESS_KEY_ID,
        access_key_secret=settings.ALIYUN_DYPNS_ACCESS_KEY_SECRET,
        endpoint=settings.ALIYUN_DYPNS_ENDPOINT,
    )
    return DypnsClient(config)


def _extract_error_code(error: Exception) -> str | None:
    code = getattr(error, "code", None)
    if code:
        return code

    data = getattr(error, "data", None)
    if isinstance(data, dict):
        for key in ("Code", "code"):
            if data.get(key):
                return str(data[key])

    message = str(error)
    for known_code in ERROR_MESSAGES:
        if known_code in message:
            return known_code
    return None


def _friendly_error(code: str | None, fallback: str = "短信服务暂不可用，请稍后再试") -> str:
    if not code:
        return fallback
    return ERROR_MESSAGES.get(code, fallback)


def _response_error(response_body: object, fallback: str) -> SmsServiceError:
    code = getattr(response_body, "code", None)
    message = getattr(response_body, "message", None)
    return SmsServiceError(_friendly_error(code, message or fallback), code)


def purpose_for_scene(scene: str) -> str | None:
    """Map a request ``scene`` (register / reset_password / …) to a code purpose."""
    return PURPOSE_BY_SCENE.get(scene)


def send_sms(phone: str, scene: str) -> None:
    template_code = SCENE_TEMPLATE_CODES.get(scene)
    if not template_code:
        raise SmsServiceError("短信验证码场景不正确")

    if settings.SMS_PROVIDER == "local":
        return

    request = dypns_models.SendSmsVerifyCodeRequest(
        country_code="86",
        phone_number=phone,
        sign_name=settings.ALIYUN_DYPNS_SIGN_NAME,
        template_code=template_code,
        template_param=settings.ALIYUN_DYPNS_TEMPLATE_PARAM,
        code_length=settings.ALIYUN_DYPNS_CODE_LENGTH,
        valid_time=settings.ALIYUN_DYPNS_VALID_TIME,
        interval=settings.ALIYUN_DYPNS_INTERVAL,
        code_type=settings.ALIYUN_DYPNS_CODE_TYPE,
    )

    try:
        response = _get_client().send_sms_verify_code(request)
    except Exception as exc:
        code = _extract_error_code(exc)
        raise SmsServiceError(_friendly_error(code), code) from exc

    body = response.body
    if not getattr(body, "success", False) or getattr(body, "code", "") != "OK":
        raise _response_error(body, "验证码发送失败，请稍后再试")


def record_code_issued(db: Session, phone: str, scene: str) -> None:
    """Remember the purpose of the code just sent to ``phone``.

    The SMS provider only knows the phone number, not why a code was requested,
    so the purpose is stored here and checked when the code comes back.
    """
    purpose = purpose_for_scene(scene)
    if not purpose:
        return

    db.query(SmsCodeIssue).filter(SmsCodeIssue.phone == phone).delete()
    db.add(SmsCodeIssue(phone=phone, purpose=purpose, issued_at=datetime.now()))
    db.commit()
    # A fresh code also opens a fresh wrong-attempt window.
    limiter.reset(sms_code_attempt_key(phone, purpose))


def issued_code_purpose(db: Session, phone: str) -> str | None:
    """Purpose of the newest still-valid code sent to ``phone``, if any."""
    cutoff = datetime.now() - timedelta(seconds=settings.ALIYUN_DYPNS_VALID_TIME)
    issue = (
        db.query(SmsCodeIssue)
        .filter(SmsCodeIssue.phone == phone, SmsCodeIssue.issued_at >= cutoff)
        .order_by(SmsCodeIssue.id.desc())
        .first()
    )
    return issue.purpose if issue else None


def _clear_code_issue(db: Session, phone: str) -> None:
    db.query(SmsCodeIssue).filter(SmsCodeIssue.phone == phone).delete()
    db.commit()


def check_sms_code(phone: str, code: str) -> bool:
    if settings.SMS_PROVIDER == "local":
        return code == settings.SMS_DEV_CODE

    request = dypns_models.CheckSmsVerifyCodeRequest(
        country_code="86",
        phone_number=phone,
        verify_code=code,
    )

    try:
        response = _get_client().check_sms_verify_code(request)
    except Exception as exc:
        error_code = _extract_error_code(exc)
        raise SmsServiceError(_friendly_error(error_code, "验证码校验失败，请稍后再试"), error_code) from exc

    body = response.body
    if getattr(body, "code", "") != "OK":
        raise _response_error(body, "验证码校验失败，请稍后再试")

    return getattr(getattr(body, "model", None), "verify_result", None) == "PASS"


def verify_code_for_purpose(db: Session, phone: str, code: str, purpose: str) -> bool:
    """Verify ``code`` for ``phone``, requiring it to belong to ``purpose``.

    Five consecutive failures for the same phone + purpose void the code: the
    attempt window reports as exceeded and the caller must request a new one.
    """
    attempt_key = sms_code_attempt_key(phone, purpose)
    if limiter.is_limited(attempt_key, SMS_CODE_PHONE_ATTEMPTS):
        raise SmsServiceError("验证码错误次数过多，请重新获取验证码", CODE_ATTEMPTS_EXCEEDED)

    issued_purpose = issued_code_purpose(db, phone)
    # A code we never issued has no purpose at all, so it can never match:
    # reject it for every provider instead of only for the local stub.
    if issued_purpose is None:
        raise SmsServiceError("验证码已失效，请重新获取", CODE_PURPOSE_MISMATCH)
    if issued_purpose != purpose:
        raise SmsServiceError("验证码与当前操作不匹配，请重新获取", CODE_PURPOSE_MISMATCH)

    if settings.SMS_PROVIDER == "local":
        # The stub code is static, so only a recorded issue can be valid.
        valid = code == settings.SMS_DEV_CODE
    else:
        valid = check_sms_code(phone, code)

    if not valid:
        if limiter.record(attempt_key, SMS_CODE_PHONE_ATTEMPTS) >= SMS_CODE_PHONE_ATTEMPTS.limit:
            # Five wrong guesses void the code entirely.
            _clear_code_issue(db, phone)
            raise SmsServiceError("验证码错误次数过多，请重新获取验证码", CODE_ATTEMPTS_EXCEEDED)
        return False

    limiter.reset(attempt_key)
    _clear_code_issue(db, phone)
    return True
