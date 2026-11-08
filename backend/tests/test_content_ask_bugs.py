"""Regression tests for the discover/ask bugs fixed in the content API."""
import asyncio
from datetime import date, datetime, timedelta
import http.client
from types import SimpleNamespace
import unittest
import urllib.error
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import content
from app.core.timeutil import day_window_cn, now_cn, today_cn
from app.db.base import Base
from app.models.content import ContentArticle
from app.models.profile import UserAiDailyUsage, UserAiUsageRecord
from app.models.user import User
from app.schemas.content import AiAnswerRequest, AjinChatRequest
from app.schemas.profile import AiUsageRecordRequest
from services import ai as ai_service


def _consume_body(response, chunk_limit: int | None = None) -> list[str]:
    """Drain the (async) body iterator the way Starlette does in ASGI."""

    async def run() -> list[str]:
        collected: list[str] = []
        iterator = response.body_iterator
        try:
            async for chunk in iterator:
                collected.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8"))
                if chunk_limit is not None and len(collected) >= chunk_limit:
                    break
        finally:
            await iterator.aclose()
        return collected

    return asyncio.run(run())


class ChinaTimezoneTests(unittest.TestCase):
    def test_time_helpers_use_shanghai(self) -> None:
        self.assertEqual(now_cn().utcoffset(), timedelta(hours=8))
        self.assertEqual(today_cn(), now_cn().date())

    def test_day_window_is_half_open_midnight_to_midnight(self) -> None:
        start, end = day_window_cn(date(2026, 7, 3))
        self.assertEqual(start, datetime(2026, 7, 3, 0, 0))
        self.assertEqual(end - start, timedelta(days=1))


class StreamUsageTests(unittest.TestCase):
    """Streaming answers must record usage on their own session."""

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            user = User(phone="19900000013", nickname="Stream", password_hash="hash")
            db.add(user)
            db.commit()
            self.user_id = user.id

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _response(self):
        with self.Session() as db:
            user = db.get(User, self.user_id)
            with patch.object(content, "stream_ask", return_value=iter(["第一段", "第二段"])), \
                 patch.object(content, "_ensure_ai_quota", lambda *args, **kwargs: None), \
                 patch.object(content, "_build_ask_context", lambda *args, **kwargs: {}):
                return content.stream_answer_question(
                    AiAnswerRequest(question="政策怎么查"), db=db, current_user=user
                )

    @staticmethod
    def _consume(response, chunk_limit: int | None = None) -> list[str]:
        """Drain the (async) body iterator the way Starlette does in ASGI."""
        return _consume_body(response, chunk_limit)

    def test_streamed_answer_records_usage_after_session_closed(self) -> None:
        response = self._response()
        with patch.object(content, "SessionLocal", self.Session):
            chunks = self._consume(response)
        self.assertEqual("".join(chunks), "第一段第二段")

        with self.Session() as db:
            records = db.query(UserAiUsageRecord).all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].answer, "第一段第二段")
        self.assertEqual(records[0].question, "政策怎么查")

    def test_client_disconnect_still_records_partial_usage(self) -> None:
        response = self._response()
        with patch.object(content, "SessionLocal", self.Session):
            chunks = self._consume(response, chunk_limit=1)
        self.assertEqual("".join(chunks), "第一段")

        with self.Session() as db:
            records = db.query(UserAiUsageRecord).all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].answer, "第一段")

    def test_fallback_stream_records_rule_based_sources(self) -> None:
        with self.Session() as db:
            user = db.get(User, self.user_id)
            with patch.object(content, "stream_ask", side_effect=ai_service.AIClientError("boom")), \
                 patch.object(content, "_ensure_ai_quota", lambda *args, **kwargs: None), \
                 patch.object(content, "_build_ask_context", lambda *args, **kwargs: {}):
                response = content.stream_answer_question(
                    AiAnswerRequest(question="住房政策怎么查"), db=db, current_user=user
                )
            with patch.object(content, "SessionLocal", self.Session):
                self._consume(response)

        with self.Session() as db:
            records = db.query(UserAiUsageRecord).all()
        self.assertEqual(len(records), 1)
        self.assertNotIn("AI 回答基于", records[0].sources or "")


