"""连续阅读天数：今天/昨天/断签/匿名。"""

import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import content
from app.models.reading import ArticleReadingDay

TODAY = date(2026, 11, 14)


class ReadingStreakTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        ArticleReadingDay.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _read(self, *days: date, user_id: int = 1) -> None:
        with self.Session() as db:
            for index, day in enumerate(days):
                db.add(
                    ArticleReadingDay(
                        user_id=user_id,
                        article_id=f"a-{day.isoformat()}-{index}",
                        content_date=day,
                        title="t",
                    )
                )
            db.commit()

    def _streak(self) -> int:
        with self.Session() as db, patch.object(content, "get_content_date", return_value=TODAY):
            return content._reading_streak_days(db, SimpleNamespace(id=1))

    def test_anonymous_has_no_streak(self) -> None:
        with self.Session() as db, patch.object(content, "get_content_date", return_value=TODAY):
            self.assertEqual(content._reading_streak_days(db, None), 0)

    def test_three_consecutive_days_including_today(self) -> None:
        self._read(TODAY - timedelta(days=2), TODAY - timedelta(days=1), TODAY)
        self.assertEqual(self._streak(), 3)

    def test_yesterday_counts_when_today_not_read(self) -> None:
        self._read(TODAY - timedelta(days=2), TODAY - timedelta(days=1))
        self.assertEqual(self._streak(), 2)

    def test_gap_stops_streak(self) -> None:
        self._read(TODAY - timedelta(days=2), TODAY)
        self.assertEqual(self._streak(), 1)

    def test_empty_history(self) -> None:
        self.assertEqual(self._streak(), 0)


if __name__ == "__main__":
    unittest.main()
