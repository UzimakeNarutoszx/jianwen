import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import settings


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, stored_digest = password_hash.split("$", 2)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return hmac.compare_digest(digest.hex(), stored_digest)


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_SECONDS,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_token = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = hmac.new(settings.SECRET_KEY.encode("utf-8"), payload_token.encode("utf-8"), hashlib.sha256)
    signature_token = base64.urlsafe_b64encode(signature.digest()).decode("utf-8").rstrip("=")
    return f"{payload_token}.{signature_token}"


def _add_base64_padding(value: str) -> str:
    return value + "=" * (-len(value) % 4)


def verify_access_token(token: str) -> int | None:
    if not isinstance(token, str) or not token.isascii():
        return None
    try:
        payload_token, signature_token = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload_token.encode("utf-8"),
        hashlib.sha256,
    )
    expected_signature_token = base64.urlsafe_b64encode(expected_signature.digest()).decode("utf-8").rstrip("=")
    if not hmac.compare_digest(signature_token, expected_signature_token):
        return None

    try:
        payload_bytes = base64.urlsafe_b64decode(_add_base64_padding(payload_token))
        payload = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(payload, dict) or int(payload.get("exp", 0)) <= int(time.time()):
            return None
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
