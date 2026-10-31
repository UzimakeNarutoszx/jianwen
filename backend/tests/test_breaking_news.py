"""重大会议置顶：识别、白名单、去重、状态与置顶窗口。

全部用固定 HTML/JSON 样例，不联网；抓取函数一律被替换。
"""
from datetime import date, datetime, time, timedelta
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.api.v1 import content
from app.core.config import settings
from app.db.base import Base
from app.models.breaking_news import BreakingNews
from app.services import breaking_news


GOV_INDEX_JSON = """[
  {
    "TITLE": "中国共产党第二十届中央委员会第五次全体会议在京开幕",
    "URL": "https://www.gov.cn/yaowen/2026-10/26/content_9001.htm",
    "DOCRELPUBTIME": "2026-10-26"
  },
  {
    "TITLE": "国务院常务会议研究部署近期经济工作",
    "URL": "https://www.gov.cn/yaowen/2026-10/25/content_9002.htm",
    "DOCRELPUBTIME": "2026-10-25"
  }
]"""

GOV_ARTICLE_HTML = """<html><head>
<meta name="publishdate" content="2026-10-26 09:12" />
</head><body>
<script>var tracker = "中国共产党第二十届中央委员会第五次全体会议";</script>
<p>新华社北京10月26日电</p>
<p>中国共产党第二十届中央委员会第五次全体会议26日上午在北京开幕，会议于10月26日至29日在北京举行。</p>
<p>版权所有，未经许可不得转载。</p>
</body></html>"""

XINHUA_INDEX_HTML = """<html><body>
<a href="https://www.news.cn/politics/20261026/abc/c.html">二十届五中全会在北京开幕</a>
<a href="https://example.com/fake/20261026/fake.html">二十届五中全会在某商业站转载</a>
</body></html>"""

XINHUA_ARTICLE_HTML = """<html><head>
<meta name="publishdate" content="2026-10-26 10:00" />
</head><body>
<p>中国共产党第二十届中央委员会第五次全体会议26日在北京开幕。</p>
</body></html>"""

ANNOUNCE_ONLY_HTML = """<html><head>
<meta name="publishdate" content="2026-09-21 19:00" />
</head><body>
<p>中共中央政治局召开会议，决定今年10月在北京召开中国共产党第二十届中央委员会第五次全体会议。</p>
</body></html>"""


def _fixed_pages() -> dict[str, str]:
    return {
        "https://www.gov.cn/yaowen/liebiao/YAOWENLIEBIAO.json": GOV_INDEX_JSON,
        "https://www.gov.cn/yaowen/2026-10/26/content_9001.htm": GOV_ARTICLE_HTML,
        "https://www.news.cn/politics/": XINHUA_INDEX_HTML,
        "https://www.news.cn/politics/20261026/abc/c.html": XINHUA_ARTICLE_HTML,
    }


class BreakingNewsTestCase(unittest.TestCase):
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


class EventRecognitionTests(BreakingNewsTestCase):
    def test_event_name_and_dates_are_recognised_from_official_text(self) -> None:
        info = breaking_news.confirm_event(
            "中国共产党第二十届中央委员会第五次全体会议26日上午在北京开幕，会议于10月26日至29日在北京举行。",
            date(2026, 10, 26),
        )

        self.assertIsNotNone(info)
        self.assertEqual(info["event_name"], "中国共产党第二十届中央委员会第五次全体会议")
        self.assertEqual(info["event_type"], "中央全会")
        self.assertEqual(info["start_date"], date(2026, 10, 26))
        self.assertEqual(info["end_date"], date(2026, 10, 29))

    def test_shorthand_session_name_is_normalised(self) -> None:
        info = breaking_news.confirm_event(
            "二十届五中全会于2026年10月26日至29日在北京举行。", date(2026, 10, 26)
        )

        self.assertIsNotNone(info)
        self.assertEqual(info["event_name"], "中国共产党第二十届中央委员会第五次全体会议")

    def test_other_conference_types_are_recognised(self) -> None:
        cases = (
            ("第十四届全国人民代表大会第三次会议3月5日在北京开幕。", date(2026, 3, 6), "全国人代会"),
            ("中央经济工作会议12月10日至11日在北京举行。", date(2026, 12, 12), "中央经济工作会议"),
            ("中国共产党第二十次全国代表大会于10月16日开幕。", date(2026, 10, 17), "全国党代会"),
            ("全国政协十四届三次会议3月4日开幕。", date(2026, 3, 5), "全国政协会议"),
        )
        for text, reference, expected_type in cases:
            with self.subTest(text=text):
                info = breaking_news.confirm_event(text, reference)
                self.assertIsNotNone(info)
                self.assertEqual(info["event_type"], expected_type)

    def test_announcement_without_a_date_is_not_confirmed(self) -> None:
        """只有预告、没有召开日期的不算确认。"""
        self.assertIsNone(
            breaking_news.confirm_event(
                "中共中央政治局召开会议，决定今年10月在北京召开中国共产党第二十届中央委员会第五次全体会议。",
                date(2026, 9, 21),
            )
        )
        self.assertIsNone(
            breaking_news.confirm_event(
                "中国共产党第二十届中央委员会第五次全体会议将于近期在北京召开。", date(2026, 9, 21)
            )
        )

    def test_article_page_requires_official_confirmation(self) -> None:
        record = {
            "source_name": "中国政府网",
            "title": "中国共产党第二十届中央委员会第五次全体会议在京开幕",
            "url": "https://www.gov.cn/yaowen/2026-10/26/content_9001.htm",
            "date": "2026-10-26",
        }
        article = breaking_news.parse_article(record, GOV_ARTICLE_HTML)
        self.assertIsNotNone(article)
        self.assertEqual(article["start_date"], date(2026, 10, 26))
        self.assertIn("10月26日至29日", article["summary"])
        # script 里的文字不能被当成正文证据。
        self.assertNotIn("tracker", (article["summary"] or ""))

        announce = breaking_news.parse_article(record, ANNOUNCE_ONLY_HTML)
        self.assertIsNone(announce)


