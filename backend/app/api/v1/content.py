from datetime import date, datetime, timedelta
import difflib
import json
import logging
from pathlib import Path
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.core.config import settings
from app.core.timeutil import today_cn
from app.crud.user import AiQuotaExceeded, ai_quota_used, consume_ai_quota, refund_ai_quota
from app.db.session import SessionLocal
from app.models.content import (
    AiAnswerRule,
    AiPrompt,
    ClassicBook,
    ClassicBookChapter,
    ContentArticle,
    ContentCategory,
    ContentFeature,
    ContentPage,
    DailyArticleSet,
    DailyQuote,
)
from app.models.profile import UserAiUsageRecord, UserBrowsingHistory, UserFollowTopic
from app.models.reading import ArticleReadingDay
from app.models.user import User
from app.services.breaking_news import active_breaking_news, card_payload
from app.services.daily_articles import AI_ARTICLE_ID_PREFIX, get_content_date, read_daily_articles
from app.schemas.content import (
    AiAnswerRequest,
    AiAnswerResponse,
    AiCitation,
    AiCitationsRequest,
    AiCitationsResponse,
    AjinChatRequest,
    AiPromptResponse,
    BreakingNewsResponse,
    ClassicBookChapterDetailResponse,
    ClassicBookChapterResponse,
    ClassicBookDetailResponse,
    ClassicBookListResponse,
    ContentArticleDetailResponse,
    ContentArticleListResponse,
    ContentCategoryResponse,
    ContentPageResponse,
    DailyQuoteResponse,
    DiscoverContentResponse,
    TodayChecklistResponse,
    TodayAudioArticleResponse,
    TodayAudioContinuousResponse,
    TodayAudioSegmentResponse,
    TodayAudioResponse,
)
from services.ai import AIClientError, ask as ask_ai, ask_ajin, stream_ask


router = APIRouter()
logger = logging.getLogger(__name__)

_UPDATES_HARD_LIMIT = 120
_UPDATES_RECENT_DAYS = 15
_UPDATES_MID_DAYS = 30
_UPDATES_MID_DAILY_CAP = 2
_UPDATES_OLD_DAYS = 90
_UPDATES_OLD_WEEKLY_CAP = 2
_ASK_CONTEXT_RECENT_LIMIT = 20
_ASK_CONTEXT_RELATED_LIMIT = 10
_ASK_CONTEXT_QUESTION_KEYWORD_LIMIT = 6
# 一次回答最多回传多少条引用，避免模型大段复述编号时撑大响应。
_AI_CITATION_LIMIT = 5
# 回答里的 [n] 标记；编号对应上下文里带 [n] 前缀的文章。
_AI_CITATION_MARKER = re.compile(r"\[(\d{1,3})\]")
# 无标记降级匹配的标题片段最短长度；过短的片段太容易误命中。
_AI_CITATION_TITLE_MIN_LENGTH = 4
_AI_CITATION_QUOTE_MAX_LENGTH = 120
_AI_DAILY_ID_PATTERN = re.compile(rf"^{AI_ARTICLE_ID_PREFIX}-(\d{{8}})-(\d+)$")


def _as_list(value: list | None) -> list:
    return value if isinstance(value, list) else []


def _article_list_response(article: ContentArticle, viewed_article_ids: set[str] | None = None) -> ContentArticleListResponse:
    viewed_ids = viewed_article_ids or set()
    published_date = getattr(article, "_published_date", None)
    if published_date is None:
        published_date = _article_published_date(article)
    return ContentArticleListResponse(
        id=article.article_id,
        article_id=article.article_id,
        category=article.category,
        topic=article.topic or article.category,
        title=article.title,
        desc=article.desc,
        source=article.sources,
        sources=article.sources,
        read_time=article.read_time,
        image=article.image,
        relation=article.relation,
        viewed=article.article_id in viewed_ids,
        published_date=published_date,
        updated_at=article.updated_at,
    )


def _article_detail_response(article: ContentArticle) -> ContentArticleDetailResponse:
    return ContentArticleDetailResponse(
        **_article_list_response(article).model_dump(),
        summary=_as_list(article.summary),
        sections=_as_list(article.sections),
        references=_as_list(article.references),
    )


def _chapter_response(chapter: ClassicBookChapter, include_content: bool = False) -> ClassicBookChapterResponse:
    return ClassicBookChapterResponse(
        id=chapter.id,
        book_id=chapter.book_id,
        title=chapter.title,
        chapter_order=chapter.chapter_order,
        summary=chapter.summary,
        external_url=chapter.external_url,
        content=chapter.content if include_content else None,
        has_full_text=bool(chapter.content),
    )


def _book_list_response(book: ClassicBook) -> ClassicBookListResponse:
    return ClassicBookListResponse(
        id=book.id,
        book_id=book.book_id,
        title=book.title,
        author=book.author,
        category=book.category,
        description=book.description,
        cover_image=book.cover_image,
        source_org=book.source_org,
        external_url=book.external_url,
        is_featured=book.is_featured,
        sort_order=book.sort_order,
    )


def _today_articles(db: Session) -> list[ContentArticle]:
    return read_daily_articles(db, get_content_date())[:5]


