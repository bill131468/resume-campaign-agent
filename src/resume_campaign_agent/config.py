from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env.local", override=False)


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_api_key: str | None
    llm_base_url: str | None
    llm_model: str | None
    job_api_url: str
    request_timeout_seconds: float
    ai_ranking_timeout_seconds: float = 45.0
    app_environment: str = "production"
    enable_test_fixtures: bool = False
    auth_enabled: bool = False
    auth_database_path: str = "data/auth.sqlite3"
    auth_hash_secret: str | None = None
    auth_cookie_secure: bool = True
    auth_session_days: int = 30
    aliyun_ecs_role_name: str | None = None
    aliyun_region_id: str | None = None
    aliyun_dypns_endpoint: str = "dypnsapi.aliyuncs.com"
    aliyun_sms_sign_name: str | None = None
    aliyun_sms_template_code: str | None = None
    aliyun_sms_scheme_name: str | None = None
    sms_code_length: int = 6
    sms_valid_seconds: int = 300
    sms_interval_seconds: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "openai-compatible"),
            llm_api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            llm_base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
            llm_model=os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL"),
            job_api_url=os.getenv(
                "JOB_API_URL", "https://www.arbeitnow.com/api/job-board-api"
            ),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
            ai_ranking_timeout_seconds=float(
                os.getenv("AI_RANKING_TIMEOUT_SECONDS", "45")
            ),
            app_environment=os.getenv("APP_ENV", "production").strip().lower(),
            enable_test_fixtures=os.getenv("ENABLE_TEST_FIXTURES", "false")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"},
            auth_enabled=_env_bool("AUTH_ENABLED", False),
            auth_database_path=os.getenv("AUTH_DATABASE_PATH", "data/auth.sqlite3"),
            auth_hash_secret=os.getenv("AUTH_HASH_SECRET") or None,
            auth_cookie_secure=_env_bool("AUTH_COOKIE_SECURE", True),
            auth_session_days=_env_int("AUTH_SESSION_DAYS", 30, 1, 90),
            aliyun_ecs_role_name=os.getenv("ALIBABA_CLOUD_ECS_METADATA") or None,
            aliyun_region_id=os.getenv("ALIBABA_CLOUD_REGION_ID") or None,
            aliyun_dypns_endpoint=os.getenv(
                "ALIBABA_CLOUD_DYPNS_ENDPOINT", "dypnsapi.aliyuncs.com"
            ),
            aliyun_sms_sign_name=os.getenv("ALIYUN_SMS_SIGN_NAME") or None,
            aliyun_sms_template_code=os.getenv("ALIYUN_SMS_TEMPLATE_CODE") or None,
            aliyun_sms_scheme_name=os.getenv("ALIYUN_SMS_SCHEME_NAME") or None,
            sms_code_length=_env_int("SMS_CODE_LENGTH", 6, 4, 8),
            sms_valid_seconds=_env_int("SMS_VALID_SECONDS", 300, 60, 1800),
            sms_interval_seconds=_env_int("SMS_INTERVAL_SECONDS", 60, 30, 600),
        )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model)


def _env_bool(name: str, fallback: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return fallback
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _env_int(name: str, fallback: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw and raw.strip() else fallback
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value