class WhitelistTests(BreakingNewsTestCase):
    def test_non_whitelisted_domain_is_dropped(self) -> None:
        self.assertFalse(breaking_news.allowed_url("https://example.com/a.html", "新华社"))
        self.assertFalse(breaking_news.allowed_url("http://www.gov.cn/a.html"))
        self.assertFalse(breaking_news.allowed_url("https://www.gov.cn.evil.example/a.html"))
        self.assertTrue(breaking_news.allowed_url("https://www.gov.cn/a.html", "中国政府网"))
        self.assertTrue(breaking_news.allowed_url("https://cpc.people.com.cn/n1/2026/1029/x.html", "人民日报"))
        self.assertTrue(breaking_news.allowed_url("https://www.news.cn/politics/a.html", "新华社"))
        self.assertTrue(breaking_news.allowed_url("https://www.xinhuanet.com/politics/a.html", "新华社"))
        # 来源与域名必须匹配，白名单内跨来源也不行。
        self.assertFalse(breaking_news.allowed_url("https://www.news.cn/a.html", "中国政府网"))

    def test_index_entries_outside_the_whitelist_are_dropped(self) -> None:
        entries = breaking_news.parse_index("新华社", "https://www.news.cn/politics/", "html", XINHUA_INDEX_HTML)

        self.assertEqual([entry["url"] for entry in entries], ["https://www.news.cn/politics/20261026/abc/c.html"])

    def test_json_index_drops_foreign_urls(self) -> None:
        payload = """[
          {"TITLE": "标题一", "URL": "https://www.gov.cn/ok.htm", "DOCRELPUBTIME": "2026-10-26"},
          {"TITLE": "标题二", "URL": "https://mirror.example.com/bad.htm", "DOCRELPUBTIME": "2026-10-26"}
        ]"""
        entries = breaking_news.parse_index("中国政府网", "https://www.gov.cn/x.json", "json", payload)

        self.assertEqual([entry["url"] for entry in entries], ["https://www.gov.cn/ok.htm"])

    def test_refresh_rejects_records_with_foreign_source_url(self) -> None:
        with self.Session() as db:
            stored = breaking_news.refresh_breaking_news(
                db,
                now=datetime(2026, 10, 27, 12),
                records=[
                    {
                        "event_name": "中国共产党第二十届中央委员会第五次全体会议",
                        "event_type": "中央全会",
                        "start_date": date(2026, 10, 26),
                        "end_date": date(2026, 10, 29),
                        "title": "外部站点转载",
                        "summary": "摘要",
                        "source_name": "某门户",
                        "source_url": "https://example.com/a.html",
                    }
                ],
            )

            self.assertEqual(stored, 0)
            self.assertEqual(db.query(BreakingNews).count(), 0)


