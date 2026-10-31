"""Schema additions must apply to both MySQL and SQLite (W5 items 1 and 2)."""

import base64
import hashlib
import hmac
import json
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.core.config import settings
from app.db import session as db_session


class SchemaMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # Users table without the new column, like an existing production DB.
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE users ("
                    "id INTEGER PRIMARY KEY, phone VARCHAR(20) NOT NULL UNIQUE, "
                    "nickname VARCHAR(32) NOT NULL, password_hash VARCHAR(255) NOT NULL, "
                    "avatar_path VARCHAR(255) NULL, bio VARCHAR(160) NULL, "
                    "is_active BOOLEAN NOT NULL DEFAULT 1)"
                )
            )

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_table_columns_reads_names_on_sqlite(self) -> None:
        with self.engine.connect() as connection:
            columns = db_session.table_columns(connection, "users")
        self.assertIn("phone", columns)
        self.assertNotIn("token_version", columns)

    def test_token_version_column_is_added_once(self) -> None:
        with patch.object(db_session, "engine", self.engine):
            db_session.ensure_user_token_version_column()
            db_session.ensure_user_token_version_column()

        with self.engine.connect() as connection:
            columns = db_session.table_columns(connection, "users")
            # Existing rows get the documented default.
            connection.execute(text("INSERT INTO users (phone, nickname, password_hash) VALUES ('13800000001', 'n', 'h')"))
            value = connection.execute(text("SELECT token_version FROM users")).scalar_one()
        self.assertIn("token_version", columns)
        self.assertEqual(value, 0)

    def test_daily_usage_table_is_created_by_metadata(self) -> None:
        from app.db.base import Base
        from app.models.profile import UserAiDailyUsage  # noqa: F401

        Base.metadata.create_all(self.engine)
        inspector = inspect(self.engine)
        self.assertIn("user_ai_daily_usage", inspector.get_table_names())
        unique_names = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("user_ai_daily_usage")
        }
        self.assertIn("uq_user_ai_daily_usage", unique_names)

    def test_sms_code_issue_table_is_created_by_metadata(self) -> None:
        from app.db.base import Base
        from app.models.sms import SmsCodeIssue  # noqa: F401

        Base.metadata.create_all(self.engine)
        columns = {column["name"] for column in inspect(self.engine).get_columns("sms_code_issues")}
        self.assertEqual(columns, {"id", "phone", "purpose", "issued_at"})


class LegacyTokenTests(unittest.TestCase):
    """Tokens signed before the ``tv`` claim existed must keep working."""

    def _legacy_token(self, user_id: int) -> str:
        payload = {"sub": str(user_id), "exp": 2000000000}
        payload_token = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode().rstrip("=")
        signature = base64.urlsafe_b64encode(
            hmac.new(settings.SECRET_KEY.encode(), payload_token.encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")
        return f"{payload_token}.{signature}"

    def test_legacy_token_matches_token_version_zero(self) -> None:
        from app.db.base import Base
        from app.models.user import User

        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        try:
            with Session() as db:
                user = User(phone="13800000002", nickname="Legacy", password_hash="hash")
                db.add(user)
                db.commit()
                user_id = user.id

                self.assertEqual(deps._load_token_user(db, self._legacy_token(user_id)).id, user_id)

                # After a reset the legacy token is rejected.
                user.token_version = 1
                db.commit()
                self.assertIsNone(deps._load_token_user(db, self._legacy_token(user_id)))
        finally:
            Base.metadata.drop_all(engine)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