# 声音顺序即前端显示顺序，第一个为默认；manifest 缺失时用它兜底。
_TODAY_AUDIO_VOICES = (
    {"id": "jianwen", "label": "见闻"},
    {"id": "dylan", "label": "男声·京味"},
)


def _audio_voices(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    voices = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        voice_id = str(entry.get("id") or "").strip()
        if voice_id:
            voices.append({"id": voice_id, "label": str(entry.get("label") or voice_id)})
    return voices


def _audio_tracks(value: object) -> dict[str, dict]:
    """只接受站内相对路径的音频；其他形态的 url 一律丢弃。"""
    if not isinstance(value, dict):
        return {}
    tracks: dict[str, dict] = {}
    for voice_id, track in value.items():
        if not isinstance(track, dict):
            continue
        url = str(track.get("url") or "")
        if not url.startswith("/uploads/"):
            continue
        duration = track.get("duration")
        tracks[str(voice_id)] = {
            "url": url,
            "duration": float(duration) if isinstance(duration, (int, float)) else None,
        }
    return tracks


def _viewed_article_ids(db: Session, user: User | None, article_ids: list[str]) -> set[str]:
    if user is None or not article_ids:
        return set()
    return {
        row.article_id
        for row in (
            db.query(UserBrowsingHistory.article_id)
            .filter(UserBrowsingHistory.user_id == user.id, UserBrowsingHistory.article_id.in_(article_ids))
            .all()
        )
    }


def _followed_topics(db: Session, user: User | None) -> list[str]:
    if user is None:
        return []
    return [
        row.topic
        for row in (
            db.query(UserFollowTopic)
            .filter(UserFollowTopic.user_id == user.id)
            .order_by(UserFollowTopic.sort_order, UserFollowTopic.id)
            .all()
        )
    ]


def _personalize_articles(articles: list[ContentArticle], topics: list[str]) -> list[ContentArticle]:
    if not topics:
        return articles

    topic_rank = {topic: index for index, topic in enumerate(topics)}

    def rank(article: ContentArticle) -> tuple[int, int, int, int]:
        article_topics = [article.topic or "", article.category or ""]
        matched = [topic_rank[value] for value in article_topics if value in topic_rank]
        daily_position = getattr(article, "_daily_position", article.today_order)
        if matched:
            return (0, min(matched), daily_position, article.sort_order)
        return (1, len(topic_rank), daily_position, article.sort_order)

    return sorted(articles, key=rank)


def _reading_streak_days(db: Session, user: User | None) -> int:
    """连续阅读天数：从今天往前数有阅读记录的天数；今天没读则从昨天开始。"""
    if user is None:
        return 0
    days = {
        row[0]
        for row in db.query(ArticleReadingDay.content_date)
        .filter(ArticleReadingDay.user_id == user.id)
        .distinct()
        .all()
    }
    if not days:
        return 0
    today = get_content_date()
    day = today if today in days else today - timedelta(days=1)
    streak = 0
    while day in days and streak < 3650:
        streak += 1
        day -= timedelta(days=1)
    return streak


def _today_checklist_response(
    articles: list[ContentArticle],
    viewed_ids: set[str] | None = None,
    streak_days: int = 0,
) -> TodayChecklistResponse:
    viewed_article_ids = viewed_ids or set()
    items = [_article_list_response(article, viewed_article_ids) for article in articles]
    read_count = sum(1 for item in items if item.viewed)
    return TodayChecklistResponse(
        articles=items,
        total_count=len(items),
        read_count=read_count,
        is_complete=bool(items) and read_count == len(items),
        streak_days=streak_days,
    )


def _article_context(article: ContentArticle, index: int | None = None) -> str:
    """把一篇文章压成给模型的上下文。

    ``index`` 是这篇文章在本次上下文里的编号（从 1 开始）：模型回答里出现
    ``[n]`` 时，用同一个编号回查文章，生成可点击的引用来源。
    """
    summary = "；".join(str(item) for item in _as_list(article.summary) if item)
    sections = []
    for section in _as_list(article.sections):
        if not isinstance(section, dict):
            continue
        heading = section.get("heading", "")
        body = section.get("body", "")
        if heading or body:
            sections.append(f"{heading}：{body}".strip("："))
    references = []
    for reference in _as_list(article.references):
        if not isinstance(reference, dict):
            continue
        title = reference.get("title", "")
        org = reference.get("org", "")
        if title or org:
            references.append(f"{title}（{org}）".strip("（）"))

    article_line = f"文章ID：{article.article_id}"
    if index is not None:
        article_line = f"[{index}] {article_line}"

    return "\n".join(
        part
        for part in [
            article_line,
            f"标题：{article.title}",
            f"主题：{article.topic or article.category or ''}",
            f"来源：{article.sources or ''}",
            f"一句话说明：{article.desc or ''}",
            f"摘要：{summary}",
            f"正文要点：{' | '.join(sections)}",
            f"依据：{'；'.join(references)}",
        ]
        if part.strip()
    )


def _trim_quote(text: str) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= _AI_CITATION_QUOTE_MAX_LENGTH:
        return normalized
    return normalized[: _AI_CITATION_QUOTE_MAX_LENGTH - 1] + "…"


def _article_quote(article: ContentArticle) -> str | None:
    """取文章里最适合当“依据段落”的一句原文；没有可摘录内容时返回 None。"""
    for item in _as_list(getattr(article, "summary", None)):
        quote = _trim_quote(str(item))
        if quote:
            return quote
    quote = _trim_quote(str(getattr(article, "desc", "") or ""))
    return quote or None


def _title_matches_answer(title: str, answer: str) -> bool:
    """保守判断回答是否提到了某篇文章：完整标题，或足够长的标题片段。"""
    compact_title = re.sub(r"\s+", "", title or "")
    compact_answer = re.sub(r"\s+", "", answer or "")
    if not compact_title or not compact_answer or len(compact_title) < _AI_CITATION_TITLE_MIN_LENGTH:
        return False
    if compact_title in compact_answer:
        return True

    matched = 0
    longest = 0
    matcher = difflib.SequenceMatcher(None, compact_title, compact_answer, autojunk=False)
    for block in matcher.get_matching_blocks():
        if block.size < 2:
            continue
        matched += block.size
        longest = max(longest, block.size)
    # 至少要有一段 4 字以上的连续命中，且总命中量不少于标题的一半。
    threshold = max(_AI_CITATION_TITLE_MIN_LENGTH, (len(compact_title) + 1) // 2)
    return longest >= _AI_CITATION_TITLE_MIN_LENGTH and matched >= threshold


def _match_citations_by_title(answer: str, articles: list[ContentArticle]) -> list[AiCitation]:
    """模型没写 [n] 时，用标题/关键词做保守匹配：宁缺毋滥。"""
    citations: list[AiCitation] = []
    for article in articles:
        title = str(getattr(article, "title", "") or "")
        if not _title_matches_answer(title, answer):
            continue
        article_id = str(getattr(article, "article_id", "") or "")
        if not article_id:
            continue
        citations.append(AiCitation(article_id=article_id, title=title, quote=_article_quote(article)))
        if len(citations) >= _AI_CITATION_LIMIT:
            break
    return citations


def _citations_from_answer(answer: str, articles: list[ContentArticle]) -> list[AiCitation]:
    """把回答里的 [n] 标记映射回本次上下文里的文章。

    解析失败或没有任何可靠依据时一律返回空列表，绝不让问诊接口因此报错。
    """
    try:
        if not isinstance(answer, str) or not answer.strip() or not articles:
            return []

        citations: list[AiCitation] = []
        seen: set[str] = set()
        for match in _AI_CITATION_MARKER.finditer(answer):
            index = int(match.group(1))
            if index < 1 or index > len(articles):
                continue
            article = articles[index - 1]
            article_id = str(getattr(article, "article_id", "") or "")
            if not article_id or article_id in seen:
                continue
            seen.add(article_id)
            citations.append(
                AiCitation(
                    article_id=article_id,
                    title=str(getattr(article, "title", "") or ""),
                    quote=_article_quote(article),
                )
            )
            if len(citations) >= _AI_CITATION_LIMIT:
                break
        if citations:
            return citations
        # 模型没按约定标注时，退回保守的标题/关键词匹配。
        return _match_citations_by_title(answer, articles)
    except Exception:
        logger.warning("Failed to parse AI answer citations", exc_info=True)
        return []


def _local_answer(db: Session, question: str) -> AiAnswerResponse | None:
    rules = (
        db.query(AiAnswerRule)
        .filter(AiAnswerRule.is_active.is_(True))
        .order_by(AiAnswerRule.sort_order, AiAnswerRule.id)
        .all()
    )
    fallback = None
    for rule in rules:
        if not rule.keyword:
            fallback = rule
            continue
        if rule.keyword in question:
            return AiAnswerResponse(answer=rule.answer, sources=rule.sources)
    if fallback:
        return AiAnswerResponse(answer=fallback.answer, sources=fallback.sources)
    return None


def _ajin_fallback_answer(question: str) -> AiAnswerResponse:
    """Keep 阿烬 usable when the configured external model is unavailable."""
    text = question.strip()
    if any(word in text for word in ("架子鼓", "鼓", "音乐", "BGM")):
        answer = "可以先把目标拆小：选一首熟悉的歌，先用慢速练底鼓和军鼓的基本拍，再逐步加上镲片和填充。录一遍回听，比盯着谱子更容易发现节奏问题。"
    elif any(word in text for word in ("代码", "Python", "编程", "项目")):
        answer = "先把问题缩成一个能运行的小例子，再逐步加回原来的功能。遇到报错时先看完整错误信息和出错位置，修一个变量后立刻重跑，别一次改很多处。"
    elif any(word in text for word in ("数学", "方程", "几何")):
        answer = "先把已知条件和要证明的目标写清楚，再找它们之间最直接的关系。卡住时回到定义或画图，通常比继续套公式更快。"
    else:
        answer = "我现在暂时接不上外部模型，但这个问题可以继续聊。先把你最想解决的一个具体点说出来，我们从那里往下拆。"
    return AiAnswerResponse(answer=answer, sources="阿烬本地应急回复；外部 AI 服务恢复后将继续提供完整对话。")


def _ensure_ai_quota(db: Session, user: User) -> None:
    """Charge one question against today's quota.

    The counter lives in ``user_ai_daily_usage`` (not the record rows) and is
    incremented atomically, so deleting chat history does not refund quota and
    concurrent requests cannot exceed the daily limit.
    """
    try:
        consume_ai_quota(db, user.id, settings.AI_DAILY_QUESTION_LIMIT)
    except AiQuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"今日 AI 提问额度已用完，每日最多 {settings.AI_DAILY_QUESTION_LIMIT} 个问题",
        ) from exc


def _save_ai_usage(db: Session, user: User, question: str, answer: str, sources: str | None) -> None:
    db.add(UserAiUsageRecord(user_id=user.id, question=question, answer=answer, sources=sources))
    db.commit()


def _record_stream_usage(user_id: int, question: str, answer: str, sources: str | None) -> None:
    """Persist streamed-answer usage on a fresh session.

    Streaming responses outlive the request-scoped session, so this opens its
    own short-lived session. Failures are logged, never raised: the answer has
    already been delivered to the client.
    """
    try:
        with SessionLocal() as db:
            db.add(UserAiUsageRecord(user_id=user_id, question=question, answer=answer, sources=sources))
            db.commit()
    except Exception:
        logger.exception("Failed to record streamed AI usage for user %s", user_id)


def _refund_ai_quota(user_id: int, usage_date: date | None = None) -> None:
    """Give the daily quota back when no answer reached the client.

    ``usage_date`` is the day the question was charged on: a refund that ran
    after the 06:00 rollover must still hit the original day's row.
    """
    try:
        with SessionLocal() as db:
            refund_ai_quota(db, user_id, usage_date)
    except Exception:
        logger.exception("Failed to refund AI quota for user %s", user_id)


def _question_keywords(question: str) -> list[str]:
    """Rough Chinese keyword extraction for narrowing the AI context."""
    text = (question or "").strip()
    if not text:
        return []
    keywords: list[str] = []
    # Latin words / numbers are meaningful on their own.
    keywords.extend(re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", text))
    # Chinese has no spaces: fall back to 2-4 character sliding windows.
    han_runs = re.findall(r"[一-鿿]{2,}", text)
    for run in han_runs:
        if len(run) <= 4:
            keywords.append(run)
            continue
        for size in (2, 3, 4):
            for start in range(0, len(run) - size + 1):
                keywords.append(run[start : start + size])
    seen: list[str] = []
    for keyword in keywords:
        if keyword and keyword not in seen:
            seen.append(keyword)
        if len(seen) >= _ASK_CONTEXT_QUESTION_KEYWORD_LIMIT:
            break
    return seen


def _select_ask_articles(
    db: Session, article_id: str | None = None, question: str | None = None
) -> tuple[list[ContentArticle], ContentArticle | None]:
    """选出本次回答可用的文章，顺序即给模型标注的 [1]…[n]。

    Sending the whole catalog bloats the prompt and slows answers, so only the
    current article, articles matching the question, and the most recent N
    articles are included.
    """
    recent_articles = (
        db.query(ContentArticle)
        .order_by(ContentArticle.created_at.desc(), ContentArticle.id.desc())
        .limit(_ASK_CONTEXT_RECENT_LIMIT)
        .all()
    )
    linked_article: ContentArticle | None = None
    if article_id:
        linked_article = db.query(ContentArticle).filter(ContentArticle.article_id == article_id).first()

    related_articles: list[ContentArticle] = []
    keywords = _question_keywords(question or "")
    if keywords:
        conditions = []
        for keyword in keywords:
            like = f"%{keyword}%"
            conditions.extend(
                [
                    ContentArticle.title.like(like),
                    ContentArticle.desc.like(like),
                    ContentArticle.topic.like(like),
                    ContentArticle.category.like(like),
                ]
            )
        related_articles = (
            db.query(ContentArticle)
            .filter(or_(*conditions))
            .order_by(ContentArticle.created_at.desc(), ContentArticle.id.desc())
            .limit(_ASK_CONTEXT_RELATED_LIMIT)
            .all()
        )

    selected: list[ContentArticle] = []
    seen_ids: set[str] = set()
    for candidate in ([linked_article] if linked_article else []) + related_articles + recent_articles:
        if candidate.article_id in seen_ids:
            continue
        seen_ids.add(candidate.article_id)
        selected.append(candidate)
    return selected, linked_article


def _ask_context_from_articles(
    selected: list[ContentArticle], linked_article: ContentArticle | None = None
) -> dict[str, object]:
    """把选好的文章渲染成带 [n] 编号的模型上下文。"""
    context: dict[str, object] = {
        "相关文章资料库": [_article_context(article, index=index + 1) for index, article in enumerate(selected)],
        "引用标注要求": (
            "回答中如果某句话依据上面某篇文章，就在句末标注该文章编号，例如 [1]；"
            "同一句引用多篇写成 [1][2]。没有依据的句子不要标注。"
        ),
    }
    if linked_article is not None:
        linked_index = next(
            (
                index + 1
                for index, article in enumerate(selected)
                if article.article_id == linked_article.article_id
            ),
            None,
        )
        context["当前关联文章"] = _article_context(linked_article, index=linked_index)
    return context


def _build_ask_context(
    db: Session, article_id: str | None = None, question: str | None = None
) -> dict[str, object]:
    selected, linked_article = _select_ask_articles(db, article_id, question)
    return _ask_context_from_articles(selected, linked_article)


@router.get("/categories", response_model=list[ContentCategoryResponse])
def list_categories(db: Session = Depends(get_db)) -> list[ContentCategory]:
    return (
        db.query(ContentCategory)
        .order_by(ContentCategory.is_priority.desc(), ContentCategory.sort_order, ContentCategory.id)
        .all()
    )


@router.get("/today", response_model=list[ContentArticleListResponse])
def list_today_articles(db: Session = Depends(get_db)) -> list[ContentArticleListResponse]:
    return [_article_list_response(article) for article in _today_articles(db)]


@router.get("/today/personalized", response_model=TodayChecklistResponse)
def get_personalized_today(
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> TodayChecklistResponse:
    articles = _today_articles(db)
    topics = _followed_topics(db, current_user)
    sorted_articles = _personalize_articles(articles, topics)
    viewed_ids = _viewed_article_ids(db, current_user, [article.article_id for article in sorted_articles])
    return _today_checklist_response(sorted_articles, viewed_ids, _reading_streak_days(db, current_user))


@router.get("/today/audio", response_model=TodayAudioResponse)
def get_today_audio(db: Session = Depends(get_db)) -> TodayAudioResponse:
    """今日朗读：只读 manifest，不生成音频，也不需要登录。

    文件不存在或解析失败时返回 ready=false，前端显示「今日朗读生成中」，
    不作为错误处理。日期只取自服务端 ``get_content_date()``，不接受外部输入，
    因此不存在路径穿越。
    """
    content_date = get_content_date()
    manifest_date = content_date.isoformat()
    # manifest 在 <UPLOAD_DIR>/tts/<date>/manifest.json；date 由服务端算出来，不拼外部参数。
    manifest_path = Path(settings.UPLOAD_DIR) / "tts" / manifest_date / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.info("Today audio manifest unavailable for %s", manifest_date)
        return TodayAudioResponse(date=content_date, ready=False, voices=_TODAY_AUDIO_VOICES)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("articles"), list):
        logger.warning("Today audio manifest is malformed for %s", manifest_date)
        return TodayAudioResponse(date=content_date, ready=False, voices=_TODAY_AUDIO_VOICES)

    # 只保留属于当日文章集的条目，并按当日顺序排列；manifest 里的顺序不可信。
    positions = {article.article_id: index for index, article in enumerate(_today_articles(db))}
    articles: list[TodayAudioArticleResponse] = []
    for entry in manifest["articles"]:
        if not isinstance(entry, dict):
            continue
        article_id = str(entry.get("article_id") or "")
        if article_id not in positions:
            continue
        articles.append(
            TodayAudioArticleResponse(
                article_id=article_id,
                title=str(entry.get("title") or ""),
                position=positions[article_id],
                audio=_audio_tracks(entry.get("audio")),
            )
        )
    articles.sort(key=lambda item: item.position)

    manifest_voices = _audio_voices(manifest.get("voices"))
    generated_at = manifest.get("generated_at")

    # 连续音轨：只保留属于当日文章的片段，段内文章必须真实存在。
    continuous: dict[str, TodayAudioContinuousResponse] = {}
    raw_continuous = manifest.get("continuous")
    if isinstance(raw_continuous, dict):
        for voice_id, entry in raw_continuous.items():
            if not isinstance(entry, dict) or not entry.get("url"):
                continue
            segments: list[TodayAudioSegmentResponse] = []
            for segment in entry.get("segments") or []:
                if not isinstance(segment, dict):
                    continue
                article_id = str(segment.get("article_id") or "")
                if article_id not in positions:
                    continue
                try:
                    start = float(segment.get("start"))
                    end = float(segment.get("end"))
                except (TypeError, ValueError):
                    continue
                if end <= start:
                    continue
                segments.append(TodayAudioSegmentResponse(article_id=article_id, start=start, end=end))
            if segments:
                duration = entry.get("duration")
                continuous[str(voice_id)] = TodayAudioContinuousResponse(
                    url=str(entry["url"]),
                    duration=float(duration) if isinstance(duration, (int, float)) else None,
                    segments=segments,
                )

    return TodayAudioResponse(
        date=content_date,
        ready=True,
        voices=manifest_voices or _TODAY_AUDIO_VOICES,
        articles=articles,
        continuous=continuous,
        generated_at=str(generated_at) if generated_at else None,
    )


@router.get("/articles", response_model=list[ContentArticleListResponse])
def list_articles(
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ContentArticleListResponse]:
    query = db.query(ContentArticle)
    if category:
        query = query.filter(ContentArticle.category == category)
    if q:
        keyword = q.strip()
        query = query.filter(
            or_(
                ContentArticle.category.contains(keyword, autoescape=True),
                ContentArticle.topic.contains(keyword, autoescape=True),
                ContentArticle.title.contains(keyword, autoescape=True),
                ContentArticle.desc.contains(keyword, autoescape=True),
                ContentArticle.sources.contains(keyword, autoescape=True),
            )
        )
    articles = query.order_by(ContentArticle.sort_order, ContentArticle.id).all()
    return [_article_list_response(article) for article in articles]


@router.get("/articles/{article_id}", response_model=ContentArticleDetailResponse)
def get_article(article_id: str, db: Session = Depends(get_db)) -> ContentArticleDetailResponse:
    article = db.query(ContentArticle).filter(ContentArticle.article_id == article_id).first()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    return _article_detail_response(article)


@router.get("/articles/{article_id}/related", response_model=list[ContentArticleListResponse])
def list_related_articles(
    article_id: str,
    limit: Annotated[int, Query(ge=1, le=12)] = 4,
    db: Session = Depends(get_db),
) -> list[ContentArticleListResponse]:
    article = db.query(ContentArticle).filter(ContentArticle.article_id == article_id).first()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在")
    matches = []
    if article.topic:
        matches.append(ContentArticle.topic == article.topic)
    if article.category:
        matches.append(ContentArticle.category == article.category)
    if not matches:
        return []
    # A topic match is more specific than a shared category.
    ranking = case(*[(condition, index) for index, condition in enumerate(matches)], else_=len(matches))
    articles = (
        db.query(ContentArticle)
        .filter(ContentArticle.article_id != article_id, or_(*matches))
        .order_by(ranking, ContentArticle.sort_order, ContentArticle.id)
        .limit(limit)
        .all()
    )
    return [_article_list_response(item) for item in articles]


def _article_published_date(
    article: ContentArticle, daily_dates: dict[str, date] | None = None
) -> date | None:
    """Resolve a publish date: daily set first, then ai-daily id, then created_at."""
    if daily_dates:
        stored = daily_dates.get(article.article_id)
        if stored is not None:
            return stored
    match = _AI_DAILY_ID_PATTERN.match(article.article_id or "")
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            pass
    created_at = article.created_at
    if isinstance(created_at, datetime):
        return created_at.date()
    if isinstance(created_at, date):
        return created_at
    return None


def _updates_are_important(
    published: date,
    today: date,
    mid_day_counts: dict[date, int],
    old_week_counts: dict[tuple[int, int], int],
) -> tuple[bool, int, int]:
    """Decide whether one article is kept, returning (keep, mid, old) counters.

    Recency tiers, measured against today in Asia/Shanghai:
    0-15 days keep everything, 15-30 days keep at most 2 per day,
    30-90 days keep at most 2 per ISO week, older than 90 days is dropped.
    Search is unaffected because this only filters /discover updates.
    """
    age_days = (today - published).days
    if age_days < 0:
        # A future-dated entry is still the newest thing we have; keep it.
        return True, 0, 0
    if age_days <= _UPDATES_RECENT_DAYS:
        return True, 0, 0
    if age_days <= _UPDATES_MID_DAYS:
        used = mid_day_counts.get(published, 0)
        if used >= _UPDATES_MID_DAILY_CAP:
            return False, 0, 0
        return True, 1, 0
    if age_days <= _UPDATES_OLD_DAYS:
        iso_year, iso_week, _weekday = published.isocalendar()
        key = (iso_year, iso_week)
        used = old_week_counts.get(key, 0)
        if used >= _UPDATES_OLD_WEEKLY_CAP:
            return False, 0, 0
        return True, 0, 1
    return False, 0, 0


def _discover_updates(db: Session, today: date | None = None) -> list[ContentArticle]:
    """Recent ai-daily articles, newest first, with importance-based thinning."""
    reference_day = today or today_cn()
    rows = (
        db.query(ContentArticle)
        .filter(ContentArticle.article_id.startswith(f"{AI_ARTICLE_ID_PREFIX}-"))
        .all()
    )
    if not rows:
        return []

    daily_dates = {
        row.article_id: row.content_date
        for row in db.query(DailyArticleSet)
        .filter(DailyArticleSet.article_id.in_([article.article_id for article in rows]))
        .all()
    }

    published_by_id: dict[str, date | None] = {}
    position_by_id: dict[str, int] = {}
    for article in rows:
        published_by_id[article.article_id] = _article_published_date(article, daily_dates)
        match = _AI_DAILY_ID_PATTERN.match(article.article_id)
        position_by_id[article.article_id] = int(match.group(2)) if match else 0

    ordered = sorted(
        (article for article in rows if published_by_id[article.article_id] is not None),
        key=lambda article: (
            -published_by_id[article.article_id].toordinal(),
            position_by_id[article.article_id],
            -article.id,
        ),
    )

    kept: list[ContentArticle] = []
    mid_day_counts: dict[date, int] = {}
    old_week_counts: dict[tuple[int, int], int] = {}
    for article in ordered:
        published = published_by_id[article.article_id]
        keep, mid, old = _updates_are_important(published, reference_day, mid_day_counts, old_week_counts)
        if not keep:
            continue
        if mid:
            mid_day_counts[published] = mid_day_counts.get(published, 0) + 1
        if old:
            iso_year, iso_week, _weekday = published.isocalendar()
            old_week_counts[(iso_year, iso_week)] = old_week_counts.get((iso_year, iso_week), 0) + 1
        setattr(article, "_published_date", published)
        kept.append(article)
        if len(kept) >= _UPDATES_HARD_LIMIT:
            break
    return kept


@router.get("/discover", response_model=DiscoverContentResponse)
def get_discover_content(db: Session = Depends(get_db)) -> DiscoverContentResponse:
    topics = list_categories(db)
    features = db.query(ContentFeature).order_by(ContentFeature.sort_order, ContentFeature.id).all()
    updates = _discover_updates(db)
    return DiscoverContentResponse(
        topics=topics,
        features=features,
        updates=[_article_list_response(article) for article in updates],
    )


@router.get("/classic-books", response_model=list[ClassicBookListResponse])
def list_classic_books(db: Session = Depends(get_db)) -> list[ClassicBookListResponse]:
    books = (
        db.query(ClassicBook)
        .filter(ClassicBook.is_featured.is_(True))
        .order_by(ClassicBook.sort_order, ClassicBook.id)
        .all()
    )
    return [_book_list_response(book) for book in books]


@router.get("/classic-books/{book_id}", response_model=ClassicBookDetailResponse)
def get_classic_book(book_id: str, db: Session = Depends(get_db)) -> ClassicBookDetailResponse:
    book = db.query(ClassicBook).filter(ClassicBook.book_id == book_id).first()
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="经典文献不存在")

    chapters = (
        db.query(ClassicBookChapter)
        .filter(ClassicBookChapter.book_id == book.book_id)
        .order_by(ClassicBookChapter.chapter_order, ClassicBookChapter.id)
        .all()
    )
    return ClassicBookDetailResponse(
        **_book_list_response(book).model_dump(),
        chapters=[_chapter_response(chapter) for chapter in chapters],
    )


@router.get("/classic-books/{book_id}/chapters/{chapter_id}", response_model=ClassicBookChapterDetailResponse)
def get_classic_book_chapter(
    book_id: str,
    chapter_id: int,
    db: Session = Depends(get_db),
) -> ClassicBookChapterDetailResponse:
    chapter = (
        db.query(ClassicBookChapter)
        .filter(
            ClassicBookChapter.book_id == book_id,
            ClassicBookChapter.id == chapter_id,
        )
        .first()
    )
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classic book chapter not found")

    return ClassicBookChapterDetailResponse(**_chapter_response(chapter, include_content=True).model_dump())


@router.get("/pages/{page_key}", response_model=ContentPageResponse)
def get_content_page(page_key: str, db: Session = Depends(get_db)) -> ContentPage:
    page = db.query(ContentPage).filter(ContentPage.page_key == page_key).first()
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="页面内容不存在")
    return page


