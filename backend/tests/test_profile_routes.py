import unittest
from datetime import date, datetime, timedelta
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import profile
from app.db.base import Base
from app.models.content import ClassicBook, ClassicBookChapter, ContentArticle
from app.models.profile import (
    UserAiUsageRecord,
    UserBrowsingHistory,
    UserFavoriteArticle,
    UserFollowTopic,
    UserReadingPosition,
)
from app.models.reading import ArticleReadingDay
from app.models.user import User
from app.schemas.profile import (
    ArticleRecordRequest,
    FollowTopicsRequest,
    ProfileUpdateRequest,
    ReadingPositionRequest,
    ReadingPositionResponse,
)


class _MissFirstQuery:
    """指定模型上的第一次查询故意返回“没有记录”，模拟并发插入窗口。

    只有 upsert 里“先查”的那一次要落空，参数校验和之后的重查都必须看到真实数据。
    """

    def __init__(self, session, model) -> None:
        self.original = session.query
        self.model = model
        self.pending = True

    def __call__(self, *entities, **kwargs):
        query = self.original(*entities, **kwargs)
        if self.pending and entities and entities[0] is self.model:
            self.pending = False
            return _EmptyQuery(query)
        return query


class _EmptyQuery:
    def __init__(self, query) -> None:
        self.query = query

    def filter(self, *args, **kwargs):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return None


