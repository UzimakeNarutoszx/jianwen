from datetime import datetime
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.breaking_news import BreakingNews
from app.services import breaking_news


class BreakingNewsTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)

    def test_short_and_full_plenary_names_share_identity(self):
        published = datetime(2026, 10, 25)
        self.assertEqual(
            breaking_news.identity("明天召开五中全会", published),
            breaking_news.identity("中国共产党第二十届中央委员会第五次全体会议将召开", published),
        )

    def test_requires_two_sources_and_hides_expired(self):
        now = datetime(2026, 10, 25, 8, 0)
        records = [
            {"source": "中国政府网", "title": "明天召开五中全会", "url": "https://www.gov.cn/a", "published_at": "2026-10-25", "summary": "会议将于明天召开。"},
            {"source": "新华社", "title": "明天召开五中全会", "url": "https://www.news.cn/a", "published_at": "2026-10-25", "summary": "会议将于明天召开。"},
        ]
        original = breaking_news.fetch_source_items
        try:
            breaking_news.fetch_source_items = lambda now=None: records
            with self.session() as db:
                self.assertEqual(breaking_news.refresh_breaking_news(db, now), 1)
                self.assertEqual(len(breaking_news.active_breaking_news(db, now)), 1)
                item = db.query(BreakingNews).one()
                item.latest_reported_at = datetime(2026, 10, 20)
                item.is_ongoing = False
                db.commit()
                self.assertEqual(breaking_news.active_breaking_news(db, now), [])
        finally:
            breaking_news.fetch_source_items = original

    def test_single_source_is_not_published(self):
        original = breaking_news.fetch_source_items
        try:
            breaking_news.fetch_source_items = lambda now=None: [{"source": "中国政府网", "title": "召开重要会议", "url": "https://www.gov.cn/a", "published_at": "2026-10-25", "summary": "会议正式召开。"}]
            with self.session() as db:
                self.assertEqual(breaking_news.refresh_breaking_news(db, datetime(2026, 10, 25, 8, 0)), 0)
                self.assertEqual(db.query(BreakingNews).count(), 0)
        finally:
            breaking_news.fetch_source_items = original


if __name__ == "__main__":
    unittest.main()
