"""W5 backend security work: rate limits, SMS purposes, token revocation."""

import unittest
import unittest.mock
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth
from app.core import ratelimit
from app.core.config import DEFAULT_SECRET_KEY, Settings, assert_production_safe
from app.core.ratelimit import (
    LOGIN_IP,
    LOGIN_PHONE_FAILURE,
    LOGIN_PHONE_LOCK,
    SMS_CODE_PHONE_ATTEMPTS,
    SMS_IP,
    SMS_PHONE_DAILY,
    SMS_PHONE_INTERVAL,
    RateLimiter,
    RateLimitRule,
    client_ip,
    limiter,
)
from app.crud.user import PhoneAlreadyRegistered, create_user, get_user_by_phone, reset_password
from app.db.base import Base
from app.models.user import User
from app.schemas.user import ForgotPasswordRequest, LoginRequest, RegisterRequest, SendSmsRequest
from app.services import sms


PHONE = "19900000006"
OTHER_PHONE = "19900000007"


class FakeRequest:
    """Minimal stand-in for ``starlette.requests.Request``."""

    def __init__(self, host: str = "127.0.0.1", headers: dict[str, str] | None = None) -> None:
        self.client = SimpleNamespace(host=host)
        self.headers = headers or {}


class LimiterTestBase(unittest.TestCase):
    def setUp(self) -> None:
        limiter.reset()

    def tearDown(self) -> None:
        limiter.reset()