class ProfileRouteTests(unittest.TestCase):
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

    def _create_user(self, db):
        user = User(phone="19900000003", nickname="Tester", password_hash="hash")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def test_save_follow_topics_trims_deduplicates_and_preserves_order(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            payload = FollowTopicsRequest(topics=[" 就业 ", "住房", "就业", "", "  科技  "])

            topics = profile.save_follow_topics(payload, current_user=user, db=db)
            stored_topics = [row.topic for row in db.query(UserFollowTopic).order_by(UserFollowTopic.sort_order).all()]

        self.assertEqual(topics, ["就业", "住房", "科技"])
        self.assertEqual(stored_topics, ["就业", "住房", "科技"])

    def test_long_topics_deduplicate_after_truncation(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            prefix = "长" * 64
            topics = profile.save_follow_topics(
                FollowTopicsRequest(topics=[prefix + "甲", prefix + "乙"]), current_user=user, db=db
            )
            self.assertEqual(topics, [prefix])
            self.assertEqual(db.query(UserFollowTopic).count(), 1)

    def test_article_id_only_records_receive_catalog_metadata(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            db.add(ContentArticle(article_id="catalog", title="Readable title", category="就业", desc="Summary"))
            db.commit()
            payload = ArticleRecordRequest(article_id="catalog")
            favorite = profile.save_favorite(payload, current_user=user, db=db)
            history = profile.save_history(payload, current_user=user, db=db)
            self.assertEqual(favorite.title, "Readable title")
            self.assertEqual(history.topic, "就业")
            self.assertEqual(history.desc, "Summary")

    def test_partial_record_does_not_erase_existing_metadata(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            for save in (profile.save_favorite, profile.save_history):
                save(ArticleRecordRequest(article_id="external", title="Saved title"), current_user=user, db=db)
                record = save(ArticleRecordRequest(article_id="external"), current_user=user, db=db)
                self.assertEqual(record.title, "Saved title")

    def test_avatar_rejects_empty_and_oversized_files_with_bounded_read(self) -> None:
        with TemporaryDirectory() as upload_dir, patch.object(profile, "settings", SimpleNamespace(UPLOAD_DIR=upload_dir)):
            for data in (b"", b"x" * (2 * 1024 * 1024 + 1)):
                # The route is a sync def (FastAPI runs it in the thread pool),
                # so the upload file is read synchronously.
                read = Mock(return_value=data)
                upload = SimpleNamespace(filename="avatar.png", content_type="image/png", file=SimpleNamespace(read=read))
                with self.assertRaises(HTTPException) as raised:
                    profile.upload_avatar(upload, current_user=SimpleNamespace(id=1), db=None)
                self.assertEqual(raised.exception.status_code, 400)
                read.assert_called_once_with(2 * 1024 * 1024 + 1)

    def test_profile_response_counts_user_records(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            db.add_all(
                [
                    UserFavoriteArticle(user_id=user.id, article_id="a1"),
                    UserBrowsingHistory(user_id=user.id, article_id="a1"),
                    UserAiUsageRecord(user_id=user.id, question="Q", answer="A"),
                    UserFollowTopic(user_id=user.id, topic="就业", sort_order=0),
                ]
            )
            db.commit()

            response = profile.get_profile(current_user=user, db=db)

        self.assertEqual(response.favorites_count, 1)
        self.assertEqual(response.history_count, 1)
        self.assertEqual(response.ai_records_count, 1)
        self.assertEqual(response.followed_topics, ["就业"])

    def test_update_profile_persists_nickname_and_bio(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            payload = ProfileUpdateRequest(nickname="New Name", bio="Short bio")

            response = profile.update_profile(payload, current_user=user, db=db)

        self.assertEqual(response.nickname, "New Name")
        self.assertEqual(response.bio, "Short bio")

    def test_save_favorite_updates_existing_record(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            first = ArticleRecordRequest(article_id="a1", topic="就业", title="Old")
            second = ArticleRecordRequest(article_id="a1", topic="住房", title="New")

            created = profile.save_favorite(first, current_user=user, db=db)
            updated = profile.save_favorite(second, current_user=user, db=db)
            total = db.query(UserFavoriteArticle).count()

        self.assertEqual(created.id, updated.id)
        self.assertEqual(total, 1)
        self.assertEqual(updated.topic, "住房")
        self.assertEqual(updated.title, "New")

    def test_save_history_updates_existing_record(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            first = ArticleRecordRequest(article_id="a1", topic="就业", title="Old")
            second = ArticleRecordRequest(article_id="a1", topic="就业", title="New")

            created = profile.save_history(first, current_user=user, db=db)
            updated = profile.save_history(second, current_user=user, db=db)
            total = db.query(UserBrowsingHistory).count()

        self.assertEqual(created.id, updated.id)
        self.assertEqual(total, 1)
        self.assertEqual(updated.title, "New")

    def test_history_day_uses_the_content_date_that_rolls_over_at_six(self) -> None:
        # 05:30 仍属于前一天的内容日期，阅读清单不能记到自然日上。
        with self.Session() as db:
            user = self._create_user(db)
            with patch.object(
                profile, "get_content_date", return_value=date(2026, 11, 7)
            ) as content_date:
                profile.save_history(ArticleRecordRequest(article_id="a1"), current_user=user, db=db)
            content_date.assert_called_once_with()
            stored = [row.content_date for row in db.query(ArticleReadingDay).all()]

        self.assertEqual(stored, [date(2026, 11, 7)])

    def test_concurrent_favorite_insert_is_resolved_by_reloading(self) -> None:
        """并发插入撞唯一约束时不能 500，应回滚后更新已有行。"""
        with self.Session() as db:
            user = self._create_user(db)
            # 另一个请求已经插入了同一 (user, article)，但本次请求的第一次查询没看到它。
            db.add(UserFavoriteArticle(user_id=user.id, article_id="a1", title="Other"))
            db.commit()

            with patch.object(db, "query", side_effect=_MissFirstQuery(db, UserFavoriteArticle)):
                record = profile.save_favorite(
                    ArticleRecordRequest(article_id="a1", title="Updated"), current_user=user, db=db
                )

            rows = db.query(UserFavoriteArticle).all()

        self.assertEqual(len(rows), 1)
        self.assertEqual(record.title, "Updated")

    def test_concurrent_reading_position_insert_is_resolved_by_reloading(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            db.add(ClassicBook(book_id="book", title="Book"))
            db.flush()
            chapter = ClassicBookChapter(book_id="book", title="One", chapter_order=1)
            db.add(chapter)
            db.commit()
            # 另一个请求已经写入了同一 (user, book) 的进度。
            db.add(
                UserReadingPosition(
                    user_id=user.id,
                    book_id="book",
                    chapter_id=chapter.id,
                    scroll_progress=10,
                    updated_at=datetime.now(),
                )
            )
            db.commit()

            with patch.object(db, "query", side_effect=_MissFirstQuery(db, UserReadingPosition)):
                record = profile.save_reading_position(
                    "book",
                    ReadingPositionRequest(chapter_id=chapter.id, scroll_progress=77),
                    current_user=user,
                    db=db,
                )

            rows = db.query(UserReadingPosition).all()

        self.assertEqual(len(rows), 1)
        self.assertEqual(record.scroll_progress, 77)

    def test_concurrent_follow_topics_insert_is_retried(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            db.add(UserFollowTopic(user_id=user.id, topic="就业", sort_order=0))
            db.commit()

            original_commit = db.commit
            state = {"failed": False}

            def commit_with_one_conflict():
                # 第一次提交模拟另一个请求抢先写入了同一 (user, topic)。
                if not state["failed"]:
                    state["failed"] = True
                    raise IntegrityError("insert", {}, Exception("duplicate"))
                return original_commit()

            with patch.object(db, "commit", side_effect=commit_with_one_conflict):
                topics = profile.save_follow_topics(
                    FollowTopicsRequest(topics=["就业", "住房"]), current_user=user, db=db
                )

            stored = [
                row.topic
                for row in db.query(UserFollowTopic).order_by(UserFollowTopic.sort_order, UserFollowTopic.id).all()
            ]

        self.assertEqual(topics, ["就业", "住房"])
        self.assertEqual(stored, ["就业", "住房"])

    def test_reading_position_output_is_timezone_aware(self) -> None:
        with self.Session() as db:
            user = self._create_user(db)
            db.add(ClassicBook(book_id="book", title="Book"))
            db.flush()
            chapter = ClassicBookChapter(book_id="book", title="One", chapter_order=1)
            db.add(chapter)
            db.commit()

            record = profile.save_reading_position(
                "book", ReadingPositionRequest(chapter_id=chapter.id, scroll_progress=40), current_user=user, db=db
            )
            response = ReadingPositionResponse.model_validate(record)

        self.assertEqual(response.updated_at.utcoffset(), timedelta(hours=8))


if __name__ == "__main__":
    unittest.main()
