from datetime import date, datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import content
from app.db.base import Base
from app.models.content import AiAnswerRule, ContentArticle, ContentCategory, DailyArticleSet, DailyQuote
from app.models.profile import UserBrowsingHistory, UserFollowTopic
from app.models.user import User


class ContentRouteTests(unittest.TestCase):
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

    def test_list_categories_returns_priority_categories_first(self) -> None:
        with self.Session() as db:
            db.add_all(
                [
                    ContentCategory(name="普通", is_priority=False, sort_order=1),
                    ContentCategory(name="重点二", is_priority=True, sort_order=2),
                    ContentCategory(name="重点一", is_priority=True, sort_order=1),
                ]
            )
            db.commit()

            categories = content.list_categories(db)

        self.assertEqual([category.name for category in categories], ["重点一", "重点二", "普通"])

    def test_list_articles_filters_by_category_and_keyword(self) -> None:
        with self.Session() as db:
            db.add_all(
                [
                    ContentArticle(
                        article_id="housing",
                        category="住房",
                        topic="民生",
                        title="租房补贴怎么查",
                        desc="查本地细则",
                        sources="住建部门",
                        sort_order=2,
                    ),
                    ContentArticle(
                        article_id="job",
                        category="就业",
                        topic="青年就业",
                        title="见习岗位怎么找",
                        desc="看人社入口",
                        sources="人社部门",
                        sort_order=1,
                    ),
                ]
            )
            db.commit()

            articles = content.list_articles(category=None, q="补贴", db=db)
            housing_articles = content.list_articles(category="住房", q=None, db=db)

        self.assertEqual([article.article_id for article in articles], ["housing"])
        self.assertEqual([article.article_id for article in housing_articles], ["housing"])

    def test_article_detail_normalizes_missing_json_lists(self) -> None:
        with self.Session() as db:
            db.add(ContentArticle(article_id="empty-json", title="Empty JSON", summary=None, sections=None, references=None))
            db.commit()

            detail = content.get_article("empty-json", db)

        self.assertEqual(detail.summary, [])
        self.assertEqual(detail.sections, [])
        self.assertEqual(detail.references, [])

    def test_search_treats_sql_wildcards_as_literal_characters(self) -> None:
        with self.Session() as db:
            db.add_all([
                ContentArticle(article_id="percent", title="增长 5%"),
                ContentArticle(article_id="underscore", title="a_b"),
                ContentArticle(article_id="plain", title="普通文章"),
            ])
            db.commit()
            self.assertEqual([item.id for item in content.list_articles(category=None, q="%", db=db)], ["percent"])
            self.assertEqual([item.id for item in content.list_articles(category=None, q="_", db=db)], ["underscore"])

    def test_related_articles_rank_topic_first_and_exclude_current_and_unrelated(self) -> None:
        with self.Session() as db:
            db.add_all([
                ContentArticle(article_id="current", title="Current", topic="租房", category="住房"),
                ContentArticle(article_id="category", title="Category", topic="购房", category="住房", sort_order=0),
                ContentArticle(article_id="topic", title="Topic", topic="租房", category="民生", sort_order=10),
                ContentArticle(article_id="other", title="Other", topic="就业", category="就业"),
            ])
            db.commit()
            self.assertEqual([item.id for item in content.list_related_articles("current", db=db)], ["topic", "category"])
            self.assertEqual([item.id for item in content.list_related_articles("current", limit=1, db=db)], ["topic"])

    def test_related_articles_without_taxonomy_are_empty_and_missing_is_404(self) -> None:
        with self.Session() as db:
            db.add(ContentArticle(article_id="untagged", title="Untagged"))
            db.commit()
            self.assertEqual(content.list_related_articles("untagged", db=db), [])
            with self.assertRaises(HTTPException) as raised:
                content.list_related_articles("missing", db=db)
            self.assertEqual(raised.exception.status_code, 404)

    def test_get_article_returns_404_for_missing_article(self) -> None:
        with self.Session() as db:
            with self.assertRaises(HTTPException) as raised:
                content.get_article("missing", db)

        self.assertEqual(raised.exception.status_code, 404)

    def test_local_answer_prefers_keyword_rule_then_fallback(self) -> None:
        with self.Session() as db:
            db.add_all(
                [
                    AiAnswerRule(keyword=None, answer="fallback answer", sources="fallback source", sort_order=2),
                    AiAnswerRule(keyword="就业", answer="job answer", sources="job source", sort_order=1),
                ]
            )
            db.commit()

            keyword_answer = content._local_answer(db, "就业政策怎么查")
            fallback_answer = content._local_answer(db, "其他问题")

        self.assertEqual(keyword_answer.answer, "job answer")
        self.assertEqual(keyword_answer.sources, "job source")
        self.assertEqual(fallback_answer.answer, "fallback answer")

    def test_daily_quote_is_deterministic_for_requested_date(self) -> None:
        with self.Session() as db:
            db.add_all(
                [
                    DailyQuote(
                        quote_id="q1",
                        text="A",
                        source_title="Source A",
                        source_type="classical",
                        theme="求真",
                        plain_explanation="A plain",
                        today_connection="A today",
                        sort_order=1,
                    ),
                    DailyQuote(
                        quote_id="q2",
                        text="B",
                        source_title="Source B",
                        source_type="red",
                        theme="奋斗",
                        plain_explanation="B plain",
                        today_connection="B today",
                        sort_order=2,
                    ),
                ]
            )
            db.commit()

            quote = content.get_daily_quote("2026-07-03", db)

        self.assertEqual(quote.quote_id, "q2")

    def test_personalized_today_prioritizes_followed_topics_and_marks_viewed(self) -> None:
        with self.Session() as db:
            user = User(phone="13800000000", nickname="Tester", password_hash="hash")
            db.add(user)
            db.flush()
            articles = [
                ContentArticle(article_id="general", title="General", topic="普通", today_order=1, sort_order=1),
                ContentArticle(article_id="job", title="Job", topic="就业", today_order=2, sort_order=2),
                ContentArticle(article_id="housing", title="Housing", topic="住房", today_order=3, sort_order=3),
            ]
            db.add_all(articles)
            db.flush()
            db.add_all(
                [
                    DailyArticleSet(content_date=date(2026, 7, 3), article_id="general", position=1),
                    DailyArticleSet(content_date=date(2026, 7, 3), article_id="job", position=2),
                    DailyArticleSet(content_date=date(2026, 7, 3), article_id="housing", position=3),
                    UserFollowTopic(user_id=user.id, topic="住房", sort_order=0),
                    UserFollowTopic(user_id=user.id, topic="就业", sort_order=1),
                    UserBrowsingHistory(user_id=user.id, article_id="housing", title="Housing", visited_at=datetime.now()),
                ]
            )
            db.commit()

            original_get_content_date = content.get_content_date
            try:
                content.get_content_date = lambda: date(2026, 7, 3)
                response = content.get_personalized_today(current_user=user, db=db)
            finally:
                content.get_content_date = original_get_content_date

        self.assertEqual([article.article_id for article in response.articles], ["housing", "job", "general"])
        self.assertEqual(response.read_count, 1)
        self.assertFalse(response.is_complete)
        self.assertTrue(response.articles[0].viewed)


if __name__ == "__main__":
    unittest.main()
