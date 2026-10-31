from datetime import date, datetime
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
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

    def test_article_payload_requires_three_bounded_analytical_sections_and_official_reference(self) -> None:
        source = {
            "title": "当日政策要闻",
            "date": "2026-09-19",
            "url": "https://www.gov.cn/example.htm",
            "excerpt": "公开信息",
        }
        paragraph = "政" * 159 + "但"
        payload = {
            "title": "标题",
            "desc": "这是一段事实摘要",
            "relation": "旅游从业者 / 房车消费者",
            "summary": ["事实一", "事实二", "事实三"],
            "sections": [
                {"heading": "核对发布内容", "body": paragraph},
                {"heading": "梳理执行环节", "body": paragraph},
                {"heading": "观察后续影响", "body": paragraph},
            ],
            "references": [{"title": source["title"], "date": source["date"], "url": source["url"]}],
        }

        self.assertTrue(daily_articles._article_payload_is_valid(payload, {source["url"]: source}))
        for section in payload["sections"]:
            section["body"] = "政" * 160
        self.assertFalse(daily_articles._article_payload_is_valid(payload, {source["url"]: source}))
        for section in payload["sections"]:
            section["body"] = paragraph
        payload["sections"][2]["body"] = "政" * 159
        self.assertFalse(daily_articles._article_payload_is_valid(payload, {source["url"]: source}))
        payload["sections"][2]["body"] = "政" * 300 + "但"
        self.assertFalse(daily_articles._article_payload_is_valid(payload, {source["url"]: source}))

    def test_daily_prompt_limits_materials_to_today_and_previous_day(self) -> None:
        prompt = daily_articles._daily_article_prompt(date(2026, 9, 19))

        self.assertIn("2026-09-19 或 2026-09-18", prompt)
        self.assertIn("硬性范围是 160–300 个可见字符", prompt)
        self.assertIn("至少点出一个可能的代价、风险或受损群体", prompt)

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
            paragraph = "政" * 159 + "但"
            for index in range(1, 5):
                db.add(
                    ContentArticle(
                        article_id=f"article-{index}",
                        title=f"Article {index}",
                        is_today=True,
                        today_order=index,
                        sort_order=index,
                        sections=[
                            {"heading": "核对事实", "body": paragraph},
                            {"heading": "梳理背景", "body": paragraph},
                            {"heading": "观察影响", "body": paragraph},
                        ],
                        references=[
                            {
                                "title": "当日政策要闻",
                                "org": "中国政府网",
                                "date": "2026-07-03",
                                "url": "https://www.gov.cn/example.htm",
                            }
                        ],
                    )
                )
            db.commit()

            articles = daily_articles._fallback_articles(db, date(2026, 7, 3))

        expected_offset = int("20260703") % 4
        expected = [f"article-{((expected_offset + index) % 4) + 1}" for index in range(4)]
        self.assertEqual([article.article_id for article in articles], expected)

    def test_scheduler_replaces_a_full_fallback_set(self) -> None:
        selected_date = date(2026, 7, 3)
        with self.Session() as db:
            old = [ContentArticle(article_id=f"old-{i}", title="Old") for i in range(5)]
            db.add_all(old)
            db.flush()
            db.add_all([DailyArticleSet(content_date=selected_date, article_id=a.article_id, position=i)
                        for i, a in enumerate(old, 1)])
            db.commit()
            def generate(session, content_date):
                rows = [ContentArticle(article_id=f"fresh-{i}", title="Fresh") for i in range(5)]
                session.add_all(rows)
                session.flush()
                return rows
            with patch.object(daily_articles, "SessionLocal", return_value=db), \
                 patch.object(daily_articles, "get_content_date", return_value=selected_date), \
                 patch.object(daily_articles, "_generate_ai_articles", side_effect=generate):
                daily_articles.scheduled_daily_article_refresh()
                rows = daily_articles._daily_articles_for_date(db, selected_date)
                self.assertEqual([a.article_id for a in rows], [f"fresh-{i}" for i in range(5)])


