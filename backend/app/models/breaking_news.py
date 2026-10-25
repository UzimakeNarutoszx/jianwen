from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BreakingNews(Base):
    __tablename__ = "breaking_news"
    __table_args__ = (UniqueConstraint("event_key", name="uq_breaking_news_event_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), default="重大会议", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list] = mapped_column(JSON, nullable=False)
    image: Mapped[str] = mapped_column(String(255), default="/static/images/共产党.png", nullable=False)
    first_confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    latest_reported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    is_ongoing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ongoing_until: Mapped[datetime | None] = mapped_column(DateTime)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class BreakingNewsSync(Base):
    __tablename__ = "breaking_news_sync"
    id: Mapped[int] = mapped_column(primary_key=True)
    content_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(Text)
