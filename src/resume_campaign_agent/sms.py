from __future__ import annotations

import json
import re

from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_credentials.models import Config as CredentialConfig
from alibabacloud_dypnsapi20170525.client import Client as DypnsClient
from alibabacloud_dypnsapi20170525.models import (
    CheckSmsVerifyCodeRequest,
    SendSmsVerifyCodeRequest,
)
from alibabacloud_tea_openapi.models import Config as OpenApiConfig

from .config import Settings


class SmsProviderError(RuntimeError):
    def __init__(self, operation: str, provider_code: str = "UNKNOWN") -> None:
        super().__init__(f"SMS provider {operation} failed")
        self.operation = operation
        self.provider_code = _safe_provider_code(provider_code)


class AliyunSmsProvider:
    """Alibaba Cloud PNVS adapter using an ECS RAM role and IMDSv2."""

    def __init__(self, settings: Settings) -> None:
        role_name = settings.aliyun_ecs_role_name
        region_id = settings.aliyun_region_id
        sign_name = settings.aliyun_sms_sign_name
        template_code = settings.aliyun_sms_template_code
        if not role_name or not region_id or not sign_name or not template_code:
            raise ValueError(
                "SMS requires ALIBABA_CLOUD_ECS_METADATA, "
                "ALIBABA_CLOUD_REGION_ID, ALIYUN_SMS_SIGN_NAME and "
                "ALIYUN_SMS_TEMPLATE_CODE"
            )

        credential = CredentialClient(
            CredentialConfig(
                type="ecs_ram_role",
                role_name=role_name,
                enable_imds_v2=True,
                disable_imds_v1=True,
            )
        )
        open_api_config = OpenApiConfig(
            credential=credential,
            region_id=region_id,
            endpoint=settings.aliyun_dypns_endpoint,
            protocol="https",
            connect_timeout=5_000,
            read_timeout=10_000,
        )
        self.client = DypnsClient(open_api_config)
        self.sign_name = sign_name
        self.template_code = template_code
        self.scheme_name = settings.aliyun_sms_scheme_name
        self.code_length = settings.sms_code_length
        self.valid_seconds = settings.sms_valid_seconds
        self.interval_seconds = settings.sms_interval_seconds

    async def send_code(self, phone: str) -> None:
        request = SendSmsVerifyCodeRequest(
            phone_number=phone,
            country_code="86",
            sign_name=self.sign_name,
            template_code=self.template_code,
            template_param=json.dumps(
                {"code": "##code##", "min": str(self.valid_seconds // 60)},
                separators=(",", ":"),
            ),
            code_length=self.code_length,
            valid_time=self.valid_seconds,
            duplicate_policy=1,
            interval=self.interval_seconds,
            code_type=1,
            return_verify_code=False,
            auto_retry=1,
            scheme_name=self.scheme_name,
        )
        try:
            response = await self.client.send_sms_verify_code_async(request)
        except Exception as exc:
            raise SmsProviderError("send", _exception_code(exc)) from exc
        if response.body.success is not True or response.body.code != "OK":
            raise SmsProviderError("send", response.body.code)

    async def verify_code(self, phone: str, code: str) -> bool:
        request = CheckSmsVerifyCodeRequest(
            phone_number=phone,
            country_code="86",
            verify_code=code,
            case_auth_policy=2,
            scheme_name=self.scheme_name,
        )
        try:
            response = await self.client.check_sms_verify_code_async(request)
        except Exception as exc:
            provider_code = _exception_code(exc)
            if provider_code == "isv.ValidateFail":
                return False
            raise SmsProviderError("verify", provider_code) from exc
        if response.body.code == "isv.ValidateFail":
            return False
        if response.body.success is not True or response.body.code != "OK":
            raise SmsProviderError("verify", response.body.code)
        return response.body.model is not None and response.body.model.verify_result == "PASS"


def _exception_code(exc: Exception) -> str:
    for candidate in (
        getattr(exc, "code", None),
        getattr(getattr(exc, "data", None), "code", None),
    ):
        if isinstance(candidate, str):
            return candidate
    data = getattr(exc, "data", None)
    if isinstance(data, dict):
        for key in ("Code", "code"):
            if isinstance(data.get(key), str):
                return data[key]
    return "SDK_ERROR"


def _safe_provider_code(value: str | None) -> str:
    text = value or "UNKNOWN"
    return text if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", text) else "UNKNOWN"