class StreamAnswerDetachedSessionTests(unittest.TestCase):
    """The stream generator must not touch the request-scoped ORM state.

    ``_ensure_ai_quota`` commits, which expires ``current_user``; the session
    from ``Depends(get_db)`` is closed before Starlette streams the body. Any
    attribute read on the user (or use of ``db``) inside the generator then
    raises ``DetachedInstanceError`` and the client receives an empty body.
    """

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            user = User(phone="19900000014", nickname="Stream", password_hash="hash")
            db.add(user)
            db.commit()
            self.user_id = user.id

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_stream_survives_quota_commit_and_closed_request_session(self) -> None:
        request_db = self.Session()
        try:
            user = request_db.get(User, self.user_id)
            with patch.object(content, "stream_ask", return_value=iter(["第一段", "第二段"])), \
                 patch.object(content, "_build_ask_context", lambda *args, **kwargs: {}), \
                 patch.object(content, "settings", SimpleNamespace(AI_DAILY_QUESTION_LIMIT=5)):
                # The real _ensure_ai_quota commits, expiring ``user``.
                response = content.stream_answer_question(
                    AiAnswerRequest(question="政策怎么查"), db=request_db, current_user=user
                )
        finally:
            # Depends(get_db) closes the request session before the body is sent.
            request_db.close()

        with patch.object(content, "SessionLocal", self.Session):
            chunks = _consume_body(response)

        self.assertEqual("".join(chunks), "第一段第二段")

        with self.Session() as db:
            records = db.query(UserAiUsageRecord).all()
            used = db.query(UserAiDailyUsage).one()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].answer, "第一段第二段")
        self.assertEqual(records[0].question, "政策怎么查")
        self.assertEqual(records[0].user_id, self.user_id)
        # The question was charged exactly once.
        self.assertEqual(used.count, 1)

    def test_empty_stream_refunds_quota_after_the_commit(self) -> None:
        """An empty stream must be a 502 with the question refunded.

        The refund runs after ``_ensure_ai_quota`` committed, so it uses the id
        captured up front. (The session is still open on this path, so this is
        coverage of the refund, not a detachment repro.)
        """
        request_db = self.Session()
        try:
            user = request_db.get(User, self.user_id)
            with patch.object(content, "stream_ask", return_value=iter([])), \
                 patch.object(content, "_build_ask_context", lambda *args, **kwargs: {}), \
                 patch.object(content, "settings", SimpleNamespace(AI_DAILY_QUESTION_LIMIT=5)), \
                 patch.object(content, "SessionLocal", self.Session):
                with self.assertRaises(HTTPException) as raised:
                    content.stream_answer_question(
                        AiAnswerRequest(question="政策怎么查"), db=request_db, current_user=user
                    )
        finally:
            request_db.close()

        self.assertEqual(raised.exception.status_code, 502)
        with self.Session() as db:
            used = db.query(UserAiDailyUsage).one()
        self.assertEqual(used.count, 0)