@router.get("/breaking-news", response_model=list[BreakingNewsResponse])
def list_breaking_news(db: Session = Depends(get_db)) -> list[dict]:
    """当前应置顶的重大会议，无需登录；只读数据库，绝不在请求里联网。"""
    return [card_payload(row) for row in active_breaking_news(db)]


@router.get("/daily-quote", response_model=DailyQuoteResponse)
def get_daily_quote(
    date_value: str | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
) -> DailyQuote:
    if date_value:
        try:
            selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date 必须是 YYYY-MM-DD") from exc
    else:
        selected_date = today_cn()

    quotes = (
        db.query(DailyQuote)
        .filter(DailyQuote.is_active.is_(True))
        .order_by(DailyQuote.sort_order, DailyQuote.id)
        .all()
    )
    if not quotes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无每日金句")

    date_number = int(selected_date.strftime("%Y%m%d"))
    return quotes[date_number % len(quotes)]


@router.get("/ask/prompts", response_model=AiPromptResponse)
def get_ask_prompts(db: Session = Depends(get_db)) -> AiPromptResponse:
    records = db.query(AiPrompt).order_by(AiPrompt.sort_order, AiPrompt.id).all()
    prompts = [record.text for record in records if record.prompt_type == "prompt"]
    followups = [record.text for record in records if record.prompt_type == "followup"]
    welcome = next((record.text for record in records if record.prompt_type == "welcome"), None)
    return AiPromptResponse(prompts=prompts, followups=followups, welcome_message=welcome)


