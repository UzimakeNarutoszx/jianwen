from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models import AiAnswerRule, AiPrompt, ClassicBook, ClassicBookChapter, ContentArticle, ContentCategory, ContentFeature, ContentPage, DailyArticleSet, DailyQuote, User  # noqa: F401
from app.models import UserAiUsageRecord, UserBrowsingHistory, UserFavoriteArticle, UserFollowTopic  # noqa: F401
from app.models.issue import ContentIssue, ContentIssueEvent, IssueCandidate, IssueCandidateJob, IssueRevision, UserIssueFollow  # noqa: F401
from app.models.breaking_news import BreakingNews  # noqa: F401
from app.services.seed_content import seed_content


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
    ensure_classic_chapter_columns()
    with SessionLocal() as db:
        seed_content(db)


def ensure_user_profile_columns() -> None:
    with engine.begin() as connection:
        rows = connection.execute(text("SHOW COLUMNS FROM users")).mappings().all()
        columns = {row["Field"] for row in rows}
        if "avatar_path" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN avatar_path VARCHAR(255) NULL"))
        if "bio" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN bio VARCHAR(160) NULL"))


def ensure_classic_chapter_columns() -> None:
    with engine.begin() as connection:
        rows = connection.execute(text("SHOW COLUMNS FROM classic_book_chapters")).mappings().all()
        columns = {row["Field"]: row for row in rows}
        content_column = columns.get("content")
        if content_column and "longtext" not in str(content_column["Type"]).lower():
            connection.execute(text("ALTER TABLE classic_book_chapters MODIFY COLUMN content LONGTEXT NULL"))
