"""今日朗读接口：GET /content/today/audio 的 ready / 未就绪两条路径。

manifest 一律写到临时目录，并把 settings.UPLOAD_DIR 指过去，不碰真实 uploads。
"""

from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.api.v1 import content
from app.db.base import Base
from app.models.content import ContentArticle, DailyArticleSet


CONTENT_DATE = date(2026, 11, 8)
VOICES = [
    {"id": "jianwen", "label": "见闻"},
    {"id": "dylan", "label": "男声·京味"},
]


def _manifest(article_ids: list[str]) -> dict:
    return {
        "date": CONTENT_DATE.isoformat(),
        "generated_at": "2026-11-08T06:31:02+08:00",
        "voices": VOICES,
        "articles": [
            {
                "article_id": article_id,
                "title": f"标题 {article_id}",
                "position": index,
                "audio": {
                    "jianwen": {
                        "url": f"/uploads/tts/{CONTENT_DATE.isoformat()}/{article_id}/jianwen.mp3",
                        "duration": 182.4,
                    }
                },
            }
            for index, article_id in enumerate(article_ids)
        ],
    }


class TodayAudioRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.addCleanup(Base.metadata.drop_all, self.engine)
        self.addCleanup(self.engine.dispose)

        self.upload_dir = TemporaryDirectory()
        self.addCleanup(self.upload_dir.cleanup)
        settings_patch = patch.object(content, "settings", SimpleNamespace(UPLOAD_DIR=self.upload_dir.name))
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        date_patch = patch.object(content, "get_content_date", return_value=CONTENT_DATE)
        date_patch.start()
        self.addCleanup(date_patch.stop)

        app = FastAPI()
        app.include_router(content.router, prefix="/content")

        def database():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def _seed_today(self, positions: list[tuple[str, int]]) -> None:
        with self.Session() as db:
            for article_id, _position in positions:
                db.add(ContentArticle(article_id=article_id, title=f"文章 {article_id}"))
            db.flush()
            for article_id, position in positions:
                db.add(
                    DailyArticleSet(
                        content_date=CONTENT_DATE, article_id=article_id, position=position
                    )
                )
            db.commit()

    def _write_manifest(self, payload: object) -> None:
        directory = Path(self.upload_dir.name) / "tts" / CONTENT_DATE.isoformat()
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "manifest.json").write_text(
            payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_ready_manifest_filters_foreign_articles_and_sorts_by_today_order(self) -> None:
        # 当日顺序是 b(1) → a(2) → c(3)，manifest 里顺序反了，还多了一篇非当日文章。
        self._seed_today([("b", 1), ("a", 2), ("c", 3)])
        self._write_manifest(_manifest(["c", "yesterday-article", "a", "b"]))

        response = self.client.get("/content/today/audio")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["date"], CONTENT_DATE.isoformat())
        self.assertEqual([item["article_id"] for item in payload["articles"]], ["b", "a", "c"])
        self.assertEqual([item["position"] for item in payload["articles"]], [0, 1, 2])
        self.assertEqual([voice["id"] for voice in payload["voices"]], [voice["id"] for voice in VOICES])
        self.assertEqual(
            payload["articles"][0]["audio"]["jianwen"]["url"],
            f"/uploads/tts/{CONTENT_DATE.isoformat()}/b/jianwen.mp3",
        )
        self.assertEqual(payload["articles"][0]["audio"]["jianwen"]["duration"], 182.4)
        self.assertEqual(payload["generated_at"], "2026-11-08T06:31:02+08:00")

    def test_tracks_outside_uploads_are_dropped(self) -> None:
        self._seed_today([("a", 1)])
        manifest = _manifest(["a"])
        manifest["articles"][0]["audio"]["jianwen"]["url"] = "https://evil.example/a.mp3"
        self._write_manifest(manifest)

        payload = self.client.get("/content/today/audio").json()

        self.assertTrue(payload["ready"])
        self.assertEqual(payload["articles"][0]["audio"], {})

    def test_missing_manifest_is_not_ready(self) -> None:
        self._seed_today([("a", 1)])

        response = self.client.get("/content/today/audio")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["ready"])
        self.assertEqual(payload["date"], CONTENT_DATE.isoformat())
        self.assertEqual(payload["articles"], [])
        self.assertEqual([voice["id"] for voice in payload["voices"]], [voice["id"] for voice in VOICES])

    def test_broken_json_is_not_ready(self) -> None:
        self._seed_today([("a", 1)])
        self._write_manifest('{"date": "2026-11-08", "articles": [')

        response = self.client.get("/content/today/audio")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["ready"])
        self.assertEqual(payload["articles"], [])

    def test_manifest_without_articles_list_is_not_ready(self) -> None:
        self._write_manifest({"date": CONTENT_DATE.isoformat(), "voices": VOICES})

        payload = self.client.get("/content/today/audio").json()

        self.assertFalse(payload["ready"])
        self.assertEqual(payload["articles"], [])

    def test_route_needs_no_login(self) -> None:
        response = self.client.get("/content/today/audio")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
