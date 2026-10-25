from datetime import datetime
from typing import Any, Literal
from app.schemas.issue import IssueBriefResponse

from pydantic import BaseModel, Field


class ContentCategoryResponse(BaseModel):
    id: int
    name: str
    image: str | None = None
    is_priority: bool = False
    sort_order: int = 0

    model_config = {"from_attributes": True}


class ContentArticleListResponse(BaseModel):
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


class ContentArticleDetailResponse(ContentArticleListResponse):
    issue: IssueBriefResponse | None = None
    policy_checks: list[dict] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)


class ContentFeatureResponse(BaseModel):
    id: int
    title: str
    desc: str | None = None
    tags: str | None = None
    image: str | None = None
    count: int = 0
    category_name: str | None = None

    model_config = {"from_attributes": True}


class DiscoverContentResponse(BaseModel):
    topics: list[ContentCategoryResponse]
    features: list[ContentFeatureResponse]
    updates: list[ContentArticleListResponse]


class ContentPageResponse(BaseModel):
    page_key: str
    title: str
    subtitle: str | None = None
    updated_label: str | None = None
    sections: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime

    model_config = {"from_attributes": True}


class DailyQuoteResponse(BaseModel):
    quote_id: str
    text: str
    source_title: str
    source_author: str | None = None
    source_type: Literal["classical", "ancient", "red", "manifesto"]
    theme: str
    plain_explanation: str
    today_connection: str
    sort_order: int = 0
    is_active: bool = True

    model_config = {"from_attributes": True}


class AiPromptResponse(BaseModel):
    prompts: list[str] = Field(default_factory=list)
    followups: list[str] = Field(default_factory=list)
    welcome_message: str | None = None


class AiAnswerRequest(BaseModel):
    question: str = Field(..., min_length=1)
    article_id: str | None = None
    issue_key: str | None = None
    policy_key: str | None = None


class AiAnswerResponse(BaseModel):
    answer: str
    sources: str | None = None


class AjinChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=20)


class ClassicBookChapterResponse(BaseModel):
    id: int
    book_id: str
    title: str
    chapter_order: int = 0
    summary: str | None = None
    external_url: str | None = None
    content: str | None = None
    has_full_text: bool = False

    model_config = {"from_attributes": True}


class ClassicBookChapterDetailResponse(ClassicBookChapterResponse):
    pass


class ClassicBookListResponse(BaseModel):
    id: int
    book_id: str
    title: str
    author: str | None = None
    category: str | None = None
    description: str | None = None
    cover_image: str | None = None
    source_org: str | None = None
    external_url: str | None = None
    is_featured: bool = True
    sort_order: int = 0

    model_config = {"from_attributes": True}


class ClassicBookDetailResponse(ClassicBookListResponse):
    chapters: list[ClassicBookChapterResponse] = Field(default_factory=list)


class TodayChecklistResponse(BaseModel):
    articles: list[ContentArticleListResponse] = Field(default_factory=list)
    total_count: int = 0
    read_count: int = 0
    is_complete: bool = False


class BreakingNewsSourceResponse(BaseModel):
    name: str
    title: str
    url: str
    summary: str
    published_at: datetime | None = None


class BreakingNewsListResponse(BaseModel):
    id: int
    event_key: str
    title: str
    event_type: str
    summary: str
    image: str
    latest_reported_at: datetime
    sources: list[BreakingNewsSourceResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class BreakingNewsDetailResponse(BreakingNewsListResponse):
    first_confirmed_at: datetime
    is_ongoing: bool = False
