from dataclasses import dataclass
import logging
import os
from pathlib import Path
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

logger = logging.getLogger(__name__)

# The value shipped in source control; production must override it.
DEFAULT_SECRET_KEY = "jianwen-local-dev-secret"
DEVELOPMENT_ENVIRONMENTS = {"development", "dev", "local", "test", "testing"}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


def _split_origins(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def is_development_environment(environment: str) -> bool:
    return (environment or "").strip().lower() in DEVELOPMENT_ENVIRONMENTS


def assert_production_safe(environment: str, secret_key: str, sms_provider: str) -> None:
    """Refuse to boot a non-development deployment with development defaults."""
    if is_development_environment(environment):
        return
    if secret_key == DEFAULT_SECRET_KEY:
        raise RuntimeError(
            f"SECRET_KEY is still the built-in development default while ENVIRONMENT={environment!r}. "
            "Set SECRET_KEY before starting the service."
        )
    if (sms_provider or "").strip().lower() == "local":
        raise RuntimeError(
            f"SMS_PROVIDER=local while ENVIRONMENT={environment!r}. "
            "Configure the real SMS provider before starting the service."
        )


@dataclass(frozen=True)
class Settings:
    PROJECT_NAME: str = "见闻 API"
    API_V1_PREFIX: str = "/api/v1"

    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: str = os.getenv("MYSQL_PORT", "3306")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "ENS_Project")

    SECRET_KEY: str = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
    ACCESS_TOKEN_EXPIRE_SECONDS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", "604800"))
    CORS_ORIGINS: list[str] = None
    # Deployment environment: development / test stay permissive, anything
    # else enables the production checks below.
    ENVIRONMENT: str = (
        os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or os.getenv("ENV") or "development"
    )
    # Only trust X-Forwarded-For when the app really runs behind a proxy.
    TRUST_PROXY: bool = _env_bool("TRUST_PROXY", False)
    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        str(Path(__file__).resolve().parents[2] / "uploads"),
    )

    ALIYUN_DYPNS_ACCESS_KEY_ID: str = os.getenv("ALIYUN_DYPNS_ACCESS_KEY_ID", "")
    ALIYUN_DYPNS_ACCESS_KEY_SECRET: str = os.getenv("ALIYUN_DYPNS_ACCESS_KEY_SECRET", "")
    ALIYUN_DYPNS_ENDPOINT: str = os.getenv("ALIYUN_DYPNS_ENDPOINT", "dypnsapi.aliyuncs.com")
    ALIYUN_DYPNS_SIGN_NAME: str = os.getenv("ALIYUN_DYPNS_SIGN_NAME", "速通互联验证码")
    ALIYUN_DYPNS_SERVICE_NAME: str = os.getenv("ALIYUN_DYPNS_SERVICE_NAME", "号码认证服务（DYPNS）")
    ALIYUN_DYPNS_TEMPLATE_PARAM: str = os.getenv("ALIYUN_DYPNS_TEMPLATE_PARAM", '{"code":"##code##","min":"5"}')
    ALIYUN_DYPNS_CODE_LENGTH: int = int(os.getenv("ALIYUN_DYPNS_CODE_LENGTH", "6"))
    ALIYUN_DYPNS_VALID_TIME: int = int(os.getenv("ALIYUN_DYPNS_VALID_TIME", "300"))
    ALIYUN_DYPNS_INTERVAL: int = int(os.getenv("ALIYUN_DYPNS_INTERVAL", "60"))
    ALIYUN_DYPNS_CODE_TYPE: int = int(os.getenv("ALIYUN_DYPNS_CODE_TYPE", "1"))
    SMS_PROVIDER: str = os.getenv("SMS_PROVIDER", "aliyun")
    SMS_DEV_CODE: str = os.getenv("SMS_DEV_CODE", "123456")
    AI_DAILY_QUESTION_LIMIT: int = int(os.getenv("AI_DAILY_QUESTION_LIMIT", "20"))

    # 重大会议置顶：只在后台调度线程里按白名单抓官方来源。
    BREAKING_NEWS_SOURCES: str = os.getenv("BREAKING_NEWS_SOURCES", "中国政府网,新华社,人民日报")
    BREAKING_NEWS_TIMEOUT_SECONDS: int = int(os.getenv("BREAKING_NEWS_TIMEOUT_SECONDS", "10"))
    # 会议闭幕后继续置顶的天数（北京时间，含第 N 天当天）。
    BREAKING_NEWS_PIN_DAYS: int = int(os.getenv("BREAKING_NEWS_PIN_DAYS", "7"))


    def __post_init__(self) -> None:
        origins = os.getenv("CORS_ORIGINS", "*")
        object.__setattr__(self, "CORS_ORIGINS", ["*"] if origins == "*" else _split_origins(origins))

    @property
    def is_development(self) -> bool:
        return is_development_environment(self.ENVIRONMENT)

    def validate_startup(self) -> None:
        """Fail fast on production runs that still use development defaults."""
        assert_production_safe(self.ENVIRONMENT, self.SECRET_KEY, self.SMS_PROVIDER)
        if not self.is_development and self.CORS_ORIGINS == ["*"]:
            logger.warning(
                "CORS_ORIGINS is '*' while ENVIRONMENT=%s; restrict it to the real front-end origins.",
                self.ENVIRONMENT,
            )

    @property
    def server_database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/?charset=utf8mb4"
        )

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )


settings = Settings()
# Raises at import time in a non-development environment that kept the
# development secret or the local SMS stub.
settings.validate_startup()