@router.get("/ai/quota")
def get_ai_quota(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    limit = settings.AI_DAILY_QUESTION_LIMIT
    used = ai_quota_used(db, current_user.id)
    return {"limit": limit, "used": used, "remaining": max(0, limit - used)}


@router.get("/ask/bootstrap", response_model=AiPromptResponse)
def get_ask_bootstrap(db: Session = Depends(get_db)) -> AiPromptResponse:
    return get_ask_prompts(db)


@router.post("/ask/answer", response_model=AiAnswerResponse)
def answer_question(
    payload: AiAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AiAnswerResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题不能为空")

    _ensure_ai_quota(db, current_user)
    quota_date = today_cn()

    try:
        context_articles, linked_article = _select_ask_articles(db, payload.article_id, question)
        result = ask_ai(question, context=_ask_context_from_articles(context_articles, linked_article))
    except AIClientError as exc:
        logger.warning("Ark AI request failed: %s", exc)
        fallback = _local_answer(db, question)
        if fallback is None:
            fallback = AiAnswerResponse(
                answer="外部 AI 服务暂时不可用。你可以先根据页面中的文章和来源继续阅读，稍后再试。",
                sources="见闻本地应急回复",
            )
        elif not fallback.sources:
            # Rule-based answers must not look like AI-generated content.
            fallback = AiAnswerResponse(answer=fallback.answer, sources="见闻本地规则兜底，非 AI 生成")
        _save_ai_usage(db, current_user, question, fallback.answer, fallback.sources)
        return fallback

    if not result.text:
        # No answer was produced, so the question must not be charged.
        refund_ai_quota(db, current_user.id, quota_date)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI 未返回有效回答")

    sources = "AI 回答基于公开信息整理，涉及具体办理请以官方来源为准。"
    citations = _citations_from_answer(result.text, context_articles)
    _save_ai_usage(db, current_user, question, result.text, sources)
    return AiAnswerResponse(
        answer=result.text,
        sources=sources,
        citations=citations,
    )


@router.post("/ask/citations", response_model=AiCitationsResponse)
def resolve_ask_citations(
    payload: AiCitationsRequest,
    db: Session = Depends(get_db),
) -> AiCitationsResponse:
    """按本次提问的文章上下文解析回答里的引用来源。

    流式接口逐字返回纯文本，无法在流里附带结构化来源；前端在回答结束后
    用最终文本调这个接口，补上可点击的引用。这里不调用 AI、不扣额度，
    任何解析异常都返回空列表。
    """
    try:
        context_articles, _linked_article = _select_ask_articles(db, payload.article_id, payload.question)
        citations = _citations_from_answer(payload.answer, context_articles)
    except Exception:
        logger.warning("Failed to resolve ask citations", exc_info=True)
        return AiCitationsResponse()
    return AiCitationsResponse(citations=citations)


@router.post("/ask", response_model=AiAnswerResponse)
def answer_question_short(
    payload: AiAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AiAnswerResponse:
    return answer_question(payload, db, current_user)


@router.post("/ajin/chat", response_model=AiAnswerResponse)
def chat_with_ajin(
    payload: AjinChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AiAnswerResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题不能为空")

    _ensure_ai_quota(db, current_user)
    quota_date = today_cn()
    try:
        result = ask_ajin(question, history=payload.history)
    except AIClientError as exc:
        logger.warning("Ajin AI request failed: %s", exc)
        fallback = _ajin_fallback_answer(question)
        _save_ai_usage(db, current_user, question, fallback.answer, fallback.sources)
        return fallback

    if not result.text:
        # No answer was produced, so the question must not be charged.
        refund_ai_quota(db, current_user.id, quota_date)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="阿烬没有返回有效回答")

    _save_ai_usage(db, current_user, question, result.text, "阿烬对话")
    return AiAnswerResponse(answer=result.text, sources="阿烬的回答仅供交流参考；重要事实请核对可靠来源。")


@router.post("/ask/stream")
def stream_answer_question(
    payload: AiAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="问题不能为空")

    # Read the id first: _ensure_ai_quota commits, which expires every attribute
    # on ``current_user``, and the request-scoped session is closed before the
    # response body is streamed. Nothing below may touch the ORM instance.
    user_id = current_user.id
    # 扣费记在这一天，退款也回到这一天（跨 06:00 换日后仍要退对行）。
    quota_date = today_cn()

    _ensure_ai_quota(db, current_user)
    try:
        context = _build_ask_context(db, payload.article_id, question)
    except Exception:
        # 扣费已完成但上下文没建起来，问题不能算数。
        _refund_ai_quota(user_id, quota_date)
        raise

    used_sources = "AI 回答基于公开信息整理，涉及具体办理请以官方来源为准。"
    try:
        stream = iter(stream_ask(question, context=context))
        first_chunk = next(stream)
    except StopIteration:
        _refund_ai_quota(user_id, quota_date)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI 未返回有效回答")
    except AIClientError as exc:
        logger.warning("Ark AI stream request failed: %s", exc)
        fallback = _local_answer(db, question)
        if fallback is None:
            fallback = AiAnswerResponse(
                answer="外部 AI 服务暂时不可用。你可以先根据页面中的文章和来源继续阅读，稍后再试。",
                sources="见闻本地应急回复",
            )
        # The fallback is a local rule-based answer, so record that provenance
        # instead of claiming an AI-generated answer.
        used_sources = fallback.sources or "见闻本地应急回复（规则兜底，非 AI 生成）"
        # The first chunk is already assigned below; keep the iterator empty
        # so the fallback is not emitted twice.
        stream = iter(())
        first_chunk = fallback.answer

    def generate():
        # Only values captured above are used here: ``db`` is closed and
        # ``current_user`` is detached by the time this runs.
        chunks: list[str] = [first_chunk]
        saved = False
        # The request-scoped session from Depends(get_db) is closed before the
        # response body is streamed, so the generator owns its own session.
        try:
            yield first_chunk
            try:
                for text in stream:
                    chunks.append(text)
                    yield text
            except AIClientError as exc:
                logger.warning("Ark AI stream interrupted: %s", exc)
            answer = "".join(chunks).strip()
            if answer:
                _record_stream_usage(user_id, question, answer, used_sources)
                saved = True
        finally:
            # Runs even when the client disconnects (GeneratorExit), so a
            # partial answer still counts against the daily quota.
            if not saved:
                answer = "".join(chunks).strip()
                if answer:
                    _record_stream_usage(user_id, question, answer, used_sources)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
