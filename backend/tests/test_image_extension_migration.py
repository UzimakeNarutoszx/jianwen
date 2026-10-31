"""Category covers moved from .png to .jpg (W6): stored paths and cached URLs."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import session as db_session
from app.main import app
from app.models.content import ClassicBook, ContentArticle, ContentCategory, ContentFeature
from app.services import classic_fulltext, daily_articles, seed_content


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_IMAGES = REPO_ROOT / "frontend" / "static" / "images"


class ImagePathMigrationTests(unittest.TestCase):
    """Stored ``.png`` cover paths must follow the files that now exist."""

    def setUp(self) -> None:
        from app.db.base import Base

        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self._tmp = tempfile.TemporaryDirectory()
        self.images = Path(self._tmp.name)
        # Only two of the three referenced names were converted.
        for name in ("AI技术", "社会民生"):
            (self.images / f"{name}.jpg").write_bytes(b"jpeg")

    def tearDown(self) -> None:
        self._tmp.cleanup()
        self.engine.dispose()

    def _seed_legacy_rows(self) -> None:
        with self.Session() as db:
            db.add(ContentCategory(name="科技", image="/static/images/AI技术.png"))
            db.add(ContentCategory(name="城市生活", image="/static/images/社会民生.png"))
            db.add(ContentArticle(article_id="a1", title="t", image="/static/images/社会民生.png"))
            db.add(ContentFeature(title="f", image="/static/images/AI技术.png"))
            db.add(ClassicBook(book_id="b1", title="t", cover_image="/static/images/AI技术.png"))
            # Not converted on disk: must be left untouched.
            db.add(ContentCategory(name="住房", image="/static/images/住房.png"))
            # Unrelated paths stay untouched too.
            db.add(ContentArticle(article_id="a2", title="t", image="/uploads/avatars/a.png"))
            db.commit()

    def _values(self, model, column: str) -> list[str]:
        with self.Session() as db:
            return sorted(value for (value,) in db.query(getattr(model, column)).all())

    def test_migration_rewrites_every_image_column(self) -> None:
        self._seed_legacy_rows()
        with patch.object(db_session, "STATIC_IMAGES_DIR", self.images), self.Session() as db:
            updated = db_session.ensure_category_image_extensions(db)

        self.assertEqual(updated, 5)
        self.assertEqual(self._values(ContentCategory, "image"), [
            "/static/images/AI技术.jpg",
            "/static/images/住房.png",
            "/static/images/社会民生.jpg",
        ])
        self.assertEqual(self._values(ContentArticle, "image"), ["/static/images/社会民生.jpg", "/uploads/avatars/a.png"])
        self.assertEqual(self._values(ContentFeature, "image"), ["/static/images/AI技术.jpg"])
        self.assertEqual(self._values(ClassicBook, "cover_image"), ["/static/images/AI技术.jpg"])

    def test_migration_is_idempotent(self) -> None:
        self._seed_legacy_rows()
        with patch.object(db_session, "STATIC_IMAGES_DIR", self.images), self.Session() as db:
            self.assertEqual(db_session.ensure_category_image_extensions(db), 5)
            self.assertEqual(db_session.ensure_category_image_extensions(db), 0)
            self.assertEqual(db_session.ensure_category_image_extensions(db), 0)

        self.assertEqual(self._values(ContentCategory, "image"), [
            "/static/images/AI技术.jpg",
            "/static/images/住房.png",
            "/static/images/社会民生.jpg",
        ])

    def test_migration_skips_paths_escaping_the_images_directory(self) -> None:
        with self.Session() as db:
            db.add(ContentCategory(name="越界", image="/static/images/../secret.png"))
            db.commit()
        with patch.object(db_session, "STATIC_IMAGES_DIR", self.images), self.Session() as db:
            self.assertEqual(db_session.ensure_category_image_extensions(db), 0)

        self.assertEqual(self._values(ContentCategory, "image"), ["/static/images/../secret.png"])

    def test_init_database_runs_the_migration_after_seeding(self) -> None:
        calls: list[str] = []
        with patch.object(db_session, "create_database_if_needed"), \
             patch.object(db_session.Base.metadata, "create_all"), \
             patch.object(db_session, "ensure_user_profile_columns"), \
             patch.object(db_session, "ensure_user_token_version_column"), \
             patch.object(db_session, "ensure_classic_chapter_columns"), \
             patch.object(db_session, "SessionLocal", self.Session), \
             patch.object(db_session, "seed_content", side_effect=lambda db: calls.append("seed")), \
             patch.object(db_session, "ensure_category_image_extensions", side_effect=lambda db: calls.append("migrate")):
            db_session.init_database()

        self.assertEqual(calls, ["seed", "migrate"])


class LegacyPngRouteTests(unittest.TestCase):
    """Cached ``.png`` URLs must keep resolving after the file rename."""

    def _get(self, path: str) -> httpx.Response:
        async def request() -> httpx.Response:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                return await client.get(path)

        return asyncio.run(request())

    def test_existing_png_redirects_to_jpg_with_307(self) -> None:
        response = self._get("/static/images/AI技术.png")

        self.assertEqual(response.status_code, 307)
        self.assertTrue(response.headers["location"].endswith("/static/images/AI%E6%8A%80%E6%9C%AF.jpg"))
        followed = self._get(response.headers["location"])
        self.assertEqual(followed.status_code, 200)
        self.assertEqual(followed.content, (STATIC_IMAGES / "AI技术.jpg").read_bytes())

    def test_png_still_shipped_is_served_without_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            images = Path(tmp) / "images"
            images.mkdir()
            (images / "kept.png").write_bytes(b"png-bytes")
            with patch("app.main.frontend_static", Path(tmp)):
                response = self._get("/static/images/kept.png")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"png-bytes")

    def test_missing_image_returns_404(self) -> None:
        self.assertEqual(self._get("/static/images/不存在.png").status_code, 404)

    def test_traversal_attempts_return_404(self) -> None:
        for path in (
            "/static/images/...png",
            "/static/images/..%2Fconfig.py.png",
            "/static/images/%2e%2e%2f%2e%2e%2fapp%2fmain.py.png",
            "/static/images/%2e%2e%2Fmain.png",
        ):
            with self.subTest(path=path):
                self.assertEqual(self._get(path).status_code, 404)


class ShippedImageReferenceTests(unittest.TestCase):
    """Every image path written by the backend must exist on disk."""

    def test_seeded_image_paths_point_at_shipped_files(self) -> None:
        referenced: set[str] = set()
        referenced.update(image for _name, image, _priority in seed_content.CATEGORIES)
        referenced.update(feature[3] for feature in seed_content.FEATURES)
        referenced.update(article["image"] for article in seed_content.ARTICLES)
        referenced.update(book["cover_image"] for book in seed_content.CLASSIC_BOOKS)
        referenced.update(daily_articles.DEFAULT_IMAGE_BY_CATEGORY.values())
        referenced.update(book.cover_image for book in classic_fulltext.STATIC_BOOKS)

        for value in sorted(referenced):
            with self.subTest(image=value):
                self.assertTrue(value.startswith("/static/images/"))
                self.assertTrue((STATIC_IMAGES / value.rsplit("/", 1)[-1]).is_file())

    def test_no_backend_source_still_points_at_a_converted_png(self) -> None:
        converted = sorted(path.name for path in STATIC_IMAGES.glob("*.jpg"))
        self.assertTrue(converted, "converted JPEG covers are missing")
        for name in converted:
            legacy = f"/static/images/{Path(name).stem}.png"
            for module in (seed_content, daily_articles, classic_fulltext):
                source = Path(module.__file__).read_text(encoding="utf-8")
                with self.subTest(module=module.__name__, image=legacy):
                    self.assertNotIn(legacy, source)


if __name__ == "__main__":
    unittest.main()
