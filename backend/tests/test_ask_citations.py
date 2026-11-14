"""问诊回答引用来源（citations）的解析、降级和接口测试。"""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import content
from app.db.base import Base
from app.models.content import ContentArticle
from app.models.user import User
from app.schemas.content import (
    AiAnswerResponse,
    AiCitation,
    AiCitationsRequest,
    AiAnswerRequest,
    AjinChatRequest,
)
from services.ai import AIResult


class _Article(SimpleNamespace):
    """不落库的轻量文章对象，只覆盖引用解析用到的字段。"""


def _article(article_id: str, title: str, summary: list[str] | None = None, desc: str | None = None) -> _Article:
    return _Article(article_id=article_id, title=title, summary=summary, desc=desc)


class AiCitationSchemaTests(unittest.TestCase):
    def test_answer_response_citations_default_to_empty(self) -> None:
        response = AiAnswerResponse(answer="回答")
        self.assertEqual(response.citations, [])
        self.assertIn("citations", response.model_dump())
        self.assertEqual(response.model_dump()["citations"], [])

    def test_citation_quote_is_optional(self) -> None:
        citation = AiCitation(article_id="a-1", title="标题")
        self.assertIsNone(citation.quote)
        self.assertEqual(
            AiCitation(article_id="a-1", title="标题", quote="原文一句").model_dump(),
            {"article_id": "a-1", "title": "标题", "quote": "原文一句"},
        )


class CitationParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.articles = [
            _article("housing", "租房补贴怎么申请", summary=["补贴按月发放。", "需连续缴纳社保。"]),
            _article("jobs", "就业政策观察", summary=[], desc="就业市场的最新变化。"),
            _article("edu", "义务教育阶段减负", summary=["作业总量受到限制。"]),
        ]

    def test_markers_map_to_numbered_articles_in_answer_order(self) -> None:
        answer = "先说住房：补贴按月发放[2]；再看就业[1]。"
        citations = content._citations_from_answer(answer, self.articles)
        self.assertEqual([item.article_id for item in citations], ["jobs", "housing"])
        self.assertEqual(citations[0].title, "就业政策观察")
        self.assertEqual(citations[0].quote, "就业市场的最新变化。")
        self.assertEqual(citations[1].quote, "补贴按月发放。")

    def test_duplicate_and_out_of_range_markers_are_ignored(self) -> None:
        answer = "[1] 第一处 [1] 重复 [9] 越界 [0] 也不是编号"
        citations = content._citations_from_answer(answer, self.articles)
        self.assertEqual([item.article_id for item in citations], ["housing"])

    def test_falls_back_to_conservative_title_match_without_markers(self) -> None:
        answer = "这篇《租房补贴怎么申请》讲清了条件，但没写编号。"
        citations = content._citations_from_answer(answer, self.articles)
        self.assertEqual([item.article_id for item in citations], ["housing"])
        self.assertEqual(citations[0].quote, "补贴按月发放。")

    def test_fallback_accepts_a_long_enough_partial_title(self) -> None:
        # 复述标题关键词（不是完整标题）也能命中，但只命中两字以内不算。
        citations = content._citations_from_answer("租房补贴可以按月申请。", self.articles)
        self.assertEqual([item.article_id for item in citations], ["housing"])
        self.assertEqual(content._citations_from_answer("补贴会发放。", self.articles), [])

    def test_short_or_unrelated_text_returns_empty_list(self) -> None:
        self.assertEqual(content._citations_from_answer("好的，收到。", self.articles), [])
        self.assertEqual(content._citations_from_answer("", self.articles), [])
        self.assertEqual(content._citations_from_answer("有[1]", []), [])

    def test_partial_article_objects_do_not_raise(self) -> None:
        # 只有 id/title 的轻量对象也要能解析，quote 为空即可。
        partial = SimpleNamespace(article_id="partial", title="只有标题的文章")
        citations = content._citations_from_answer("依据[1]", [partial])
        self.assertEqual([item.article_id for item in citations], ["partial"])
        self.assertIsNone(citations[0].quote)
        # 完全不可用的对象直接跳过，不抛异常。
        self.assertEqual(content._citations_from_answer("依据[1]", [object()]), [])

    def test_citation_count_is_capped(self) -> None:
        articles = [_article(f"a-{index}", f"文章编号{index}") for index in range(1, 9)]
        answer = "".join(f"[{index}]" for index in range(1, 9))
        citations = content._citations_from_answer(answer, articles)
        self.assertLessEqual(len(citations), content._AI_CITATION_LIMIT)


