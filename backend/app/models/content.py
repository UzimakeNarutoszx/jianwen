from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContentCategory(Base):
    __tablename__ = "content_categories"
    __table_args__ = (UniqueConstraint("name", name="uq_content_category_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ContentArticle(Base):
    __tablename__ = "content_articles"
    __table_args__ = (UniqueConstraint("article_id", name="uq_content_article_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[str | None] = mapped_column(String(255), nullable=True)
    read_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sections: Mapped[list | None] = mapped_column(JSON, nullable=True)
    references: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_today: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    today_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    daily_article_sets: Mapped[list["DailyArticleSet"]] = relationship(back_populates="article")


class DailyArticleSet(Base):
    __tablename__ = "daily_article_sets"
    __table_args__ = (
        UniqueConstraint("content_date", "position", name="uq_daily_article_set_date_position"),
        UniqueConstraint("content_date", "article_id", name="uq_daily_article_set_date_article"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_date: Mapped[date] = mapped_column(Date, nullable=False)
    article_id: Mapped[str] = mapped_column(ForeignKey("content_articles.article_id"), index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    article: Mapped[ContentArticle] = relationship(back_populates="daily_article_sets")


class ContentFeature(Base):
    __tablename__ = "content_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    category_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ContentPage(Base):
    __tablename__ = "content_pages"
    __table_args__ = (UniqueConstraint("page_key", name="uq_content_page_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sections: Mapped[list | None] = mapped_column(JSON, nullable=True)
    updated_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class DailyQuote(Base):
    __tablename__ = "daily_quotes"
    __table_args__ = (
        UniqueConstraint("quote_id", name="uq_daily_quote_id"),
        CheckConstraint(
            "source_type IN ('classical', 'ancient', 'red', 'manifesto')",
            name="ck_daily_quote_source_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    text: Mapped[str] = mapped_column(String(120), nullable=False)
    source_title: Mapped[str] = mapped_column(String(128), nullable=False)
    source_author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    theme: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    plain_explanation: Mapped[str] = mapped_column(String(160), nullable=False)
    today_connection: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ClassicBook(Base):
    __tablename__ = "classic_books"
    __table_args__ = (UniqueConstraint("book_id", name="uq_classic_book_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_org: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ClassicBookChapter(Base):
    __tablename__ = "classic_book_chapters"
    __table_args__ = (UniqueConstraint("book_id", "chapter_order", name="uq_classic_book_chapter_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("classic_books.book_id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    chapter_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AiPrompt(Base):
    __tablename__ = "ai_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class AiAnswerRule(Base):
    __tablename__ = "ai_answer_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keyword: Mapped[str | None] = mapped_column(String(64), nullable=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
