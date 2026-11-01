"""重大会议置顶卡片：只存官方来源确认过的会议，不存抓取缓存。"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BreakingNews(Base):
    """一场会议一行，``event_key`` 由会议名 + 开始日期派生，用于去重。"""

    # 库里还留着已回退版本的 breaking_news 旧表（字段不同），新功能用独立表名，不碰旧表。
    __tablename__ = "major_events"
    __table_args__ = (UniqueConstraint("event_key", name="uq_major_events_event_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="进行中", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
