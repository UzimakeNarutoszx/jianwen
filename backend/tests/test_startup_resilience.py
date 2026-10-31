"""Startup must survive an unreachable scraping target (W5 item 9)."""

import http.client
import unittest
import urllib.error
from unittest.mock import patch

from app.services import classic_fulltext, seed_content


class FetchFailureTests(unittest.TestCase):
    def test_fetch_html_no_longer_disables_tls_verification(self) -> None:
        # The signature lost the verify escape hatch entirely.
        with self.assertRaises(TypeError):
            classic_fulltext.fetch_html("https://example.com", allow_unverified_ssl=True)

    def test_fetch_page_text_propagates_network_errors_to_the_caller(self) -> None:
        with patch.object(classic_fulltext, "urlopen", side_effect=urllib.error.URLError("dns failure")):
            with self.assertRaises(OSError):
                classic_fulltext.fetch_page_text("https://example.com/page.html")

    def test_static_chapter_fetch_failure_keeps_the_chapter_without_text(self) -> None:
        book = classic_fulltext.BookSpec(
            book_id="book",
            title="标题",
            author="作者",
            category="分类",
            description="简介",
            cover_image="/static/images/x.png",
            source_org="来源",
            external_url="https://example.com",
            sort_order=1,
            chapters=(
                classic_fulltext.ChapterSpec("第一章", "摘要", "https://example.com/a.html"),
                classic_fulltext.ChapterSpec("第二章", "摘要", "https://example.com/a.html"),
            ),
        )
        with patch.object(classic_fulltext, "fetch_page_text", side_effect=http.client.HTTPException("bad status line")):
            with self.assertLogs("app.services.classic_fulltext", level="WARNING"):
                chapters = classic_fulltext.resolve_static_chapters(book)

        self.assertEqual([chapter.title for chapter in chapters], ["第一章", "第二章"])
        self.assertTrue(all(chapter.content is None for chapter in chapters))

    def test_qstheory_listing_failure_does_not_raise(self) -> None:
        with patch.object(classic_fulltext, "fetch_html", side_effect=urllib.error.URLError("offline")), \
             patch.object(classic_fulltext, "existing_full_text_count", return_value=0):
            with self.assertLogs("app.services.classic_fulltext", level="WARNING"):
                grouped = classic_fulltext.resolve_qstheory_chapters(db=None)
        self.assertEqual(grouped, {})

    def test_embedded_listing_failure_does_not_raise(self) -> None:
        with patch.object(classic_fulltext, "fetch_html", side_effect=OSError("timeout")):
            with self.assertLogs("app.services.classic_fulltext", level="WARNING"):
                self.assertEqual(classic_fulltext.resolve_embedded_chapters(), {})

    def test_single_chapter_page_failure_returns_none(self) -> None:
        source = classic_fulltext.QstheoryBookSpec(
            book_id="qstheory",
            url="https://example.com/c_1.htm",
            content_id="1",
            expected_pages=1,
            volume_label="第一卷",
        )
        with patch.object(classic_fulltext, "fetch_html", side_effect=OSError("timeout")):
            with self.assertLogs("app.services.classic_fulltext", level="WARNING"):
                self.assertIsNone(classic_fulltext.fetch_qstheory_chapter(source, 2))


class SeedContentToleranceTests(unittest.TestCase):
    def test_full_text_import_failure_is_only_a_warning(self) -> None:
        session = _FailingSession()
        with patch.object(seed_content, "import_classic_full_texts", side_effect=RuntimeError("scrape failed")), \
             patch.object(seed_content, "has_complete_qstheory_full_text", return_value=True):
            with self.assertLogs("app.services.seed_content", level="WARNING"):
                seed_content.seed_content(db=session)

        self.assertTrue(session.rolled_back)
        # The seeded rows were committed before the scraping step.
        self.assertGreaterEqual(session.committed, 1)


class _FailingSession:
    """Stand-in session that records the rollback call."""

    def __init__(self) -> None:
        self.rolled_back = False
        self.committed = 0

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        self.rolled_back = True

    def query(self, *args, **kwargs):
        return _EmptyQuery()

    def execute(self, *args, **kwargs):
        return None

    def flush(self) -> None:
        return None

    def expire_all(self) -> None:
        return None

    def add(self, *args, **kwargs) -> None:
        return None


class _EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def delete(self, *args, **kwargs):
        return 0

    def update(self, *args, **kwargs):
        return 0

    def first(self):
        return None

    def all(self):
        return []

    def count(self):
        return 0


if __name__ == "__main__":
    unittest.main()
