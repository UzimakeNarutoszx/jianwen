"""Daily article categories must land in discover-page channels (W7)."""

import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import session as db_session
from app.db.base import Base
from app.models.content import ContentArticle
from app.services import daily_articles, seed_content


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_IMAGES = REPO_ROOT / "frontend" / "static" / "images"


class ChannelCategoryTests(unittest.TestCase):
    def test_channel_list_comes_from_seeded_categories(self) -> None:
        expected = [name for name, _image, _priority in seed_content.CATEGORIES]

        self.assertEqual(daily_articles.CHANNEL_CATEGORIES, expected)
        self.assertEqual(sorted(daily_articles.DEFAULT_IMAGE_BY_CATEGORY), sorted(expected))

    def test_default_images_exist_on_disk(self) -> None:
        for category, image in daily_articles.DEFAULT_IMAGE_BY_CATEGORY.items():
            with self.subTest(category=category):
                self.assertEqual(daily_articles.CHANNEL_CATEGORIES.count(category), 1)
                self.assertTrue(image.startswith("/static/images/"))
                self.assertTrue((STATIC_IMAGES / image.rsplit("/", 1)[-1]).is_file())

    def test_prompt_lists_all_channels_and_demands_verbatim_category(self) -> None:
        prompt = daily_articles._daily_article_prompt(date(2026, 9, 19))

        for category in daily_articles.CHANNEL_CATEGORIES:
            with self.subTest(category=category):
                self.assertIn(category, prompt)
        self.assertIn("原样选一个", prompt)
        for retired in ("民生政策", "青年就业", "科技产业"):
            self.assertNotIn(retired, prompt)


class NormalizeCategoryTests(unittest.TestCase):
    def test_channel_names_pass_through(self) -> None:
        for category in daily_articles.CHANNEL_CATEGORIES:
            with self.subTest(category=category):
                self.assertEqual(daily_articles._normalize_category(category), category)

    def test_retired_alias_names_map_to_channels(self) -> None:
        cases = {
            "青年就业": "就业",
            "科技产业": "科技",
            "AI技术": "科技",
        }
        for alias, expected in cases.items():
            with self.subTest(alias=alias):
                self.assertEqual(daily_articles._normalize_category(alias), expected)

    def test_keywords_pick_the_channel(self) -> None:
        cases = (
            ("民生政策", "住房公积金新政落地", "房贷与租房提取更便利", "住房"),
            ("民生政策", "异地就医直接结算扩围", "医保报销范围调整", "医保"),
            ("民生政策", "以旧换新补贴加力", "家电消费价格变化", "消费"),
            ("民生政策", "高校毕业生招聘会", "新增岗位与见习机会", "就业"),
            ("民生政策", "基层党建工作会议", "党员发展与党章学习", "共产党"),
        )
        for value, title, desc, expected in cases:
            with self.subTest(title=title):
                self.assertEqual(daily_articles._normalize_category(value, title, desc), expected)

    def test_keyword_rules_also_apply_to_unknown_values(self) -> None:
        self.assertEqual(daily_articles._normalize_category("不明分类", "社保缴费年限", "养老待遇"), "医保")

    def test_fallback_without_keywords(self) -> None:
        self.assertEqual(daily_articles._normalize_category("民生政策", "普通标题", "普通摘要"), "城市生活")
        self.assertEqual(daily_articles._normalize_category("其他分类", "普通标题", "普通摘要"), "时政大事")
        self.assertEqual(daily_articles._normalize_category(None), "时政大事")

    def test_alias_wins_over_keywords(self) -> None:
        # A stale alias must not be re-routed by stray keywords in the text.
        self.assertEqual(daily_articles._normalize_category("青年就业", "房贷利率", "公积金"), "就业")


class ArticleCategoryMigrationTests(unittest.TestCase):
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

    def _seed(self) -> None:
        with self.Session() as db:
            db.add_all(
                [
                    ContentArticle(
                        article_id="ai-daily-1",
                        category="民生政策",
                        topic="民生政策",
                        title="住房公积金政策调整",
                        desc="租房提取和房贷办理有新变化",
                    ),
                    ContentArticle(
                        article_id="ai-daily-2",
                        category="科技产业",
                        topic="科技产业",
                        title="国产芯片产线投产",
                        desc="产业链配套仍在补齐",
                    ),
                    ContentArticle(
                        article_id="ai-daily-3",
                        category="青年就业",
                        topic="青年就业",
                        title="高校毕业生就业服务启动",
                        desc="招聘岗位集中发布",
                    ),
                    ContentArticle(
                        article_id="ai-daily-4",
                        category="就业",
                        topic="就业观察",
                        title="already aligned",
                        desc="频道内文章不应被改动",
                    ),
                    ContentArticle(
                        article_id="ai-daily-5",
                        category="民生政策",
                        topic="社区服务",
                        title="社区食堂运营",
                        desc="没有命中任何关键词",
                    ),
                ]
            )
            db.commit()

    def _rows(self) -> dict[str, tuple[str | None, str | None]]:
        with self.Session() as db:
            return {
                row.article_id: (row.category, row.topic)
                for row in db.query(ContentArticle).all()
            }

    def test_retired_categories_are_remapped(self) -> None:
        self._seed()
        with self.Session() as db:
            changed = db_session.ensure_article_categories_aligned(db)

        self.assertEqual(changed, 4)
        rows = self._rows()
        self.assertEqual(rows["ai-daily-1"], ("住房", "住房"))
        self.assertEqual(rows["ai-daily-2"], ("科技", "科技"))
        self.assertEqual(rows["ai-daily-3"], ("就业", "就业"))
        # An aligned row keeps its more specific topic.
        self.assertEqual(rows["ai-daily-4"], ("就业", "就业观察"))
        # Unknown text without keywords falls back to 城市生活 for 民生政策.
        self.assertEqual(rows["ai-daily-5"], ("城市生活", "社区服务"))

        for category, _topic in rows.values():
            self.assertIn(category, daily_articles.CHANNEL_CATEGORIES)

    def test_second_run_changes_nothing(self) -> None:
        self._seed()
        with self.Session() as db:
            self.assertEqual(db_session.ensure_article_categories_aligned(db), 4)
            self.assertEqual(db_session.ensure_article_categories_aligned(db), 0)
            self.assertEqual(db_session.ensure_article_categories_aligned(db), 0)

        self.assertEqual(self._rows()["ai-daily-1"], ("住房", "住房"))

    def test_init_database_runs_the_migration_after_seeding_and_images(self) -> None:
        calls: list[str] = []

        with patch.object(db_session, "create_database_if_needed"), \
             patch.object(db_session.Base.metadata, "create_all"), \
             patch.object(db_session, "ensure_user_profile_columns"), \
             patch.object(db_session, "ensure_user_token_version_column"), \
             patch.object(db_session, "ensure_classic_chapter_columns"), \
             patch.object(db_session, "SessionLocal", self.Session), \
             patch.object(db_session, "seed_content", side_effect=lambda db: calls.append("seed")), \
             patch.object(db_session, "ensure_category_image_extensions", side_effect=lambda db: calls.append("images")), \
             patch.object(db_session, "ensure_article_categories_aligned", side_effect=lambda db: calls.append("categories")):
            db_session.init_database()

        self.assertEqual(calls, ["seed", "images", "categories"])


if __name__ == "__main__":
    unittest.main()
