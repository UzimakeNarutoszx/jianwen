"""Quota accounting, token revocation and avatar replacement behaviour."""

import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api.v1 import content, profile
from app.core.security import create_access_token, decode_access_token
from app.crud.user import (
    AiQuotaExceeded,
    ai_quota_used,
    consume_ai_quota,
    create_user,
    reset_password,
)
from app.db.base import Base
from app.models.profile import UserAiDailyUsage, UserAiUsageRecord
from app.models.user import User


PHONE = "19900000008"


class SessionTestBase(unittest.TestCase):
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

    def _user(self, db) -> User:
        return create_user(db, phone=PHONE, nickname="Tester", password="secret12")


class AiQuotaTests(SessionTestBase):
    def test_quota_is_charged_on_the_daily_counter(self) -> None:
        with self.Session() as db:
            user = self._user(db)
            consume_ai_quota(db, user.id, limit=3)
            consume_ai_quota(db, user.id, limit=3)
            self.assertEqual(ai_quota_used(db, user.id), 2)

    def test_limit_is_enforced_with_the_original_error_code(self) -> None:
        with self.Session() as db:
            user = self._user(db)
            for _ in range(3):
                consume_ai_quota(db, user.id, limit=3)
            with self.assertRaises(AiQuotaExceeded):
                consume_ai_quota(db, user.id, limit=3)
            self.assertEqual(ai_quota_used(db, user.id), 3)

    def test_deleting_records_does_not_restore_quota(self) -> None:
        with self.Session() as db:
            user = self._user(db)
            for _ in range(2):
                consume_ai_quota(db, user.id, limit=2)
                db.add(UserAiUsageRecord(user_id=user.id, question="问", answer="答"))
            db.commit()

            # DELETE /profile/ai-records clears the history rows only.
            response = profile.clear_ai_records(current_user=user, db=db)
            self.assertIn("已清空", response.message)
            self.assertEqual(db.query(UserAiUsageRecord).count(), 0)

            self.assertEqual(ai_quota_used(db, user.id), 2)
            with self.assertRaises(AiQuotaExceeded):
                consume_ai_quota(db, user.id, limit=2)

    def test_quota_resets_on_the_next_china_day(self) -> None:
        with self.Session() as db:
            user = self._user(db)
            today = date(2026, 7, 3)
            consume_ai_quota(db, user.id, limit=1, usage_date=today)
            with self.assertRaises(AiQuotaExceeded):
                consume_ai_quota(db, user.id, limit=1, usage_date=today)
            consume_ai_quota(db, user.id, limit=1, usage_date=today + timedelta(days=1))
            self.assertEqual(ai_quota_used(db, user.id, today + timedelta(days=1)), 1)

    def test_insert_fallback_survives_a_unique_conflict(self) -> None:
        """The INSERT path must retry the UPDATE when another request won the race."""

        with self.Session() as db:
            user = self._user(db)
            day = date(2026, 7, 3)
            calls = {"n": 0}
            real_lookup = __import__("app.crud.user", fromlist=["_ai_usage_row"])._ai_usage_row

            def fake_lookup(session, user_id, usage_date):
                # Hide the row for the first UPDATE/INSERT decision so the INSERT
                # branch runs against the row the "other request" already wrote.
                calls["n"] += 1
                if calls["n"] == 1:
                    return None
                return real_lookup(session, user_id, usage_date)

            db.add(UserAiDailyUsage(user_id=user.id, usage_date=day, count=1))
            db.commit()

            with patch("app.crud.user._ai_usage_row", side_effect=fake_lookup):
                consume_ai_quota(db, user.id, limit=3, usage_date=day)

            self.assertEqual(ai_quota_used(db, user.id, day), 2)

            # Once the limit is reached the retry must not overrun it.
            db.query(UserAiDailyUsage).update({UserAiDailyUsage.count: 3})
            db.commit()
            with patch("app.crud.user._ai_usage_row", side_effect=fake_lookup), \
                 self.assertRaises(AiQuotaExceeded):
                consume_ai_quota(db, user.id, limit=3, usage_date=day)

    def test_ensure_ai_quota_returns_429_when_exhausted(self) -> None:
        with self.Session() as db:
            user = self._user(db)
            with patch.object(content, "settings", SimpleNamespace(AI_DAILY_QUESTION_LIMIT=1)):
                content._ensure_ai_quota(db, user)
                with self.assertRaises(HTTPException) as raised:
                    content._ensure_ai_quota(db, user)
            self.assertEqual(raised.exception.status_code, 429)
            self.assertIn("额度已用完", raised.exception.detail)

    def test_ai_quota_endpoint_reports_remaining_questions(self) -> None:
        with self.Session() as db:
            user = self._user(db)
            with patch.object(content, "settings", SimpleNamespace(AI_DAILY_QUESTION_LIMIT=4)):
                content._ensure_ai_quota(db, user)
                response = content.get_ai_quota(current_user=user, db=db)
            self.assertEqual(response, {"limit": 4, "used": 1, "remaining": 3})


