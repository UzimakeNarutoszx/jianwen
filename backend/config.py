from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Final


DOTENV_PATH: Final[Path] = Path(__file__).resolve().with_name(".env")


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


_load_dotenv(DOTENV_PATH)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class Settings:
    project_name: str = "见闻 AI"
    ark_api_base_url: str = os.getenv(
        "ARK_API_BASE_URL",
        "https://ark.cn-beijing.volces.com/api/v3",
    )
    ark_api_key: str = os.getenv("ARK_API_KEY", "")
    ark_model: str = os.getenv("ARK_MODEL", "doubao-seed-1-8-251228")
    ark_timeout_seconds: int = int(os.getenv("ARK_TIMEOUT_SECONDS", "60"))
    ark_use_env_proxy: bool = _env_bool("ARK_USE_ENV_PROXY", True)
    ark_thinking_disabled: bool = _env_bool("ARK_THINKING_DISABLED", True)
    ark_temperature: float = float(os.getenv("ARK_TEMPERATURE", "0.2"))
    ark_top_p: float = float(os.getenv("ARK_TOP_P", "0.9"))

    @property
    def ark_chat_completions_url(self) -> str:
        return f"{self.ark_api_base_url.rstrip('/')}/chat/completions"


settings = Settings()
