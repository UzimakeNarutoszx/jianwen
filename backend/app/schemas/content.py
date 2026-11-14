from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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
    published_date: date | None = None
    updated_at: datetime | None = None


class ContentArticleDetailResponse(ContentArticleListResponse):
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
    question: str = Field(..., min_length=1, max_length=2000)
    article_id: str | None = None


class AiCitation(BaseModel):
    """一条可点击的原文依据：article_id/title 必填，quote 可为空。"""

    article_id: str
    title: str
    quote: str | None = None


class AiAnswerResponse(BaseModel):
    answer: str
    sources: str | None = None
    citations: list[AiCitation] = Field(default_factory=list)


class AiCitationsRequest(BaseModel):
    """流式回答结束后，前端拿最终文本回查引用来源。"""

    question: str = Field(..., min_length=1, max_length=4000)
    answer: str = Field(..., min_length=1, max_length=200000)
    article_id: str | None = None


class AiCitationsResponse(BaseModel):
    citations: list[AiCitation] = Field(default_factory=list)


class AjinChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=20)

    @field_validator("history")
    @classmethod
    def cap_history_item_length(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        """Trim over-long history messages instead of rejecting the request.

        Chat history is best-effort context; a very long past message should
        not make the whole turn fail with a 422.
        """
        return [
            {
                key: (str(item_value)[:4000] if item_value is not None else "")
                for key, item_value in item.items()
            }
            for item in value
        ]


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
    streak_days: int = 0


class BreakingNewsResponse(BaseModel):
    """置顶的重大会议卡片：字段只包含已核实的会议事实与官方原文链接。"""

    id: int
    event_name: str
    event_type: str
    start_date: date
    end_date: date | None = None
    status: str
    title: str
    summary: str | None = None
    source_name: str
    source_url: str | None = None
    image: str | None = None

    model_config = {"from_attributes": True}


class TodayAudioVoiceResponse(BaseModel):
    """朗读可选声音；顺序即前端显示顺序，第一个为默认。"""

    id: str
    label: str


class TodayAudioTrackResponse(BaseModel):
    """某篇文章某个声音的音频：url 是站内相对路径，duration 单位为秒。"""

    url: str
    duration: float | None = None


class TodayAudioArticleResponse(BaseModel):
    article_id: str
    title: str
    position: int = 0
    audio: dict[str, TodayAudioTrackResponse] = Field(default_factory=dict)


class TodayAudioSegmentResponse(BaseModel):
    """连续音轨里某篇文章的起止秒数。"""

    article_id: str
    start: float
    end: float


class TodayAudioContinuousResponse(BaseModel):
    """把当天所有篇目拼成一条的连续音轨，供熄屏/后台不依赖 JS 连播。"""

    url: str
    duration: float | None = None
    segments: list[TodayAudioSegmentResponse] = Field(default_factory=list)


class TodayAudioResponse(BaseModel):
    """GET /content/today/audio 的响应；ready=false 时前端显示「今日朗读生成中」。"""

    date: date
    ready: bool = False
    voices: list[TodayAudioVoiceResponse] = Field(default_factory=list)
    articles: list[TodayAudioArticleResponse] = Field(default_factory=list)
    continuous: dict[str, TodayAudioContinuousResponse] = Field(default_factory=dict)
    generated_at: str | None = None