class StreamRefundTests(unittest.TestCase):
    """扣费后建上下文失败要退款，且退回到扣费当天的那一行。"""

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            user = User(phone="13900002222", nickname="Stream", password_hash="hash")
            db.add(user)
            db.commit()
            self.user_id = user.id

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_context_failure_refunds_the_question(self) -> None:
        request_db = self.Session()
        try:
            user = request_db.get(User, self.user_id)
            with patch.object(content, "stream_ask", return_value=iter(["第一段"])), \
                 patch.object(content, "settings", SimpleNamespace(AI_DAILY_QUESTION_LIMIT=5)), \
                 patch.object(content, "SessionLocal", self.Session), \
                 patch.object(content, "_build_ask_context", side_effect=RuntimeError("context exploded")):
                with self.assertRaises(RuntimeError):
                    content.stream_answer_question(
                        AiAnswerRequest(question="政策怎么查"), db=request_db, current_user=user
                    )
        finally:
            request_db.close()

        with self.Session() as db:
            used = db.query(UserAiDailyUsage).one()
        self.assertEqual(used.count, 0)

    def test_refund_targets_the_day_the_question_was_charged(self) -> None:
        charge_day = date(2026, 11, 7)
        with self.Session() as db:
            db.add(UserAiDailyUsage(user_id=self.user_id, usage_date=charge_day, count=1))
            db.commit()

        with patch.object(content, "SessionLocal", self.Session):
            # 退款发生在 06:00 换日之后，仍要退回到扣费当天。
            with patch.object(content, "today_cn", return_value=date(2026, 11, 8)):
                content._refund_ai_quota(self.user_id, charge_day)
            with patch.object(content, "today_cn", return_value=date(2026, 11, 8)):
                content._refund_ai_quota(self.user_id)

        with self.Session() as db:
            rows = {row.usage_date: row.count for row in db.query(UserAiDailyUsage).all()}
        self.assertEqual(rows[charge_day], 0)
        # 不传日期时退回“今天”，扣费那天的行不会被误退。
        self.assertNotIn(date(2026, 11, 8), rows)


class AskContextTests(unittest.TestCase):
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

    def test_context_is_bounded_and_question_relevant(self) -> None:
        with self.Session() as db:
            for index in range(50):
                db.add(
                    ContentArticle(
                        article_id=f"filler-{index}",
                        title=f"无关文章 {index}",
                        topic="其他",
                        category="其他",
                        sort_order=index,
                    )
                )
            db.add(
                ContentArticle(
                    article_id="housing-article",
                    title="租房补贴怎么申请",
                    topic="住房",
                    category="住房",
                )
            )
            db.commit()

            context = content._build_ask_context(db, "housing-article", "租房补贴怎么申请")

        self.assertIn("相关文章资料库", context)
        self.assertNotIn("全站文章资料库", context)
        entries = context["相关文章资料库"]
        self.assertLessEqual(len(entries), 20 + content._ASK_CONTEXT_RELATED_LIMIT + 1)
        self.assertTrue(any("租房补贴" in entry for entry in entries))
        self.assertIn("当前关联文章", context)


class AskPayloadValidationTests(unittest.TestCase):
    def test_question_length_is_capped(self) -> None:
        self.assertEqual(AiAnswerRequest(question="问" * 2000).question, "问" * 2000)
        with self.assertRaises(ValidationError):
            AiAnswerRequest(question="问" * 2001)
        with self.assertRaises(ValidationError):
            AiUsageRecordRequest(question="问" * 2001)

    def test_history_item_length_and_count_are_capped(self) -> None:
        request = AjinChatRequest(
            question="你好",
            history=[{"role": "user", "content": "字" * 5000}],
        )
        self.assertEqual(len(request.history[0]["content"]), 4000)
        with self.assertRaises(ValidationError):
            AjinChatRequest(question="你好", history=[{"role": "user", "content": "a"}] * 21)


class AiClientErrorTests(unittest.TestCase):
    def test_network_errors_become_ai_client_errors(self) -> None:
        for error in (
            OSError("socket reset"),
            http.client.HTTPException("bad status line"),
            http.client.IncompleteRead(b"partial"),
            urllib.error.URLError("dns failure"),
        ):
            with self.subTest(error=type(error).__name__):
                with patch.object(ai_service, "_open_request", side_effect=error):
                    with self.assertRaises(ai_service.AIClientError):
                        ai_service.chat_completions([{"role": "user", "content": "hi"}])

    def test_stream_network_errors_become_ai_client_errors(self) -> None:
        with patch.object(ai_service, "_open_request", side_effect=http.client.IncompleteRead(b"partial")):
            with self.assertRaises(ai_service.AIClientError):
                list(ai_service.stream_chat_completions([{"role": "user", "content": "hi"}]))


if __name__ == "__main__":
    unittest.main()