class TokenVersionTests(SessionTestBase):
    def test_token_carries_and_reads_the_version(self) -> None:
        token = create_access_token(7, token_version=3)
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual((payload.user_id, payload.token_version), (7, 3))

    def test_tokens_without_a_version_claim_count_as_zero(self) -> None:
        import base64
        import hashlib
        import hmac
        import json

        from app.core.config import settings

        # Rebuild the payload without "tv" and sign it the same way the app does.
        payload_token = create_access_token(7, token_version=0).split(".", 1)[0]
        data = json.loads(base64.urlsafe_b64decode(payload_token + "=" * (-len(payload_token) % 4)))
        data.pop("tv", None)
        rebuilt = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")
        signature = base64.urlsafe_b64encode(
            hmac.new(settings.SECRET_KEY.encode(), rebuilt.encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")

        payload = decode_access_token(f"{rebuilt}.{signature}")
        self.assertIsNotNone(payload)
        self.assertEqual((payload.user_id, payload.token_version), (7, 0))

    def test_password_reset_invalidates_old_tokens(self) -> None:
        with self.Session() as db:
            user = self._user(db)
            old_token = create_access_token(user.id, user.token_version)
            self.assertEqual(deps._load_token_user(db, old_token).id, user.id)

            reset_password(db, user, "brand-new-password")

            self.assertIsNone(deps._load_token_user(db, old_token))
            fresh_token = create_access_token(user.id, user.token_version)
            self.assertEqual(deps._load_token_user(db, fresh_token).id, user.id)

    def test_get_current_user_rejects_a_stale_token_with_401(self) -> None:
        from fastapi.security import HTTPAuthorizationCredentials

        with self.Session() as db:
            user = self._user(db)
            stale = create_access_token(user.id, user.token_version)
            reset_password(db, user, "brand-new-password")
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=stale)
            with self.assertRaises(HTTPException) as raised:
                deps.get_current_user(credentials=credentials, db=db)
            self.assertEqual(raised.exception.status_code, 401)

    def test_optional_user_returns_none_for_a_stale_token(self) -> None:
        from fastapi.security import HTTPAuthorizationCredentials

        with self.Session() as db:
            user = self._user(db)
            stale = create_access_token(user.id, user.token_version)
            reset_password(db, user, "brand-new-password")
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=stale)
            self.assertIsNone(deps.get_optional_current_user(credentials=credentials, db=db))


class AvatarReplacementTests(SessionTestBase):
    def _upload(self, data: bytes = b"png-bytes", filename: str = "avatar.png"):
        return SimpleNamespace(filename=filename, content_type="image/png", file=SimpleNamespace(read=lambda n: data))

    def test_old_avatar_file_is_removed(self) -> None:
        with TemporaryDirectory() as upload_dir, self.Session() as db:
            user = self._user(db)
            avatars = Path(upload_dir) / "avatars"
            avatars.mkdir(parents=True)
            old_file = avatars / "old.png"
            old_file.write_bytes(b"old")
            user.avatar_path = "/uploads/avatars/old.png"
            db.add(user)
            db.commit()

            with patch.object(profile, "settings", SimpleNamespace(UPLOAD_DIR=upload_dir)):
                response = profile.upload_avatar(self._upload(), current_user=user, db=db)

            self.assertFalse(old_file.exists())
            self.assertTrue((Path(upload_dir) / response.avatar_path.removeprefix("/uploads/")).is_file())

    def test_paths_outside_the_upload_directory_are_never_deleted(self) -> None:
        with TemporaryDirectory() as upload_dir, TemporaryDirectory() as outside:
            victim = Path(outside) / "keep.txt"
            victim.write_text("keep me")

            with patch.object(profile, "settings", SimpleNamespace(UPLOAD_DIR=upload_dir)):
                for avatar_path in (
                    f"{victim}",
                    "/uploads/../outside/keep.txt",
                    f"/uploads/{os_relpath(victim, Path(upload_dir))}",
                ):
                    profile._remove_old_avatar(avatar_path)

            self.assertTrue(victim.exists())

    def test_upload_avatar_is_synchronous_for_the_thread_pool(self) -> None:
        import inspect

        self.assertFalse(inspect.iscoroutinefunction(profile.upload_avatar))

    def test_empty_or_oversized_upload_is_rejected(self) -> None:
        with TemporaryDirectory() as upload_dir, self.Session() as db:
            user = self._user(db)
            with patch.object(profile, "settings", SimpleNamespace(UPLOAD_DIR=upload_dir)):
                for data in (b"", b"x" * (2 * 1024 * 1024 + 1)):
                    with self.assertRaises(HTTPException) as raised:
                        profile.upload_avatar(self._upload(data), current_user=user, db=db)
                    self.assertEqual(raised.exception.status_code, 400)


def os_relpath(target: Path, root: Path) -> str:
    import os

    return os.path.relpath(target, root)


if __name__ == "__main__":
    unittest.main()
