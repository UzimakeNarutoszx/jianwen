from datetime import date, datetime
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.content import ContentArticle, DailyArticleSet
from app.services import daily_articles


class DailyArticleTests(unittest.TestCase):
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

    def test_content_date_rolls_over_at_six_in_shanghai(self) -> None:
        before_rollover = datetime(2026, 7, 3, 5, 59)
        at_rollover = datetime(2026, 7, 3, 6, 0)

        self.assertEqual(daily_articles.get_content_date(before_rollover), date(2026, 7, 2))
        self.assertEqual(daily_articles.get_content_date(at_rollover), date(2026, 7, 3))

    def test_extract_json_payload_accepts_markdown_fence_and_surrounding_text(self) -> None:
        fenced = '```json\n{"articles": [{"title": "A"}]}\n```'
        surrounded = 'prefix ignored {"articles": [{"title": "B"}]} suffix ignored'

        self.assertEqual(daily_articles._extract_json_payload(fenced), {"articles": [{"title": "A"}]})
        self.assertEqual(daily_articles._extract_json_payload(surrounded), {"articles": [{"title": "B"}]})

    def test_existing_daily_set_is_returned_in_position_order(self) -> None:
        with self.Session() as db:
            for index in range(1, 6):
                db.add(
                    ContentArticle(
                        article_id=f"article-{index}",
                        title=f"Article {index}",
                        is_today=True,
                        today_order=index,
                        sort_order=index,
                    )
                )
            db.flush()
            db.add_all(
                [
                    DailyArticleSet(content_date=date(2026, 7, 3), article_id="article-3", position=3),
                    DailyArticleSet(content_date=date(2026, 7, 3), article_id="article-1", position=1),
                    DailyArticleSet(content_date=date(2026, 7, 3), article_id="article-2", position=2),
                    DailyArticleSet(content_date=date(2026, 7, 3), article_id="article-5", position=5),
                    DailyArticleSet(content_date=date(2026, 7, 3), article_id="article-4", position=4),
                ]
            )
            db.commit()

            articles = daily_articles.ensure_daily_articles(db, date(2026, 7, 3))

        self.assertEqual([article.article_id for article in articles], [f"article-{index}" for index in range(1, 6)])

    def test_fallback_articles_rotate_from_content_date(self) -> None:
        with self.Session() as db:
            for index in range(1, 5):
                db.add(
                    ContentArticle(
                        article_id=f"article-{index}",
                        title=f"Article {index}",
                        is_today=True,
                        today_order=index,
                        sort_order=index,
                    )
                )
            db.commit()

            articles = daily_articles._fallback_articles(db, date(2026, 7, 3))

        expected_offset = int("20260703") % 4
        expected = [f"article-{((expected_offset + index) % 4) + 1}" for index in range(4)]
        self.assertEqual([article.article_id for article in articles], expected)


if __name__ == "__main__":
    unittest.main()