class BehaviourTests(BreakingNewsTestCase):
    def _record(self, **overrides) -> dict:
        record = {
            "event_name": "中国共产党第二十届中央委员会第五次全体会议",
            "event_type": "中央全会",
            "start_date": date(2026, 10, 26),
            "end_date": None,
            "title": "二十届五中全会在北京开幕",
            "summary": "会议于10月26日至29日在北京举行。",
            "source_name": "新华社",
            "source_url": "https://www.news.cn/politics/20261026/abc/c.html",
        }
        record.update(overrides)
        return record

    def test_same_event_is_deduplicated_and_only_status_and_end_date_change(self) -> None:
        with self.Session() as db:
            breaking_news.refresh_breaking_news(db, now=datetime(2026, 10, 26, 12), records=[self._record()])
            breaking_news.refresh_breaking_news(
                db,
                now=datetime(2026, 10, 26, 20),
                records=[
                    self._record(
                        title="五中全会举行第二次全体会议",
                        source_name="人民日报",
                        source_url="https://cpc.people.com.cn/n1/2026/1026/c64387-1.html",
                    )
                ],
            )

            rows = db.query(BreakingNews).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].status, breaking_news.STATUS_ONGOING)
            self.assertEqual(rows[0].title, "二十届五中全会在北京开幕")
            self.assertIsNone(rows[0].end_date)

    def test_ongoing_to_closed_transition_updates_end_date(self) -> None:
        with self.Session() as db:
            breaking_news.refresh_breaking_news(db, now=datetime(2026, 10, 26, 12), records=[self._record()])
            breaking_news.refresh_breaking_news(
                db, now=datetime(2026, 10, 30, 9), records=[self._record(end_date=date(2026, 10, 29))]
            )

            row = db.query(BreakingNews).one()
            self.assertEqual(row.status, breaking_news.STATUS_CLOSED)
            self.assertEqual(row.end_date, date(2026, 10, 29))
            self.assertEqual(db.query(BreakingNews).count(), 1)

    def test_pin_window_keeps_day_seven_and_drops_day_eight(self) -> None:
        # 闭幕当天是第 0 天，之后的第 1…7 天继续置顶，第 8 天不再返回。
        end = date(2026, 10, 29)
        seventh_day = end + timedelta(days=settings.BREAKING_NEWS_PIN_DAYS)
        eighth_day = seventh_day + timedelta(days=1)
        with self.Session() as db:
            db.add(
                BreakingNews(
                    event_key="k",
                    event_name="中国共产党第二十届中央委员会第五次全体会议",
                    event_type="中央全会",
                    start_date=date(2026, 10, 26),
                    end_date=end,
                    status=breaking_news.STATUS_CLOSED,
                    title="公报发布",
                    summary="摘要",
                    source_name="人民日报",
                    source_url=breaking_news.SEED_RECORD["source_url"],
                    image=breaking_news.DEFAULT_IMAGE,
                )
            )
            db.commit()

            seventh = breaking_news.active_breaking_news(
                db, datetime.combine(seventh_day, time(23, 59))
            )
            eighth = breaking_news.active_breaking_news(db, datetime.combine(eighth_day, time(0, 1)))

            self.assertEqual(len(seventh), 1)
            self.assertEqual(
                breaking_news.card_payload(seventh[0], now=datetime.combine(seventh_day, time(23, 59)))["status"],
                breaking_news.STATUS_CLOSED,
            )
            self.assertEqual(eighth, [])

    def test_newest_event_is_listed_first(self) -> None:
        with self.Session() as db:
            db.add_all(
                [
                    BreakingNews(
                        event_key="older",
                        event_name="旧会议",
                        event_type="中央全会",
                        start_date=date(2026, 10, 20),
                        end_date=date(2026, 10, 22),
                        status=breaking_news.STATUS_CLOSED,
                        title="旧",
                        source_name="新华社",
                        source_url="https://www.news.cn/a.html",
                        image=breaking_news.DEFAULT_IMAGE,
                    ),
                    BreakingNews(
                        event_key="newer",
                        event_name="新会议",
                        event_type="中央全会",
                        start_date=date(2026, 10, 27),
                        end_date=date(2026, 10, 29),
                        status=breaking_news.STATUS_ONGOING,
                        title="新",
                        source_name="新华社",
                        source_url="https://www.news.cn/b.html",
                        image=breaking_news.DEFAULT_IMAGE,
                    ),
                ]
            )
            db.commit()

            rows = breaking_news.active_breaking_news(db, datetime(2026, 10, 28, 12))

        self.assertEqual([row.event_name for row in rows], ["新会议", "旧会议"])

    def test_seed_is_written_only_once(self) -> None:
        fixed_now = datetime(2026, 11, 1, 12, tzinfo=breaking_news.CONTENT_TIMEZONE)
        with self.Session() as db, patch.object(
            breaking_news, "local_now", lambda now=None: fixed_now
        ):
            self.assertTrue(breaking_news.seed_breaking_news(db))
            self.assertFalse(breaking_news.seed_breaking_news(db))

            row = db.query(BreakingNews).one()
            self.assertEqual(row.event_name, "中国共产党第二十届中央委员会第五次全体会议")
            self.assertEqual(row.start_date, date(2026, 10, 26))
            self.assertEqual(row.end_date, date(2026, 10, 29))
            self.assertEqual(row.status, breaking_news.STATUS_CLOSED)
            self.assertEqual(row.source_name, "人民日报")
            self.assertEqual(
                row.source_url, "https://cpc.people.com.cn/n1/2026/1029/c64387-40824095.html"
            )
            self.assertEqual(row.image, "/static/images/共产党.jpg")
            self.assertEqual(
                row.summary, "会议于10月26日至29日在北京举行，审议通过关于持之以恒推进全面从严治党的决定。"
            )

    def test_seed_does_not_overwrite_existing_rows(self) -> None:
        with self.Session() as db:
            breaking_news.refresh_breaking_news(db, now=datetime(2026, 10, 26, 12), records=[self._record()])
            self.assertFalse(breaking_news.seed_breaking_news(db))
            self.assertEqual(db.query(BreakingNews).count(), 1)