class RateLimiterUnitTests(LimiterTestBase):
    def test_sliding_window_expires_old_hits(self) -> None:
        store = RateLimiter()
        rule = RateLimitRule(limit=2, window_seconds=10)
        self.assertEqual(store.record("k", rule, now=0), 1)
        self.assertEqual(store.record("k", rule, now=5), 2)
        self.assertTrue(store.is_limited("k", rule, now=6))
        # First hit leaves the window at t=10, so only one remains.
        self.assertFalse(store.is_limited("k", rule, now=10.5))
        self.assertEqual(store.hit_count("k", rule.window_seconds, now=10.5), 1)

    def test_reset_clears_one_key_or_everything(self) -> None:
        store = RateLimiter()
        rule = RateLimitRule(limit=1, window_seconds=60)
        store.record("a", rule)
        store.record("b", rule)
        store.reset("a")
        self.assertFalse(store.is_limited("a", rule))
        self.assertTrue(store.is_limited("b", rule))
        store.reset()
        self.assertFalse(store.is_limited("b", rule))

    def test_forwarded_for_is_ignored_unless_trust_proxy(self) -> None:
        request = FakeRequest(host="10.0.0.9", headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
        self.assertEqual(client_ip(request), "10.0.0.9")
        with unittest.mock.patch.object(ratelimit, "settings", SimpleNamespace(TRUST_PROXY=True)):
            self.assertEqual(client_ip(request), "1.2.3.4")

    def test_missing_client_falls_back_to_unknown(self) -> None:
        self.assertEqual(client_ip(SimpleNamespace(client=None, headers={})), "unknown")


class LoginRateLimitTests(LimiterTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            create_user(db, phone=PHONE, nickname="Tester", password="correct-password")

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        super().tearDown()

    def _login(self, phone: str, password: str, host: str = "127.0.0.1"):
        with self.Session() as db:
            return auth.login(LoginRequest(phone=phone, password=password), FakeRequest(host), db)

    def test_unknown_phone_and_wrong_password_share_one_message(self) -> None:
        for phone, password in ((PHONE, "wrong-password"), (OTHER_PHONE, "whatever")):
            with self.assertRaises(HTTPException) as raised:
                self._login(phone, password)
            self.assertEqual(raised.exception.status_code, 401)
            self.assertEqual(raised.exception.detail, "手机号或密码错误")

    def test_five_failures_lock_the_phone_for_fifteen_minutes(self) -> None:
        for _ in range(LOGIN_PHONE_FAILURE.limit):
            with self.assertRaises(HTTPException) as raised:
                self._login(PHONE, "wrong-password")
            self.assertEqual(raised.exception.status_code, 401)

        # Lock is active even for the correct password.
        with self.assertRaises(HTTPException) as raised:
            self._login(PHONE, "correct-password")
        self.assertEqual(raised.exception.status_code, 429)
        self.assertIn("15 分钟", raised.exception.detail)

        # Simulate the lock window passing.
        limiter.reset(ratelimit.login_lock_key(PHONE))
        response = self._login(PHONE, "correct-password")
        self.assertTrue(response.access_token)

    def test_lock_key_is_freed_after_the_window(self) -> None:
        store = RateLimiter()
        key = "login:lock:test"
        store.record(key, LOGIN_PHONE_LOCK, now=0)
        self.assertTrue(store.is_limited(key, LOGIN_PHONE_LOCK, now=1))
        self.assertFalse(store.is_limited(key, LOGIN_PHONE_LOCK, now=LOGIN_PHONE_LOCK.window_seconds + 1))

    def test_same_ip_is_capped_per_minute(self) -> None:
        for index in range(LOGIN_IP.limit):
            with self.assertRaises(HTTPException):
                self._login(f"1390000{index:04d}", "wrong-password", host="10.1.1.1")
        with self.assertRaises(HTTPException) as raised:
            self._login(PHONE, "correct-password", host="10.1.1.1")
        self.assertEqual(raised.exception.status_code, 429)
        # Another IP is unaffected.
        self.assertTrue(self._login(PHONE, "correct-password", host="10.1.1.2").access_token)


class SendSmsRateLimitTests(LimiterTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        super().tearDown()

    def _send(self, phone: str = PHONE, host: str = "127.0.0.1", scene: str = "register"):
        local = SimpleNamespace(
            SMS_PROVIDER="local", SMS_DEV_CODE="123456", ALIYUN_DYPNS_VALID_TIME=300, is_development=True
        )
        with self.Session() as db:
            with unittest.mock.patch.object(auth, "send_sms") as sender, \
                 unittest.mock.patch.object(auth, "settings", local):
                response = auth.send_sms_code(SendSmsRequest(phone=phone, scene=scene), FakeRequest(host), db)
                return response, sender

    def test_second_request_within_a_minute_is_rejected(self) -> None:
        response, sender = self._send()
        self.assertIn("开发验证码", response.message)
        sender.assert_called_once()

        with self.assertRaises(HTTPException) as raised:
            self._send()
        self.assertEqual(raised.exception.status_code, 429)
        self.assertIn("频繁", raised.exception.detail)

    def test_daily_cap_per_phone(self) -> None:
        for _ in range(SMS_PHONE_DAILY.limit):
            limiter.reset(ratelimit.sms_phone_key(PHONE))
            self._send()
        limiter.reset(ratelimit.sms_phone_key(PHONE))
        with self.assertRaises(HTTPException) as raised:
            self._send()
        self.assertEqual(raised.exception.status_code, 429)
        self.assertIn("上限", raised.exception.detail)

    def test_ip_hourly_cap(self) -> None:
        for index in range(SMS_IP.limit):
            self._send(f"1370000{index:04d}", host="10.2.2.2")
        with self.assertRaises(HTTPException) as raised:
            self._send("19900000002", host="10.2.2.2")
        self.assertEqual(raised.exception.status_code, 429)
        # A different IP can still request codes.
        self._send("19900000001", host="10.2.2.3")

    def test_rule_constants_match_the_spec(self) -> None:
        self.assertEqual((LOGIN_PHONE_FAILURE.limit, LOGIN_PHONE_FAILURE.window_seconds), (5, 900))
        self.assertEqual((LOGIN_IP.limit, LOGIN_IP.window_seconds), (20, 60))
        self.assertEqual((SMS_PHONE_INTERVAL.limit, SMS_PHONE_INTERVAL.window_seconds), (1, 60))
        self.assertEqual((SMS_PHONE_DAILY.limit, SMS_PHONE_DAILY.window_seconds), (10, 86400))
        self.assertEqual((SMS_IP.limit, SMS_IP.window_seconds), (30, 3600))
        self.assertEqual(SMS_CODE_PHONE_ATTEMPTS.limit, 5)


class SendSmsOrderingTests(SendSmsRateLimitTests):
    """限流必须在注册状态检查之前：否则 409/404 可被用来枚举号码。"""

    def test_ip_limit_wins_over_the_registration_check(self) -> None:
        with self.Session() as db:
            create_user(db, phone=PHONE, nickname="Tester", password="secret12")
        for index in range(SMS_IP.limit):
            limiter.record(ratelimit.sms_ip_key("10.9.9.9"), SMS_IP)

        local = SimpleNamespace(
            SMS_PROVIDER="local", SMS_DEV_CODE="123456", ALIYUN_DYPNS_VALID_TIME=300, is_development=True
        )
        with self.Session() as db, \
             unittest.mock.patch.object(auth, "send_sms") as sender, \
             unittest.mock.patch.object(auth, "settings", local):
            with self.assertRaises(HTTPException) as raised:
                auth.send_sms_code(SendSmsRequest(phone=PHONE, scene="register"), FakeRequest("10.9.9.9"), db)

        # 已注册号码在限流生效后只能看到 429，看不到 409。
        self.assertEqual(raised.exception.status_code, 429)
        sender.assert_not_called()

    def test_phone_interval_wins_over_the_registration_check(self) -> None:
        with self.Session() as db:
            create_user(db, phone=PHONE, nickname="Tester", password="secret12")
        limiter.record(ratelimit.sms_phone_key(PHONE), SMS_PHONE_INTERVAL)

        local = SimpleNamespace(
            SMS_PROVIDER="local", SMS_DEV_CODE="123456", ALIYUN_DYPNS_VALID_TIME=300, is_development=True
        )
        with self.Session() as db, unittest.mock.patch.object(auth, "settings", local):
            with self.assertRaises(HTTPException) as raised:
                auth.send_sms_code(SendSmsRequest(phone=PHONE, scene="register"), FakeRequest(), db)

        self.assertEqual(raised.exception.status_code, 429)

    def test_registered_number_still_gets_409_without_limits(self) -> None:
        with self.Session() as db:
            create_user(db, phone=PHONE, nickname="Tester", password="secret12")

        local = SimpleNamespace(
            SMS_PROVIDER="local", SMS_DEV_CODE="123456", ALIYUN_DYPNS_VALID_TIME=300, is_development=True
        )
        with self.Session() as db, \
             unittest.mock.patch.object(auth, "settings", local), \
             unittest.mock.patch.object(auth, "send_sms"):
            with self.assertRaises(HTTPException) as raised:
                auth.send_sms_code(SendSmsRequest(phone=PHONE, scene="register"), FakeRequest(), db)
        self.assertEqual(raised.exception.status_code, 409)


class ForgotPasswordRateLimitTests(LimiterTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.local_settings = SimpleNamespace(
            SMS_PROVIDER="local", SMS_DEV_CODE="123456", ALIYUN_DYPNS_VALID_TIME=300
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        super().tearDown()

    def _reset(self, phone: str = PHONE, host: str = "127.0.0.1"):
        with self.Session() as db:
            return auth.forgot_password(
                ForgotPasswordRequest(phone=phone, new_password="new-password", sms_code="123456"),
                FakeRequest(host),
                db,
            )

    def test_ip_limit_blocks_the_registration_lookup(self) -> None:
        for index in range(SMS_IP.limit):
            limiter.record(ratelimit.sms_ip_key("10.3.3.3"), SMS_IP)
        with self.assertRaises(HTTPException) as raised:
            self._reset(phone=OTHER_PHONE, host="10.3.3.3")
        # 未注册号码在限流生效时只看到 429，看不到 404。
        self.assertEqual(raised.exception.status_code, 429)

    def test_unknown_number_is_404_without_limits(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            self._reset(phone=OTHER_PHONE)
        self.assertEqual(raised.exception.status_code, 404)

    def test_repeated_reset_requests_are_capped_per_phone(self) -> None:
        with self.Session() as db:
            create_user(db, phone=PHONE, nickname="Tester", password="old-password")
        # 每一次都耗尽 60 秒的手机号窗口，第二次必须被挡住。
        for _ in range(SMS_PHONE_DAILY.limit):
            limiter.record(ratelimit.sms_phone_key(PHONE), SMS_PHONE_INTERVAL)
        limiter.reset(ratelimit.sms_phone_key(PHONE))
        limiter.record(ratelimit.sms_phone_key(PHONE), SMS_PHONE_INTERVAL)
        for _ in range(SMS_PHONE_DAILY.limit):
            limiter.record(ratelimit.sms_phone_daily_key(PHONE), SMS_PHONE_DAILY)

        with self.Session() as db, unittest.mock.patch.object(auth, "settings", self.local_settings):
            with self.assertRaises(HTTPException) as raised:
                auth.forgot_password(
                    ForgotPasswordRequest(phone=PHONE, new_password="new-password", sms_code="123456"),
                    FakeRequest(),
                    db,
                )
        self.assertEqual(raised.exception.status_code, 429)
        self.assertIn("上限", raised.exception.detail)


class SmsPurposeTests(LimiterTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        # SMS_PROVIDER=local and the dev code are what the test environment uses.
        self.local_settings = SimpleNamespace(
            SMS_PROVIDER="local", SMS_DEV_CODE="123456", ALIYUN_DYPNS_VALID_TIME=300
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        super().tearDown()

    def _target(self):
        """Patch ``settings`` where the sms service reads it."""
        return unittest.mock.patch.object(sms, "settings", self.local_settings)

    def _issue(self, db, scene: str = "register") -> None:
        """Simulate a sent code: the provider stub plus our purpose record."""
        with self._target():
            sms.send_sms(PHONE, scene)
        sms.record_code_issued(db, PHONE, scene)

    def test_register_code_cannot_reset_a_password(self) -> None:
        with self.Session() as db:
            user = create_user(db, phone=PHONE, nickname="Tester", password="old-password")
            original_hash = user.password_hash

            self._issue(db, "register")
            with self._target(), self.assertRaises(HTTPException) as raised:
                auth.forgot_password(
                    ForgotPasswordRequest(phone=PHONE, new_password="new-password", sms_code="123456"), db
                )
            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(raised.exception.detail, "验证码输入错误，请重新输入")

            db.refresh(user)
            self.assertEqual(user.password_hash, original_hash)

    def test_reset_code_works_for_password_reset(self) -> None:
        with self.Session() as db:
            create_user(db, phone=PHONE, nickname="Tester", password="old-password")
            self._issue(db, "reset_password")
            with self._target():
                response = auth.forgot_password(
                    ForgotPasswordRequest(phone=PHONE, new_password="new-password", sms_code="123456"), db
                )
            self.assertIn("密码已重置", response.message)

    def test_register_scene_verifies_with_register_purpose(self) -> None:
        with self.Session() as db:
            self._issue(db, "register")
            with self._target():
                response = auth.register(
                    RegisterRequest(phone=PHONE, nickname="新用户", password="secret12", sms_code="123456"), db
                )
            self.assertTrue(response.access_token)
            self.assertIsNotNone(get_user_by_phone(db, PHONE))

    def test_five_wrong_codes_void_the_verification_code(self) -> None:
        with self.Session() as db:
            self._issue(db, "register")
            with self._target():
                for attempt in range(SMS_CODE_PHONE_ATTEMPTS.limit - 1):
                    self.assertFalse(
                        sms.verify_code_for_purpose(db, PHONE, f"00000{attempt}", sms.PURPOSE_REGISTER)
                    )
                self.assertEqual(
                    limiter.hit_count(sms.sms_code_attempt_key(PHONE, sms.PURPOSE_REGISTER), 900),
                    SMS_CODE_PHONE_ATTEMPTS.limit - 1,
                )
                # The 5th wrong guess closes the window.
                with self.assertRaises(sms.SmsServiceError) as raised:
                    sms.verify_code_for_purpose(db, PHONE, "000009", sms.PURPOSE_REGISTER)
                self.assertEqual(raised.exception.code, sms.CODE_ATTEMPTS_EXCEEDED)

                # The correct code no longer works either.
                with self.assertRaises(sms.SmsServiceError) as raised:
                    sms.verify_code_for_purpose(db, PHONE, "123456", sms.PURPOSE_REGISTER)
                self.assertEqual(raised.exception.code, sms.CODE_ATTEMPTS_EXCEEDED)

    def test_correct_code_resets_the_attempt_window(self) -> None:
        with self.Session() as db:
            self._issue(db, "register")
            with self._target():
                self.assertFalse(sms.verify_code_for_purpose(db, PHONE, "000000", sms.PURPOSE_REGISTER))
                self.assertEqual(
                    limiter.hit_count(sms.sms_code_attempt_key(PHONE, sms.PURPOSE_REGISTER), 900), 1
                )
                self.assertTrue(sms.verify_code_for_purpose(db, PHONE, "123456", sms.PURPOSE_REGISTER))
                self.assertEqual(
                    limiter.hit_count(sms.sms_code_attempt_key(PHONE, sms.PURPOSE_REGISTER), 900), 0
                )

    def test_code_without_a_recorded_issue_is_rejected(self) -> None:
        with self.Session() as db, self._target():
            with self.assertRaises(sms.SmsServiceError) as raised:
                sms.verify_code_for_purpose(db, PHONE, "123456", sms.PURPOSE_REGISTER)
        self.assertEqual(raised.exception.code, sms.CODE_PURPOSE_MISMATCH)

    def test_aliyun_provider_also_rejects_an_unissued_code(self) -> None:
        """没有 issue 记录时，任何 provider 都不能放行（阿里云也要拒绝）。"""
        aliyun_settings = SimpleNamespace(
            SMS_PROVIDER="aliyun", SMS_DEV_CODE="123456", ALIYUN_DYPNS_VALID_TIME=300
        )
        with self.Session() as db, \
             unittest.mock.patch.object(sms, "settings", aliyun_settings), \
             unittest.mock.patch.object(sms, "check_sms_code") as provider_check:
            with self.assertRaises(sms.SmsServiceError) as raised:
                sms.verify_code_for_purpose(db, PHONE, "123456", sms.PURPOSE_REGISTER)
        self.assertEqual(raised.exception.code, sms.CODE_PURPOSE_MISMATCH)
        # 连远程校验都不该发起：没有 issue 记录就没有可验证的验证码。
        provider_check.assert_not_called()

    def test_issue_outside_the_ttl_no_longer_counts(self) -> None:
        with self.Session() as db, self._target():
            sms.record_code_issued(db, PHONE, "register")
            self.assertEqual(sms.issued_code_purpose(db, PHONE), sms.PURPOSE_REGISTER)

            import datetime as _datetime

            db.query(sms.SmsCodeIssue).update(
                {sms.SmsCodeIssue.issued_at: _datetime.datetime.now() - _datetime.timedelta(seconds=400)}
            )
            db.commit()
            self.assertIsNone(sms.issued_code_purpose(db, PHONE))

    def test_a_new_issue_replaces_the_previous_purpose(self) -> None:
        with self.Session() as db, self._target():
            sms.record_code_issued(db, PHONE, "register")
            sms.record_code_issued(db, PHONE, "reset_password")
            self.assertEqual(sms.issued_code_purpose(db, PHONE), sms.PURPOSE_RESET)
            self.assertEqual(db.query(sms.SmsCodeIssue).count(), 1)


class TokenVersionStorageTests(LimiterTestBase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_new_users_start_at_token_version_zero(self) -> None:
        with self.Session() as db:
            user = create_user(db, phone=PHONE, nickname="Tester", password="secret12")
            self.assertEqual(user.token_version, 0)

    def test_reset_password_bumps_token_version(self) -> None:
        with self.Session() as db:
            user = create_user(db, phone=PHONE, nickname="Tester", password="secret12")
            reset_password(db, user, "another-password")
            self.assertEqual(user.token_version, 1)
            reset_password(db, user, "third-password")
            self.assertEqual(user.token_version, 2)

    def test_duplicate_phone_raises_registration_conflict(self) -> None:
        with self.Session() as db:
            create_user(db, phone=PHONE, nickname="First", password="secret12")
            with self.assertRaises(PhoneAlreadyRegistered):
                create_user(db, phone=PHONE, nickname="Second", password="secret12")
            # The session is usable again after the rollback.
            self.assertEqual(db.query(User).count(), 1)


class RegisterConflictTests(LimiterTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.local_settings = SimpleNamespace(
            SMS_PROVIDER="local", SMS_DEV_CODE="123456", ALIYUN_DYPNS_VALID_TIME=300, is_development=True
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        super().tearDown()

    def test_existing_phone_still_returns_409(self) -> None:
        with self.Session() as db:
            create_user(db, phone=PHONE, nickname="Tester", password="secret12")
            with self.assertRaises(HTTPException) as raised:
                auth.register(
                    RegisterRequest(phone=PHONE, nickname="另一个", password="secret12", sms_code="123456"), db
                )
        self.assertEqual(raised.exception.status_code, 409)

    def test_concurrent_insert_conflict_returns_409(self) -> None:
        with self.Session() as db, \
             unittest.mock.patch.object(auth, "get_user_by_phone", return_value=None), \
             unittest.mock.patch.object(auth, "create_user", side_effect=PhoneAlreadyRegistered(PHONE)), \
             unittest.mock.patch.object(auth, "_verify_sms_code"):
            with self.assertRaises(HTTPException) as raised:
                auth.register(
                    RegisterRequest(phone=PHONE, nickname="并发", password="secret12", sms_code="123456"), db
                )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, "手机号已注册")

    def test_lookup_after_the_insert_failure_sees_the_other_account(self) -> None:
        """The route's pre-check is only an optimisation; the unique index decides."""
        with self.Session() as db:
            create_user(db, phone=PHONE, nickname="First", password="secret12")
            with self.assertRaises(PhoneAlreadyRegistered):
                create_user(db, phone=PHONE, nickname="Second", password="secret12")
            self.assertEqual(db.query(User).count(), 1)


class ProductionConfigTests(unittest.TestCase):
    def test_development_accepts_defaults(self) -> None:
        for environment in ("development", "test", "Dev", " local "):
            with self.subTest(environment=environment):
                assert_production_safe(environment, DEFAULT_SECRET_KEY, "local")

    def test_production_rejects_default_secret_and_local_sms(self) -> None:
        with self.assertRaises(RuntimeError):
            assert_production_safe("production", DEFAULT_SECRET_KEY, "aliyun")
        with self.assertRaises(RuntimeError):
            assert_production_safe("production", "a-real-secret", "local")
        # A properly configured deployment passes.
        assert_production_safe("production", "a-real-secret", "aliyun")

    def test_production_warns_about_wildcard_cors_only_outside_development(self) -> None:
        production = Settings(ENVIRONMENT="production", SECRET_KEY="a-real-secret", SMS_PROVIDER="aliyun")
        with self.assertLogs("app.core.config", level="WARNING") as captured:
            production.validate_startup()
        self.assertTrue(any("CORS_ORIGINS" in line for line in captured.output))

        development = Settings(ENVIRONMENT="development")
        with unittest.mock.patch("app.core.config.logger") as logger:
            development.validate_startup()
            logger.warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
