from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .config import Settings
from .sms import SmsProviderError


SESSION_COOKIE = "rca_session"
SETUP_COOKIE = "rca_password_setup"
SETUP_TTL_SECONDS = 10 * 60
MAX_VERIFY_ATTEMPTS = 8


class SmsProvider(Protocol):
    async def send_code(self, phone: str) -> None: ...

    async def verify_code(self, phone: str, code: str) -> bool: ...


class AuthError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    phone_last4: str


@dataclass(frozen=True)
class VerificationResult:
    status: str
    phone_last4: str
    session_token: str | None = None
    setup_token: str | None = None


class AuthService:
    def __init__(
        self,
        settings: Settings,
        sms_provider: SmsProvider,
        *,
        now=time.time,
    ) -> None:
        if not settings.auth_hash_secret or len(settings.auth_hash_secret.encode()) < 32:
            raise ValueError("AUTH_HASH_SECRET must contain at least 32 bytes")
        self.settings = settings
        self.sms_provider = sms_provider
        self._secret = settings.auth_hash_secret.encode("utf-8")
        self._now = now
        self._lock = threading.RLock()
        self._active_sends: set[str] = set()
        self._active_verifications: set[str] = set()
        database_path = settings.auth_database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self.database = sqlite3.connect(database_path, check_same_thread=False)
        self.database.row_factory = sqlite3.Row
        self.database.execute("PRAGMA foreign_keys = ON")
        if database_path != ":memory:":
            self.database.execute("PRAGMA journal_mode = WAL")
        self._initialize_schema()
        self._dummy_salt = self._digest("dummy-password-salt")[:16]
        self._dummy_password_hash = self._password_hash("invalid-password", self._dummy_salt)

    def close(self) -> None:
        with self._lock:
            self.database.close()

    def _initialize_schema(self) -> None:
        with self.database:
            self.database.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    phone_hash TEXT NOT NULL UNIQUE,
                    phone_last4 TEXT NOT NULL,
                    password_salt BLOB,
                    password_hash BLOB,
                    created_at_ms INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at_ms INTEGER NOT NULL,
                    expires_at_ms INTEGER NOT NULL,
                    last_seen_at_ms INTEGER NOT NULL,
                    revoked_at_ms INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
                    ON auth_sessions(user_id, expires_at_ms);
                CREATE TABLE IF NOT EXISTS sms_challenges (
                    phone_hash TEXT PRIMARY KEY,
                    requested_at_ms INTEGER NOT NULL,
                    expires_at_ms INTEGER NOT NULL,
                    verify_attempts INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS password_setups (
                    token_hash TEXT PRIMARY KEY,
                    phone_hash TEXT NOT NULL,
                    phone_last4 TEXT NOT NULL,
                    created_at_ms INTEGER NOT NULL,
                    expires_at_ms INTEGER NOT NULL,
                    consumed_at_ms INTEGER
                );
                CREATE TABLE IF NOT EXISTS auth_rate_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_kind TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    created_at_ms INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_auth_rate_events_lookup
                    ON auth_rate_events(event_kind, key_hash, created_at_ms);
                """
            )

    async def request_sms_code(self, phone_input: str, client_ip: str) -> dict[str, int]:
        phone = normalize_phone(phone_input)
        phone_hash = self._keyed_hash("phone", phone)
        ip_hash = self._keyed_hash("ip", normalize_ip(client_ip))
        now_ms = self._now_ms()

        with self._lock:
            if phone_hash in self._active_sends:
                raise AuthError(429, "SMS_ALREADY_SENDING", "验证码正在发送，请稍候", retry_after_seconds=5)
            self._prune(now_ms)
            challenge = self.database.execute(
                "SELECT requested_at_ms FROM sms_challenges WHERE phone_hash = ?",
                (phone_hash,),
            ).fetchone()
            if challenge:
                wait_ms = self.settings.sms_interval_seconds * 1000 - (
                    now_ms - challenge["requested_at_ms"]
                )
                if wait_ms > 0:
                    retry = max(1, (wait_ms + 999) // 1000)
                    raise AuthError(429, "SMS_RATE_LIMITED", f"请在 {retry} 秒后重新获取", retry_after_seconds=retry)
            with self.database:
                self._reserve_rate("sms-phone", phone_hash, now_ms, 60 * 60_000, 5)
                self._reserve_rate("sms-ip", ip_hash, now_ms, 60 * 60_000, 20)
            self._active_sends.add(phone_hash)

        try:
            await self.sms_provider.send_code(phone)
        except SmsProviderError as exc:
            _safe_log("sms_provider_error", operation=exc.operation, provider_code=exc.provider_code)
            message = (
                "阿里云短信服务还没有开通，请先开通号码认证服务"
                if exc.provider_code == "isv.PRODUCT_UN_SUBSCRIPT"
                else "验证码暂时无法发送，请稍后重试"
            )
            raise AuthError(
                503,
                "SMS_SEND_UNAVAILABLE",
                message,
                retry_after_seconds=60,
            ) from exc
        finally:
            with self._lock:
                self._active_sends.discard(phone_hash)

        completed_ms = self._now_ms()
        with self._lock, self.database:
            self.database.execute(
                """
                INSERT INTO sms_challenges(phone_hash, requested_at_ms, expires_at_ms, verify_attempts)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(phone_hash) DO UPDATE SET
                    requested_at_ms = excluded.requested_at_ms,
                    expires_at_ms = excluded.expires_at_ms,
                    verify_attempts = 0
                """,
                (
                    phone_hash,
                    completed_ms,
                    completed_ms + self.settings.sms_valid_seconds * 1000,
                ),
            )
        return {
            "expiresInSeconds": self.settings.sms_valid_seconds,
            "retryAfterSeconds": self.settings.sms_interval_seconds,
        }

    async def verify_sms_code(
        self, phone_input: str, code_input: str, client_ip: str
    ) -> VerificationResult:
        phone = normalize_phone(phone_input)
        code = normalize_code(code_input, self.settings.sms_code_length)
        phone_hash = self._keyed_hash("phone", phone)
        ip_hash = self._keyed_hash("ip", normalize_ip(client_ip))
        now_ms = self._now_ms()

        with self._lock:
            if phone_hash in self._active_verifications:
                raise AuthError(429, "VERIFY_IN_PROGRESS", "验证码正在核验，请稍候", retry_after_seconds=3)
            self._prune(now_ms)
            challenge = self.database.execute(
                "SELECT expires_at_ms, verify_attempts FROM sms_challenges WHERE phone_hash = ?",
                (phone_hash,),
            ).fetchone()
            if (
                not challenge
                or challenge["expires_at_ms"] <= now_ms
                or challenge["verify_attempts"] >= MAX_VERIFY_ATTEMPTS
            ):
                raise AuthError(401, "INVALID_SMS_CODE", "验证码错误或已过期")
            with self.database:
                self._reserve_rate("verify-phone", phone_hash, now_ms, 15 * 60_000, 12)
                self._reserve_rate("verify-ip", ip_hash, now_ms, 15 * 60_000, 60)
                self.database.execute(
                    "UPDATE sms_challenges SET verify_attempts = verify_attempts + 1 WHERE phone_hash = ?",
                    (phone_hash,),
                )
            self._active_verifications.add(phone_hash)

        try:
            verified = await self.sms_provider.verify_code(phone, code)
        except SmsProviderError as exc:
            _safe_log("sms_provider_error", operation=exc.operation, provider_code=exc.provider_code)
            raise AuthError(
                503,
                "SMS_VERIFY_UNAVAILABLE",
                "验证码暂时无法核验，请稍后重试",
                retry_after_seconds=30,
            ) from exc
        finally:
            with self._lock:
                self._active_verifications.discard(phone_hash)

        if not verified:
            raise AuthError(401, "INVALID_SMS_CODE", "验证码错误或已过期")

        with self._lock, self.database:
            self.database.execute("DELETE FROM sms_challenges WHERE phone_hash = ?", (phone_hash,))
            user = self.database.execute(
                "SELECT id, phone_last4, password_hash FROM users WHERE phone_hash = ?",
                (phone_hash,),
            ).fetchone()
            if user and user["password_hash"] is not None:
                session_token = self._insert_session(user["id"], now_ms)
                return VerificationResult(
                    status="authenticated",
                    phone_last4=user["phone_last4"],
                    session_token=session_token,
                )

            setup_token = secrets.token_urlsafe(32)
            setup_hash = self._keyed_hash("password-setup", setup_token)
            self.database.execute("DELETE FROM password_setups WHERE phone_hash = ?", (phone_hash,))
            self.database.execute(
                """
                INSERT INTO password_setups(
                    token_hash, phone_hash, phone_last4, created_at_ms, expires_at_ms, consumed_at_ms
                ) VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (setup_hash, phone_hash, phone[-4:], now_ms, now_ms + SETUP_TTL_SECONDS * 1000),
            )
            return VerificationResult(
                status="password_required",
                phone_last4=phone[-4:],
                setup_token=setup_token,
            )

    def setup_password(
        self, setup_token: str, password: str, password_confirmation: str
    ) -> tuple[AuthUser, str]:
        normalized = validate_password(password, password_confirmation)
        setup_hash = self._keyed_hash("password-setup", setup_token)
        salt = secrets.token_bytes(16)
        password_hash = self._password_hash(normalized, salt)
        now_ms = self._now_ms()

        with self._lock, self.database:
            self._prune(now_ms)
            setup = self.database.execute(
                """
                SELECT phone_hash, phone_last4 FROM password_setups
                WHERE token_hash = ? AND consumed_at_ms IS NULL AND expires_at_ms > ?
                """,
                (setup_hash, now_ms),
            ).fetchone()
            if not setup:
                raise AuthError(401, "PASSWORD_SETUP_EXPIRED", "设密凭证已过期，请重新验证手机号")
            user = self.database.execute(
                "SELECT id FROM users WHERE phone_hash = ?", (setup["phone_hash"],)
            ).fetchone()
            if user:
                user_id = user["id"]
                self.database.execute(
                    """
                    UPDATE users SET password_salt = ?, password_hash = ?, updated_at_ms = ?
                    WHERE id = ?
                    """,
                    (salt, password_hash, now_ms, user_id),
                )
            else:
                user_id = str(uuid4())
                self.database.execute(
                    """
                    INSERT INTO users(
                        id, phone_hash, phone_last4, password_salt, password_hash,
                        created_at_ms, updated_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        setup["phone_hash"],
                        setup["phone_last4"],
                        salt,
                        password_hash,
                        now_ms,
                        now_ms,
                    ),
                )
            self.database.execute(
                "UPDATE password_setups SET consumed_at_ms = ? WHERE token_hash = ?",
                (now_ms, setup_hash),
            )
            session_token = self._insert_session(user_id, now_ms)
            return AuthUser(user_id=user_id, phone_last4=setup["phone_last4"]), session_token

    def password_login(self, phone_input: str, password: str, client_ip: str) -> tuple[AuthUser, str]:
        phone = normalize_phone(phone_input)
        phone_hash = self._keyed_hash("phone", phone)
        ip_hash = self._keyed_hash("ip", normalize_ip(client_ip))
        now_ms = self._now_ms()
        with self._lock:
            self._prune(now_ms)
            with self.database:
                self._reserve_rate("login-phone", phone_hash, now_ms, 15 * 60_000, 10)
                self._reserve_rate("login-ip", ip_hash, now_ms, 15 * 60_000, 60)
            user = self.database.execute(
                """
                SELECT id, phone_last4, password_salt, password_hash
                FROM users WHERE phone_hash = ?
                """,
                (phone_hash,),
            ).fetchone()

        candidate_hash = self._password_hash(
            password,
            bytes(user["password_salt"]) if user and user["password_salt"] else self._dummy_salt,
        )
        expected = (
            bytes(user["password_hash"])
            if user and user["password_hash"]
            else self._dummy_password_hash
        )
        if not user or not hmac.compare_digest(candidate_hash, expected):
            raise AuthError(401, "INVALID_CREDENTIALS", "手机号或密码不正确")

        with self._lock, self.database:
            session_token = self._insert_session(user["id"], now_ms)
        return AuthUser(user_id=user["id"], phone_last4=user["phone_last4"]), session_token

    def authenticate_session(self, session_token: str | None) -> AuthUser:
        if not session_token or len(session_token) > 256:
            raise AuthError(401, "AUTHENTICATION_REQUIRED", "请先登录")
        token_hash = self._keyed_hash("session", session_token)
        now_ms = self._now_ms()
        with self._lock:
            self._prune(now_ms)
            row = self.database.execute(
                """
                SELECT s.id, s.user_id, s.last_seen_at_ms, u.phone_last4
                FROM auth_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.revoked_at_ms IS NULL AND s.expires_at_ms > ?
                """,
                (token_hash, now_ms),
            ).fetchone()
            if not row:
                raise AuthError(401, "AUTHENTICATION_REQUIRED", "请先登录")
            if now_ms - row["last_seen_at_ms"] >= 5 * 60_000:
                with self.database:
                    self.database.execute(
                        "UPDATE auth_sessions SET last_seen_at_ms = ? WHERE id = ?",
                        (now_ms, row["id"]),
                    )
            return AuthUser(user_id=row["user_id"], phone_last4=row["phone_last4"])

    def logout(self, session_token: str | None) -> None:
        if not session_token or len(session_token) > 256:
            return
        token_hash = self._keyed_hash("session", session_token)
        now_ms = self._now_ms()
        with self._lock, self.database:
            self.database.execute(
                "UPDATE auth_sessions SET revoked_at_ms = ? WHERE token_hash = ? AND revoked_at_ms IS NULL",
                (now_ms, token_hash),
            )

    def health(self) -> bool:
        try:
            with self._lock:
                return self.database.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        except sqlite3.Error:
            return False

    def _insert_session(self, user_id: str, now_ms: int) -> str:
        token = secrets.token_urlsafe(32)
        self.database.execute(
            """
            INSERT INTO auth_sessions(
                id, user_id, token_hash, created_at_ms, expires_at_ms, last_seen_at_ms, revoked_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                str(uuid4()),
                user_id,
                self._keyed_hash("session", token),
                now_ms,
                now_ms + self.settings.auth_session_days * 86_400_000,
                now_ms,
            ),
        )
        return token

    def _reserve_rate(
        self,
        event_kind: str,
        key_hash: str,
        now_ms: int,
        window_ms: int,
        limit: int,
    ) -> None:
        count = self.database.execute(
            """
            SELECT COUNT(*) FROM auth_rate_events
            WHERE event_kind = ? AND key_hash = ? AND created_at_ms > ?
            """,
            (event_kind, key_hash, now_ms - window_ms),
        ).fetchone()[0]
        if count >= limit:
            retry = max(30, window_ms // 1000)
            raise AuthError(429, "AUTH_RATE_LIMITED", "操作过于频繁，请稍后再试", retry_after_seconds=retry)
        self.database.execute(
            "INSERT INTO auth_rate_events(event_kind, key_hash, created_at_ms) VALUES (?, ?, ?)",
            (event_kind, key_hash, now_ms),
        )

    def _prune(self, now_ms: int) -> None:
        with self.database:
            self.database.execute("DELETE FROM sms_challenges WHERE expires_at_ms <= ?", (now_ms,))
            self.database.execute("DELETE FROM password_setups WHERE expires_at_ms <= ?", (now_ms,))
            self.database.execute("DELETE FROM auth_rate_events WHERE created_at_ms <= ?", (now_ms - 86_400_000,))
            self.database.execute(
                "DELETE FROM auth_sessions WHERE expires_at_ms <= ? OR (revoked_at_ms IS NOT NULL AND revoked_at_ms <= ?)",
                (now_ms, now_ms - 86_400_000),
            )

    def _keyed_hash(self, namespace: str, value: str) -> str:
        return hmac.new(self._secret, f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()

    def _digest(self, value: str) -> bytes:
        return hmac.new(self._secret, value.encode(), hashlib.sha256).digest()

    @staticmethod
    def _password_hash(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            maxmem=64 * 1024 * 1024,
            dklen=32,
        )

    def _now_ms(self) -> int:
        return int(self._now() * 1000)


def normalize_phone(value: str) -> str:
    text = re.sub(r"[\s()-]", "", str(value or ""))
    if text.startswith("+86"):
        text = text[3:]
    elif len(text) == 13 and text.startswith("86"):
        text = text[2:]
    if not re.fullmatch(r"1[3-9][0-9]{9}", text):
        raise AuthError(400, "INVALID_PHONE", "请输入有效的中国大陆手机号")
    return text


def normalize_code(value: str, length: int) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(rf"[0-9]{{{length}}}", text):
        raise AuthError(400, "INVALID_SMS_CODE_FORMAT", f"请输入 {length} 位数字验证码")
    return text


def normalize_ip(value: str) -> str:
    text = str(value or "unknown").strip()
    return text[:128] or "unknown"


def validate_password(password: str, confirmation: str) -> str:
    if password != confirmation:
        raise AuthError(400, "PASSWORD_MISMATCH", "两次输入的密码不一致")
    if not 8 <= len(password) <= 64 or len(password.encode("utf-8")) > 256:
        raise AuthError(400, "INVALID_PASSWORD", "密码需为 8-64 个字符")
    if any(ord(character) < 32 or ord(character) == 127 for character in password):
        raise AuthError(400, "INVALID_PASSWORD", "密码不能包含控制字符")
    if not any(character.isalpha() for character in password) or not any(
        character.isdigit() for character in password
    ):
        raise AuthError(400, "INVALID_PASSWORD", "密码需同时包含字母和数字")
    return password


def _safe_log(event: str, **fields: str) -> None:
    safe_fields = " ".join(f"{key}={value[:80]}" for key, value in fields.items())
    print(f"auth_event={event} {safe_fields}", flush=True)