class FetchTests(BreakingNewsTestCase):
    def test_fetch_confirms_from_official_pages(self) -> None:
        pages = _fixed_pages()
        opened: list[str] = []

        def fake_fetch(source_name: str, url: str) -> str:
            opened.append(url)
            self.assertTrue(breaking_news.allowed_url(url, source_name))
            if url not in pages:
                raise OSError(f"unreachable: {url}")
            return pages[url]

        with patch.object(breaking_news, "_fetch", side_effect=fake_fetch):
            events = breaking_news.fetch_confirmed_events(datetime(2026, 10, 26, 20))

        self.assertTrue(events)
        self.assertTrue(all(event["event_name"].startswith("中国共产党第二十届") for event in events))
        self.assertTrue(all(event["start_date"] == date(2026, 10, 26) for event in events))
        # 非白名单链接根本不会进入抓取队列。
        self.assertFalse(any("example.com" in url for url in opened))

    def test_fetch_refuses_non_whitelisted_url_before_any_request(self) -> None:
        with patch.object(breaking_news.urllib.request, "build_opener") as opener:
            with self.assertRaises(ValueError):
                breaking_news._fetch("新华社", "https://example.com/a.html")
        opener.assert_not_called()

    def test_fetch_failure_only_logs(self) -> None:
        with patch.object(breaking_news, "_fetch", side_effect=OSError("offline")):
            with self.assertLogs("app.services.breaking_news", level="WARNING"):
                self.assertEqual(breaking_news.fetch_confirmed_events(datetime(2026, 10, 26, 20)), [])

    def test_scheduled_refresh_swallows_errors(self) -> None:
        with patch.object(breaking_news, "seed_breaking_news", side_effect=RuntimeError("db down")):
            with self.assertLogs("app.services.breaking_news", level="ERROR"):
                self.assertEqual(breaking_news.scheduled_breaking_news_refresh(datetime(2026, 10, 26, 20)), 0)


class RouteTests(BreakingNewsTestCase):
    def setUp(self) -> None:
        super().setUp()
        # 固定“现在”，避免测试随真实日期漂移出置顶窗口。
        self.fixed_now = datetime(2026, 11, 1, 12, tzinfo=breaking_news.CONTENT_TIMEZONE)
        self.now_patcher = patch.object(breaking_news, "local_now", lambda now=None: self.fixed_now)
        self.now_patcher.start()
        self.addCleanup(self.now_patcher.stop)
        self.db = self.Session()
        app = FastAPI()
        app.include_router(content.router, prefix="/content")

        def database():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.db.close()
        super().tearDown()

    def test_route_needs_no_login_and_returns_active_cards(self) -> None:
        breaking_news.seed_breaking_news(self.db)

        response = self.client.get("/content/breaking-news")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["event_name"], "中国共产党第二十届中央委员会第五次全体会议")
        self.assertEqual(payload[0]["status"], "已闭幕")
        self.assertEqual(payload[0]["image"], "/static/images/共产党.jpg")

    def test_route_returns_empty_list_when_nothing_is_pinned(self) -> None:
        response = self.client.get("/content/breaking-news")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_route_does_not_touch_the_network(self) -> None:
        breaking_news.seed_breaking_news(self.db)
        with patch.object(breaking_news, "_fetch", side_effect=AssertionError("request must not fetch")), \
             patch.object(breaking_news, "fetch_confirmed_events", side_effect=AssertionError("request must not fetch")):
            response = self.client.get("/content/breaking-news")

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
