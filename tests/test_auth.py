from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from resume_campaign_agent.api import create_app
from resume_campaign_agent.auth import AuthError, AuthService
from resume_campaign_agent.config import Settings
from resume_campaign_agent.models import CreateSessionRequest
from resume_campaign_agent.sms import AliyunSmsProvider, SmsProviderError
from resume_campaign_agent.store import (
    InMemorySessionStore,
    SessionNotFoundError,
    bind_session_owner,
    reset_session_owner,
)


VALID_PHONE = "13800138000"
VALID_CODE = "246810"


class FakeSmsProvider:
    def __init__(self) -> None:
        self.sent_to: list[str] = []

    async def send_code(self, phone: str) -> None:
        self.sent_to.append(phone)

    async def verify_code(self, phone: str, code: str) -> bool:
        return phone in self.sent_to and code == VALID_CODE


class UnsubscribedSmsProvider(FakeSmsProvider):
    async def send_code(self, phone: str) -> None:
        raise SmsProviderError("send", "isv.PRODUCT_UN_SUBSCRIPT")


def auth_settings(tmp_path) -> Settings:
    return Settings(
        llm_provider="openai-compatible",
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
        job_api_url="https://example.invalid",
        request_timeout_seconds=1,
        app_environment="test",
        enable_test_fixtures=True,
        auth_enabled=True,
        auth_database_path=str(tmp_path / "auth.sqlite3"),
        auth_hash_secret="test-only-auth-hash-secret-32-bytes-minimum",
        auth_cookie_secure=False,
        aliyun_ecs_role_name="SilverSmsAuthRole",
        aliyun_region_id="cn-beijing",
        aliyun_sms_sign_name="test-sign",
        aliyun_sms_template_code="100001",
    )


def test_authentication_flow_requires_sms_setup_then_allows_password_login(tmp_path):
    settings = auth_settings(tmp_path)
    sms = FakeSmsProvider()
    service = AuthService(settings, sms)
    app = create_app(settings=settings, auth_service=service)

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/auth/status").json() == {"enabled": True}
        assert client.get("/", follow_redirects=False).headers["location"] == "/login"
        assert client.get("/api/sessions").status_code == 401
        assert "登录或创建账户" in client.get("/login").text

        sent = client.post("/api/auth/sms/request", json={"phone": "+86 138 0013 8000"})
        assert sent.status_code == 200
        assert sms.sent_to == [VALID_PHONE]

        verified = client.post(
            "/api/auth/sms/verify", json={"phone": VALID_PHONE, "code": VALID_CODE}
        )
        assert verified.status_code == 200
        assert verified.json() == {"status": "password_required", "phoneLast4": "8000"}
        assert "rca_password_setup" in client.cookies
        assert "rca_session" not in client.cookies

        weak_password = client.post(
            "/api/auth/password/setup",
            json={"password": "password", "password_confirmation": "password"},
        )
        assert weak_password.status_code == 400
        assert weak_password.json()["error"]["code"] == "INVALID_PASSWORD"

        created = client.post(
            "/api/auth/password/setup",
            json={"password": "Password2468", "password_confirmation": "Password2468"},
        )
        assert created.status_code == 201
        assert created.json()["phoneLast4"] == "8000"
        assert "rca_session" in client.cookies
        assert client.get("/").status_code == 200
        assert client.get("/api/auth/me").json()["phoneLast4"] == "8000"
        created_session = client.post(
            "/api/sessions", json={"resume": {"full_name": "本人档案"}}
        )
        assert created_session.status_code == 201
        own_sessions = client.get("/api/sessions")
        assert [item["id"] for item in own_sessions.json()] == [created_session.json()["id"]]

        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401

        bad_login = client.post(
            "/api/auth/password/login",
            json={"phone": VALID_PHONE, "password": "Password0000"},
        )
        assert bad_login.status_code == 401
        assert bad_login.json()["error"]["code"] == "INVALID_CREDENTIALS"

        logged_in = client.post(
            "/api/auth/password/login",
            json={"phone": VALID_PHONE, "password": "Password2468"},
        )
        assert logged_in.status_code == 200
        assert client.get("/api/auth/me").status_code == 200

    database_bytes = b"".join(
        path.read_bytes()
        for path in tmp_path.iterdir()
        if path.name.startswith("auth.sqlite3")
    )
    assert VALID_PHONE.encode() not in database_bytes
    assert VALID_CODE.encode() not in database_bytes
    assert b"Password2468" not in database_bytes


def test_unsubscribed_sms_product_explains_the_required_action(tmp_path):
    service = AuthService(auth_settings(tmp_path), UnsubscribedSmsProvider())

    with pytest.raises(AuthError) as error:
        import asyncio

        asyncio.run(service.request_sms_code(VALID_PHONE, "127.0.0.1"))

    assert error.value.status_code == 503
    assert "开通号码认证服务" in error.value.message


@pytest.mark.asyncio
async def test_session_store_isolates_resume_sessions_by_authenticated_owner(tmp_path):
    store = InMemorySessionStore(str(tmp_path / "sessions"))

    first_context = bind_session_owner("user-one")
    try:
        first_session = await store.create(CreateSessionRequest())
        assert (await store.get(first_session.id)).id == first_session.id
    finally:
        reset_session_owner(first_context)

    second_context = bind_session_owner("user-two")
    try:
        with pytest.raises(SessionNotFoundError):
            await store.get(first_session.id)
        assert await store.list() == []
    finally:
        reset_session_owner(second_context)


@pytest.mark.asyncio
async def test_aliyun_sms_adapter_uses_provider_generated_code_and_checks_pass(tmp_path):
    provider = AliyunSmsProvider(auth_settings(tmp_path))
    provider.client.send_sms_verify_code_async = AsyncMock(
        return_value=SimpleNamespace(body=SimpleNamespace(success=True, code="OK"))
    )
    provider.client.check_sms_verify_code_async = AsyncMock(
        return_value=SimpleNamespace(
            body=SimpleNamespace(
                success=True,
                code="OK",
                model=SimpleNamespace(verify_result="PASS"),
            )
        )
    )

    await provider.send_code(VALID_PHONE)
    send_request = provider.client.send_sms_verify_code_async.await_args.args[0]
    assert send_request.phone_number == VALID_PHONE
    assert send_request.return_verify_code is False
    assert send_request.template_param == '{"code":"##code##","min":"5"}'

    assert await provider.verify_code(VALID_PHONE, VALID_CODE) is True
    check_request = provider.client.check_sms_verify_code_async.await_args.args[0]
    assert check_request.verify_code == VALID_CODE
    assert check_request.case_auth_policy == 2
