from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from resume_campaign_agent.api import create_app
from resume_campaign_agent.config import Settings
from resume_campaign_agent.models import JobPosting


class FakeJobProvider:
    async def search(self, query):
        jobs = [
            JobPosting(
                id="job_1",
                title="Python AI Engineer",
                company="Example AI",
                location="Berlin, Germany",
                remote=False,
                url="https://example.com/jobs/1",
                tags=["Python", "FastAPI", "LLM"],
                description_excerpt="Build Python and LLM agent services.",
                posted_at=datetime.now(timezone.utc),
                source="fixture",
            ),
            JobPosting(
                id="job_2",
                title="Machine Learning Engineer",
                company="Remote Labs",
                location="Remote",
                remote=True,
                url="https://example.com/jobs/2",
                tags=["Python", "Machine Learning"],
                description_excerpt="Production machine learning systems.",
                posted_at=datetime.now(timezone.utc),
                source="fixture",
            ),
        ]
        return jobs[: query.limit]


@pytest.fixture
def client():
    settings = Settings(
        llm_provider="openai-compatible",
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
        job_api_url="https://example.invalid",
        request_timeout_seconds=1,
        app_environment="test",
        enable_test_fixtures=True,
    )
    with TestClient(create_app(settings=settings, job_provider=FakeJobProvider())) as test_client:
        yield test_client


@pytest.fixture
def production_client():
    settings = Settings(
        llm_provider="openai-compatible",
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
        job_api_url="https://example.invalid",
        request_timeout_seconds=1,
        app_environment="production",
        enable_test_fixtures=False,
    )
    with TestClient(create_app(settings=settings, job_provider=FakeJobProvider())) as test_client:
        yield test_client


@pytest.fixture
def complete_resume():
    return {
        "full_name": "测试用户",
        "email": "candidate@example.com",
        "phone": "+86 13800000000",
        "city": "上海",
        "target_roles": ["AI Engineer"],
        "years_experience": 0,
        "skills": ["Python", "FastAPI", "LLM"],
        "summary": "专注于人工智能应用开发，具备后端服务和大模型应用的项目经验。",
        "education": [
            {"school": "示例大学", "degree": "本科", "major": "计算机科学", "graduation_year": 2026}
        ],
    }