class ReadOnlyDailyArticleTests(unittest.TestCase):
    """Request-thread reads must never fetch sources or call the AI model."""

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

    def _seed_pool(self, db, count: int = 5) -> list[ContentArticle]:
        rows = [
            ContentArticle(
                article_id=f"pool-{index}",
                title=f"Pool {index}",
                is_today=True,
                today_order=index,
                sort_order=index,
            )
            for index in range(1, count + 1)
        ]
        db.add_all(rows)
        db.commit()
        return rows

    def test_read_falls_back_to_latest_day_without_generating(self) -> None:
        with self.Session() as db:
            rows = self._seed_pool(db)
            db.add_all(
                [
                    DailyArticleSet(content_date=date(2026, 7, 1), article_id=rows[0].article_id, position=1),
                    DailyArticleSet(content_date=date(2026, 7, 1), article_id=rows[1].article_id, position=2),
                ]
            )
            db.commit()

            with patch.object(daily_articles, "_generate_ai_articles") as generate:
                articles = daily_articles.read_daily_articles(db, date(2026, 7, 5))

            generate.assert_not_called()

        self.assertEqual([article.article_id for article in articles], ["pool-1", "pool-2"])

    def test_read_without_any_set_returns_fallback_pool_without_generating(self) -> None:
        with self.Session() as db:
            self._seed_pool(db)
            with patch.object(daily_articles, "_generate_ai_articles") as generate, \
                 patch.object(daily_articles, "_fetch_recent_policy_materials") as fetch:
                articles = daily_articles.read_daily_articles(db, date(2026, 7, 5))

            generate.assert_not_called()
            fetch.assert_not_called()

        self.assertEqual(len(articles), 5)

    def test_generation_failure_rolls_back_partial_rows(self) -> None:
        selected_date = date(2026, 7, 3)
        with self.Session() as db:
            self._seed_pool(db)

            def generate(session, content_date):
                session.add(ContentArticle(article_id="half-written", title="Half"))
                session.flush()
                raise RuntimeError("model exploded")

            with patch.object(daily_articles, "_generate_ai_articles", side_effect=generate):
                articles = daily_articles.generate_daily_articles(db, selected_date)

            leftover = db.query(ContentArticle).filter(ContentArticle.article_id == "half-written").count()
            stored_ids = [row.article_id for row in daily_articles._daily_articles_for_date(db, selected_date)]

        # The half-written row is gone, and the fallback pool was committed
        # alone instead of being mixed with the failed generation.
        self.assertEqual(leftover, 0)
        self.assertEqual(len(stored_ids), 5)
        self.assertFalse(any(article_id.startswith("half-written") for article_id in stored_ids))
        self.assertEqual(len(articles), 5)

    def test_incomplete_generation_does_not_commit_partial_set(self) -> None:
        selected_date = date(2026, 7, 3)
        with self.Session() as db:
            self._seed_pool(db)

            def generate(session, content_date):
                # Only 2 of the 5 required articles were upserted.
                rows = [ContentArticle(article_id=f"partial-{i}", title="Partial") for i in range(2)]
                session.add_all(rows)
                session.flush()
                return rows

            with patch.object(daily_articles, "_generate_ai_articles", side_effect=generate):
                daily_articles.generate_daily_articles(db, selected_date)

            stored_ids = [row.article_id for row in daily_articles._daily_articles_for_date(db, selected_date)]

        self.assertEqual(len(stored_ids), 5)
        self.assertFalse(any(article_id.startswith("partial-") for article_id in stored_ids))

    def test_integrity_error_rereads_instead_of_raising(self) -> None:
        selected_date = date(2026, 7, 3)
        with self.Session() as db:
            self._seed_pool(db)
            with patch.object(daily_articles, "_generate_ai_articles", return_value=[]), \
                 patch.object(
                     daily_articles,
                     "_replace_daily_set",
                     side_effect=IntegrityError("insert", {}, Exception("duplicate")),
                 ):
                articles = daily_articles.generate_daily_articles(db, selected_date)

        self.assertEqual(articles, [])


if __name__ == "__main__":
    unittest.main()
