from datetime import datetime

from pydantic import BaseModel, Field


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=16)
    bio: str | None = Field(default=None, max_length=160)


class ProfileResponse(BaseModel):
    id: int
    phone: str
    nickname: str
    avatar_path: str | None = None
    bio: str | None = None
    favorites_count: int = 0
    history_count: int = 0
    ai_records_count: int = 0
    followed_topics: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ArticleRecordRequest(BaseModel):
    article_id: str = Field(..., min_length=1, max_length=64)
    topic: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    desc: str | None = None
    sources: str | None = Field(default=None, max_length=255)
    read_time: str | None = Field(default=None, max_length=32)


class FavoriteArticleResponse(BaseModel):
    id: int
    article_id: str
    topic: str | None = None
    title: str | None = None
    desc: str | None = None
    sources: str | None = None
    read_time: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrowsingHistoryResponse(BaseModel):
    id: int
    article_id: str
    topic: str | None = None
    title: str | None = None
    desc: str | None = None
    sources: str | None = None
    read_time: str | None = None
    visited_at: datetime

    model_config = {"from_attributes": True}


class AiUsageRecordRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    answer: str | None = None
    sources: str | None = Field(default=None, max_length=255)


class AiUsageRecordResponse(BaseModel):
    id: int
    question: str
    answer: str | None = None
    sources: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FollowTopicsRequest(BaseModel):
    topics: list[str] = Field(default_factory=list, max_length=30)


class TodayChecklistItemResponse(BaseModel):
    id: str
    article_id: str
    category: str | None = None
    topic: str | None = None
    title: str
    desc: str | None = None
    source: str | None = None
    sources: str | None = None
    read_time: str | None = None
    image: str | None = None
    relation: str | None = None
    viewed: bool = False


class TodayChecklistResponse(BaseModel):
    articles: list[TodayChecklistItemResponse] = Field(default_factory=list)
    total_count: int = 0
    read_count: int = 0
    is_complete: bool = False


class ReadingPositionRequest(BaseModel):
    chapter_id: int = Field(gt=0)
    scroll_progress: int = Field(default=0, ge=0, le=100)


class ReadingPositionResponse(ReadingPositionRequest):
    book_id: str
    updated_at: datetime

    model_config = {"from_attributes": True}
