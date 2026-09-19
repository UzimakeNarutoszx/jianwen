from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def _split_origins(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    PROJECT_NAME: str = "见闻 API"
    API_V1_PREFIX: str = "/api/v1"

    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: str = os.getenv("MYSQL_PORT", "3306")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "ENS_Project")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "jianwen-local-dev-secret")
    ACCESS_TOKEN_EXPIRE_SECONDS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", "604800"))
    CORS_ORIGINS: list[str] = None
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

    def __post_init__(self) -> None:
        origins = os.getenv("CORS_ORIGINS", "*")
        object.__setattr__(self, "CORS_ORIGINS", ["*"] if origins == "*" else _split_origins(origins))

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
