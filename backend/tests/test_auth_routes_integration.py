"""End-to-end checks through the ASGI app for the W5 auth hardening."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api.v1 import auth as auth_module
from app.core.ratelimit import limiter
from app.db.base import Base
from app.main import app
from app.models.user import User
from app.services import sms as sms_module
from services import ai as ai_service


class AuthRouteIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        limiter.reset()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        limiter.reset()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _client(self) -> httpx.AsyncClient:
        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[deps.get_db] = override_get_db
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    def _run(self, coroutine):
        try:
            return asyncio.run(coroutine)
        finally:
            app.dependency_overrides.clear()

    def test_login_returns_429_with_a_chinese_message_after_five_failures(self) -> None:
        with self.Session() as db:
            from app.crud.user import create_user

            create_user(db, phone="19900000012", nickname="T", password="correct-password")

        async def scenario():
            async with self._client() as client:
                statuses = []
                for _ in range(5):
                    response = await client.post(
                        "/api/v1/auth/login", json={"phone": "19900000012", "password": "wrong-password"}
                    )
                    statuses.append((response.status_code, response.json()["detail"]))
                blocked = await client.post(
                    "/api/v1/auth/login", json={"phone": "19900000012", "password": "correct-password"}
                )
                return statuses, blocked

        statuses, blocked = self._run(scenario())
        self.assertTrue(all(code == 401 for code, _detail in statuses))
        self.assertEqual({detail for _code, detail in statuses}, {"手机号或密码错误"})
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("15 分钟", blocked.json()["detail"])

    def test_stale_token_is_rejected_by_a_protected_route(self) -> None:
        from app.core.security import create_access_token
        from app.crud.user import create_user, reset_password

        with self.Session() as db:
            user = create_user(db, phone="19900000011", nickname="T", password="correct-password")
            token = create_access_token(user.id, user.token_version)
            reset_password(db, user, "another-password")

        async def scenario():
            async with self._client() as client:
                return await client.get("/api/v1/profile/me", headers={"Authorization": f"Bearer {token}"})

        response = self._run(scenario())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "登录状态已失效，请重新登录")

    def test_ask_quota_survives_deleting_history(self) -> None:
        from app.api.v1 import content as content_module
        from app.core.security import create_access_token
        from app.crud.user import create_user

        with self.Session() as db:
            user = create_user(db, phone="19900000010", nickname="T", password="correct-password")
            token = create_access_token(user.id, user.token_version)

        async def scenario():
            async with self._client() as client:
                headers = {"Authorization": f"Bearer {token}"}
                with patch.object(ai_service, "_open_request", side_effect=ai_service.AIClientError("offline")), \
                     patch.object(content_module, "settings", SimpleNamespace(AI_DAILY_QUESTION_LIMIT=1)):
                    first = await client.post("/api/v1/content/ask", json={"question": "住房政策"}, headers=headers)
                    second = await client.post("/api/v1/content/ask", json={"question": "住房政策"}, headers=headers)
                cleared = await client.delete("/api/v1/profile/ai-records", headers=headers)
                with patch.object(ai_service, "_open_request", side_effect=ai_service.AIClientError("offline")), \
                     patch.object(content_module, "settings", SimpleNamespace(AI_DAILY_QUESTION_LIMIT=1)):
                    third = await client.post("/api/v1/content/ask", json={"question": "住房政策"}, headers=headers)
                return first, second, cleared, third

        first, second, cleared, third = self._run(scenario())
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(third.status_code, 429)

    def test_register_flow_binds_the_code_to_the_register_scene(self) -> None:
        # The stub provider keeps the code static, so the purpose recorded in
        # ``sms_code_issues`` is what separates the scenes.
        auth_settings = SimpleNamespace(
            SMS_PROVIDER="local", SMS_DEV_CODE="123456", ALIYUN_DYPNS_VALID_TIME=300, is_development=True
        )
        sms_settings = SimpleNamespace(
            SMS_PROVIDER="local", SMS_DEV_CODE="123456", ALIYUN_DYPNS_VALID_TIME=300
        )

        async def scenario():
            async with self._client() as client:
                with patch.object(auth_module, "settings", auth_settings), \
                     patch.object(sms_module, "settings", sms_settings):
                    sent = await client.post(
                        "/api/v1/auth/send-sms", json={"phone": "19900000009", "scene": "register"}
                    )
                    # A register code must not reset a password.
                    with patch.object(auth_module, "get_user_by_phone", return_value=object()):
                        stolen = await client.post(
                            "/api/v1/auth/forgot-password",
                            json={"phone": "19900000009", "new_password": "hijack12", "sms_code": "123456"},
                        )
                    registered = await client.post(
                        "/api/v1/auth/register",
                        json={
                            "phone": "19900000009",
                            "nickname": "注册用户",
                            "password": "secret12",
                            "sms_code": "123456",
                        },
                    )
                return sent, stolen, registered

        sent, stolen, registered = self._run(scenario())

        self.assertEqual(sent.status_code, 200)
        self.assertIn("开发验证码", sent.json()["message"])
        # Register code + reset purpose → rejected, and it must not burn the
        # register code either.
        self.assertEqual(stolen.status_code, 400)
        self.assertEqual(stolen.json()["detail"], "验证码输入错误，请重新输入")
        self.assertEqual(registered.status_code, 201)


if __name__ == "__main__":
    unittest.main()
