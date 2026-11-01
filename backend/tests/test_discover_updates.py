"""Discover "最近更新" must surface only AI daily articles with tiered recency."""
from datetime import date, datetime, timedelta
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import content
from app.core.timeutil import today_cn
from app.db.base import Base
from app.models.content import ContentArticle, DailyArticleSet
from app.services import seed_content as seed_content_module
from app.services.seed_content import seed_content


class DiscoverUpdatesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        # Recency tiers are relative to today, so anchor the fixtures to it.
        self.today = today_cn()

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _days_ago(self, days: int) -> date:
        return self.today - timedelta(days=days)

    def _add_ai_article(
        self,
        db,
        published: date,
        position: int = 1,
        *,
        created_at: datetime | None = None,
    ) -> ContentArticle:
        article = ContentArticle(
            article_id=f"ai-daily-{published.strftime('%Y%m%d')}-{position}",
            title=f"AI {published} #{position}",
            is_latest=True,
            is_today=True,
            sort_order=1000 + position,
        )
        if created_at is not None:
            article.created_at = created_at
        db.add(article)
        return article

    def test_seed_articles_are_excluded_from_updates(self) -> None:
        today = self._days_ago(1)
        with self.Session() as db:
            db.add(
                ContentArticle(
                    article_id="party-state",
                    title="种子测试文章",
                    is_latest=True,
                    is_today=True,
                    sort_order=1,
                )
            )
            self._add_ai_article(db, today, 2)
            db.commit()

            updates = content.get_discover_content(db).updates

        self.assertEqual([item.article_id for item in updates], [f"ai-daily-{today.strftime('%Y%m%d')}-2"])

    def test_updates_sort_by_date_desc_then_position(self) -> None:
        day1, day2, day3 = self._days_ago(3), self._days_ago(2), self._days_ago(1)
        with self.Session() as db:
            self._add_ai_article(db, day1, 3)
            self._add_ai_article(db, day3, 2)
            self._add_ai_article(db, day3, 1)
            self._add_ai_article(db, day2, 5)
            db.commit()

            updates = content.get_discover_content(db).updates

        self.assertEqual(
            [item.article_id for item in updates],
            [
                f"ai-daily-{day3.strftime('%Y%m%d')}-1",
                f"ai-daily-{day3.strftime('%Y%m%d')}-2",
                f"ai-daily-{day2.strftime('%Y%m%d')}-5",
                f"ai-daily-{day1.strftime('%Y%m%d')}-3",
            ],
        )

    def test_published_date_prefers_daily_set_then_article_id_then_created_at(self) -> None:
        with self.Session() as db:
            # 1) daily set wins over the id-embedded date
            from_set = self._add_ai_article(db, date(2026, 7, 3), 1)
            # 2) no daily set -> parse YYYYMMDD from article_id
            from_id = self._add_ai_article(db, date(2026, 7, 2), 1)
            # 3) non ai-daily article -> created_at date
            legacy = ContentArticle(
                article_id="legacy-article",
                title="Legacy",
                created_at=datetime(2026, 6, 30, 12, 0),
            )
            db.add(legacy)
            db.flush()
            db.add(DailyArticleSet(content_date=date(2026, 7, 4), article_id=from_set.article_id, position=1))
            db.commit()

            self.assertEqual(
                content._article_published_date(from_set, {from_set.article_id: date(2026, 7, 4)}),
                date(2026, 7, 4),
            )
            self.assertEqual(content._article_published_date(from_id), date(2026, 7, 2))
            self.assertEqual(content._article_published_date(legacy), date(2026, 6, 30))

    def test_published_date_is_serialized_as_iso_date(self) -> None:
        published = self._days_ago(1)
        with self.Session() as db:
            self._add_ai_article(db, published, 1)
            db.commit()

            payload = content.get_discover_content(db).model_dump(mode="json")

        self.assertEqual(payload["updates"][0]["published_date"], published.isoformat())

    def test_article_list_response_exposes_published_date_without_breaking_fields(self) -> None:
        with self.Session() as db:
            db.add(
                ContentArticle(
                    article_id="legacy-article",
                    title="Legacy",
                    desc="旧文章",
                    created_at=datetime(2026, 6, 30, 9, 0),
                )
            )
            db.commit()

            items = content.list_articles(category=None, q=None, db=db)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].published_date, date(2026, 6, 30))
        # Existing fields must stay intact for the current frontend.
        self.assertEqual(items[0].id, "legacy-article")
        self.assertEqual(items[0].article_id, "legacy-article")
        self.assertEqual(items[0].title, "Legacy")
        self.assertFalse(items[0].viewed)

    def test_recency_tiers_thin_old_articles(self) -> None:
        recent_day = self._days_ago(1)
        mid_day = self._days_ago(20)
        old_day = self._days_ago(60)
        too_old_day = self._days_ago(120)
        with self.Session() as db:
            # 0-15 days: keep everything, even 4 on the same day
            for position in range(1, 5):
                self._add_ai_article(db, recent_day, position)
            # 16-30 days: at most 2 per day
            for position in range(1, 5):
                self._add_ai_article(db, mid_day, position)
            # 31-90 days: at most 2 per ISO week
            for offset in range(3):
                day = old_day + timedelta(days=offset)
                if day.isocalendar()[:2] == old_day.isocalendar()[:2]:
                    self._add_ai_article(db, day, offset + 1)
            # older than 90 days: dropped
            self._add_ai_article(db, too_old_day, 1)
            db.commit()

            kept = content._discover_updates(db, today=self.today)
            kept_ids = [article.article_id for article in kept]

        recent = [f"ai-daily-{recent_day.strftime('%Y%m%d')}-{position}" for position in range(1, 5)]
        mid = [f"ai-daily-{mid_day.strftime('%Y%m%d')}-{position}" for position in range(1, 3)]
        self.assertEqual(kept_ids[:4], recent)
        self.assertEqual(sorted(kept_ids[4:6]), sorted(mid))
        self.assertNotIn(f"ai-daily-{too_old_day.strftime('%Y%m%d')}-1", kept_ids)
        self.assertEqual(sum(1 for item in kept_ids if item.startswith(f"ai-daily-{old_day.strftime('%Y%m')}")), 2)

    def test_updates_have_a_hard_safety_limit(self) -> None:
        with self.Session() as db:
            for index in range(130):
                self._add_ai_article(db, self._days_ago(1 + index % 10), index + 1)
            db.commit()

            kept = content._discover_updates(db, today=self.today)

        self.assertEqual(len(kept), 120)

    def test_seed_content_keeps_ai_daily_flags_but_clears_other_articles(self) -> None:
        with self.Session() as db:
            ai_article = self._add_ai_article(db, self._days_ago(1), 1)
            other = ContentArticle(article_id="stale-article", title="Stale", is_latest=True, is_today=True)
            db.add(other)
            db.commit()
            ai_article_id = ai_article.article_id

            original_import = seed_content_module.import_classic_full_texts
            seed_content_module.import_classic_full_texts = lambda session: None
            try:
                seed_content(db)
            finally:
                seed_content_module.import_classic_full_texts = original_import

            db.expire_all()
            ai_article = db.query(ContentArticle).filter(ContentArticle.article_id == ai_article_id).one()
            other = db.query(ContentArticle).filter(ContentArticle.article_id == "stale-article").one()

        self.assertTrue(ai_article.is_latest)
        self.assertTrue(ai_article.is_today)
        self.assertFalse(other.is_latest)
        self.assertFalse(other.is_today)


if __name__ == "__main__":
    unittest.main()
