"""UTC interval ledger. Accepted intervals never overlap for the same user."""
from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import DATETIME

TIMESTAMP = DateTime().with_variant(DATETIME(fsp=6), "mysql")
from app.db.base import Base


class ReadingBatch(Base):
    __tablename__ = "user_reading_batches"
    __table_args__ = (UniqueConstraint("user_id", "batch_id", name="uq_reading_batch"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    batch_id: Mapped[str] = mapped_column(String(64))


class ReadingInterval(Base):
    __tablename__ = "user_reading_intervals"
    __table_args__ = (Index("ix_reading_user_time", "user_id", "started_at", "ended_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(16))
    content_id: Mapped[str] = mapped_column(String(64))
    book_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    book_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scroll_progress: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP)
    ended_at: Mapped[datetime] = mapped_column(TIMESTAMP)


class ArticleReadingDay(Base):
    """Keep each day's article read even when the latest-history row moves forward."""
    __tablename__ = "user_article_reading_days"
    __table_args__ = (UniqueConstraint("user_id", "article_id", "content_date", name="uq_article_read_day"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    article_id: Mapped[str] = mapped_column(String(64))
    content_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(255))
    topic: Mapped[str | None] = mapped_column(String(64), nullable=True)
