import logging
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models import AiAnswerRule, AiPrompt, ClassicBook, ClassicBookChapter, ContentArticle, ContentCategory, ContentFeature, ContentPage, DailyArticleSet, DailyQuote, User  # noqa: F401
from app.models import UserAiDailyUsage, UserAiUsageRecord, UserBrowsingHistory, UserFavoriteArticle, UserFollowTopic  # noqa: F401
from app.services.seed_content import seed_content


logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_database_if_needed() -> None:
    server_engine = create_engine(settings.server_database_url, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    with server_engine.connect() as connection:
        connection.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    server_engine.dispose()


def init_database() -> None:
    create_database_if_needed()
    Base.metadata.create_all(bind=engine)
    ensure_user_profile_columns()
    ensure_user_token_version_column()
    ensure_classic_chapter_columns()
    with SessionLocal() as db:
        seed_content(db)
        ensure_category_image_extensions(db)
        ensure_article_categories_aligned(db)


def table_columns(connection, table_name: str) -> set[str]:
    """Column names of ``table_name`` on either MySQL or SQLite."""
    return {column["name"] for column in inspect(connection).get_columns(table_name)}


def ensure_user_profile_columns() -> None:
    with engine.begin() as connection:
        columns = table_columns(connection, "users")
        if "avatar_path" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN avatar_path VARCHAR(255) NULL"))
        if "bio" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN bio VARCHAR(160) NULL"))


def ensure_user_token_version_column() -> None:
    """Older databases predate the token-version logout mechanism."""
    with engine.begin() as connection:
        columns = table_columns(connection, "users")
        if "token_version" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN token_version INT NOT NULL DEFAULT 0"))


def ensure_classic_chapter_columns() -> None:
    with engine.begin() as connection:
        rows = connection.execute(text("SHOW COLUMNS FROM classic_book_chapters")).mappings().all()
        columns = {row["Field"]: row for row in rows}
        content_column = columns.get("content")
        if content_column and "longtext" not in str(content_column["Type"]).lower():
            connection.execute(text("ALTER TABLE classic_book_chapters MODIFY COLUMN content LONGTEXT NULL"))


# Cover images shipped as PNG were converted to JPEG for weight; stored paths
# in older databases still point at the removed ``.png`` files.
LEGACY_IMAGE_PREFIX = "/static/images/"
STATIC_IMAGES_DIR = Path(__file__).resolve().parents[3] / "frontend" / "static" / "images"
IMAGE_COLUMNS = (
    (ContentArticle, "image"),
    (ContentCategory, "image"),
    (ContentFeature, "image"),
    (ClassicBook, "cover_image"),
)


def converted_image_exists(value: str) -> bool:
    """True when ``value`` is a mapped PNG path whose JPEG twin exists."""
    if not value.startswith(LEGACY_IMAGE_PREFIX) or not value.endswith(".png"):
        return False
    name = value[len(LEGACY_IMAGE_PREFIX):-len(".png")]
    if not name or any(char in name for char in ("/", "\\", "\x00")) or ".." in name:
        return False
    return (STATIC_IMAGES_DIR / f"{name}.jpg").is_file()


def ensure_category_image_extensions(db: Session) -> int:
    """Rewrite stored ``/static/images/*.png`` paths to their ``.jpg`` twins.

    Idempotent: values are only rewritten when the JPEG file really exists, and
    a rewritten value no longer matches the ``.png`` filter.
    """
    updated = 0
    for model, column_name in IMAGE_COLUMNS:
        column = getattr(model, column_name)
        rows = db.query(column).filter(column.like(f"{LEGACY_IMAGE_PREFIX}%.png")).distinct().all()
        for (value,) in rows:
            if not value or not converted_image_exists(value):
                continue
            updated += db.query(model).filter(column == value).update(
                {column_name: f"{value[:-len('.png')]}.jpg"},
                synchronize_session=False,
            )
    if updated:
        db.commit()
        logger.info("Rewrote %s stored image path(s) from .png to .jpg", updated)
    return updated


def ensure_article_categories_aligned(db: Session) -> int:
    """Re-map article categories that no discover channel can match.

    Older daily generation wrote 民生政策 / 青年就业 / 科技产业, which the
    ``/articles?category=频道名`` exact match never finds. The same normalizer
    used for new AI output is applied here, so stored and fresh rows agree.
    ``topic`` is only rewritten when it just repeated the old category name.
    Idempotent: rewritten rows no longer match the filter, and nothing is
    committed when no row changed.
    """
    # Imported here on purpose: daily_articles imports this module at import time.
    from app.services.daily_articles import CHANNEL_CATEGORIES, _normalize_category

    rows = (
        db.query(
            ContentArticle.id,
            ContentArticle.category,
            ContentArticle.topic,
            ContentArticle.title,
            ContentArticle.desc,
        )
        .filter(ContentArticle.category.is_not(None))
        .filter(~ContentArticle.category.in_(CHANNEL_CATEGORIES))
        .all()
    )
    updated = 0
    for row in rows:
        category = _normalize_category(row.category, row.title, row.desc)
        values: dict[str, str] = {"category": category}
        if (row.topic or "").strip() == (row.category or "").strip():
            values["topic"] = category
        updated += db.query(ContentArticle).filter(ContentArticle.id == row.id).update(
            values, synchronize_session=False
        )
    if updated:
        db.commit()
        logger.info("Re-mapped %s article categor(ies) onto discover channels", updated)
    return updated
