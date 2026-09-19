from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserFavoriteArticle(Base):
    __tablename__ = "user_favorite_articles"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_user_favorite_article"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    article_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    topic: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[str | None] = mapped_column(String(255), nullable=True)
    read_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class UserBrowsingHistory(Base):
    __tablename__ = "user_browsing_history"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_user_history_article"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    article_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    topic: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[str | None] = mapped_column(String(255), nullable=True)
    read_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    visited_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class UserAiUsageRecord(Base):
    __tablename__ = "user_ai_usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class UserFollowTopic(Base):
    __tablename__ = "user_follow_topics"
    __table_args__ = (UniqueConstraint("user_id", "topic", name="uq_user_follow_topic"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class UserReadingPosition(Base):
    __tablename__ = "user_reading_positions"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_reading_book"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    book_id: Mapped[str] = mapped_column(ForeignKey("classic_books.book_id"), nullable=False)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("classic_book_chapters.id"), nullable=False)
    scroll_progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