class AskContextNumberingTests(unittest.TestCase):
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

    def test_context_articles_are_numbered_from_one(self) -> None:
        with self.Session() as db:
            db.add(ContentArticle(article_id="linked-1", title="租房补贴怎么申请", topic="住房", summary=["补贴按月发放。"]))
            db.add(ContentArticle(article_id="recent-2", title="无关的最近文章", topic="其他"))
            db.commit()

            selected, linked = content._select_ask_articles(db, "linked-1", "租房补贴怎么申请")
            context = content._ask_context_from_articles(selected, linked)

        self.assertEqual(selected[0].article_id, "linked-1")
        self.assertEqual(linked.article_id, "linked-1")
        entries = context["相关文章资料库"]
        self.assertTrue(entries[0].startswith("[1] 文章ID：linked-1"))
        self.assertTrue(any(entry.startswith("[2] ") for entry in entries))
        self.assertIn("引用标注要求", context)
        self.assertTrue(str(context["当前关联文章"]).startswith("[1] "))


class AskEndpointCitationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add(ContentArticle(article_id="housing", title="租房补贴怎么申请", topic="住房", summary=["补贴按月发放。"]))
            db.add(ContentArticle(article_id="jobs", title="就业政策观察", topic="就业", desc="就业市场的最新变化。"))
            user = User(phone="13900009999", nickname="Citations", password_hash="hash")
            db.add(user)
            db.commit()
            self.user_id = user.id

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_answer_returns_citations_for_markers(self) -> None:
        result = AIResult(text="住房补贴按月发放[1]，就业市场在变化[2]。", raw={})
        with self.Session() as db:
            user = db.get(User, self.user_id)
            with patch.object(content, "_ensure_ai_quota", lambda *args, **kwargs: None), \
                 patch.object(content, "ask_ai", return_value=result):
                response = content.answer_question(
                    AiAnswerRequest(question="住房和就业", article_id="housing"), db=db, current_user=user
                )
        self.assertEqual([item.article_id for item in response.citations], ["housing", "jobs"])
        self.assertEqual(response.citations[0].title, "租房补贴怎么申请")
        self.assertEqual(response.citations[1].quote, "就业市场的最新变化。")

    def test_answer_fallback_still_returns_empty_citations(self) -> None:
        with self.Session() as db:
            user = db.get(User, self.user_id)
            with patch.object(content, "_ensure_ai_quota", lambda *args, **kwargs: None), \
                 patch.object(content, "ask_ai", side_effect=content.AIClientError("boom")):
                response = content.answer_question(
                    AiAnswerRequest(question="住房政策怎么查"), db=db, current_user=user
                )
        self.assertIsInstance(response, AiAnswerResponse)
        self.assertEqual(response.citations, [])

    def test_ajin_chat_returns_empty_citations(self) -> None:
        result = AIResult(text="阿烬的回答", raw={})
        with self.Session() as db:
            user = db.get(User, self.user_id)
            with patch.object(content, "_ensure_ai_quota", lambda *args, **kwargs: None), \
                 patch.object(content, "ask_ajin", return_value=result):
                response = content.chat_with_ajin(
                    AjinChatRequest(question="你好"), db=db, current_user=user
                )
        self.assertEqual(response.answer, "阿烬的回答")
        self.assertEqual(response.citations, [])

    def test_citations_endpoint_resolves_and_degrades_safely(self) -> None:
        with self.Session() as db:
            response = content.resolve_ask_citations(
                AiCitationsRequest(question="住房补贴", answer="按月发放[1]。", article_id="housing"),
                db=db,
            )
            self.assertEqual([item.article_id for item in response.citations], ["housing"])

            with patch.object(content, "_select_ask_articles", side_effect=RuntimeError("db down")):
                failed = content.resolve_ask_citations(
                    AiCitationsRequest(question="住房补贴", answer="按月发放[1]。", article_id="housing"),
                    db=db,
                )
        self.assertEqual(failed.citations, [])


if __name__ == "__main__":
    unittest.main()
