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
        )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model)
