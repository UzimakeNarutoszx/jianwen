from datetime import date, datetime, time, timedelta
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.core.config import settings
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
from app.models.user import User
from app.services.daily_articles import ensure_daily_articles, get_content_date
from app.schemas.content import (
    AiAnswerRequest,
    AiAnswerResponse,
    AjinChatRequest,
    AiPromptResponse,
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
)
from services.ai import AIClientError, ask as ask_ai, ask_ajin, stream_ask


router = APIRouter()
logger = logging.getLogger(__name__)


def _as_list(value: list | None) -> list:
    return value if isinstance(value, list) else []


def _article_list_response(article: ContentArticle, viewed_article_ids: set[str] | None = None) -> ContentArticleListResponse:
    viewed_ids = viewed_article_ids or set()
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
    content_date = get_content_date()
    ensure_daily_articles(db)
    rows = (
        db.query(ContentArticle, DailyArticleSet.position)
        .join(DailyArticleSet, DailyArticleSet.article_id == ContentArticle.article_id)
        .filter(DailyArticleSet.content_date == content_date)
        .order_by(DailyArticleSet.position, ContentArticle.sort_order, ContentArticle.id)
        .limit(5)
        .all()
    )
    articles: list[ContentArticle] = []
    for article, position in rows:
        setattr(article, "_daily_position", position)
        articles.append(article)
    return articles


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


def _today_checklist_response(
    articles: list[ContentArticle],
    viewed_ids: set[str] | None = None,
) -> TodayChecklistResponse:
    viewed_article_ids = viewed_ids or set()
    items = [_article_list_response(article, viewed_article_ids) for article in articles]
    read_count = sum(1 for item in items if item.viewed)
    return TodayChecklistResponse(
        articles=items,
        total_count=len(items),
        read_count=read_count,
        is_complete=bool(items) and read_count == len(items),
    )


def _article_context(article: ContentArticle) -> str:
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

    return "\n".join(
        part
        for part in [
            f"文章ID：{article.article_id}",
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


def _today_usage_window() -> tuple[datetime, datetime]:
    start = datetime.combine(date.today(), time.min)
    return start, start + timedelta(days=1)


def _ensure_ai_quota(db: Session, user: User) -> None:
    start, end = _today_usage_window()
    used_count = (
        db.query(UserAiUsageRecord)
        .filter(
            UserAiUsageRecord.user_id == user.id,
            UserAiUsageRecord.created_at >= start,
            UserAiUsageRecord.created_at < end,
        )
        .count()
    )
    if used_count >= settings.AI_DAILY_QUESTION_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"今日 AI 提问额度已用完，每日最多 {settings.AI_DAILY_QUESTION_LIMIT} 个问题",
        )


def _save_ai_usage(db: Session, user: User, question: str, answer: str, sources: str | None) -> None:
    db.add(UserAiUsageRecord(user_id=user.id, question=question, answer=answer, sources=sources))
    db.commit()


def _build_ask_context(db: Session, article_id: str | None = None) -> dict[str, object]:
    articles = db.query(ContentArticle).order_by(ContentArticle.sort_order, ContentArticle.id).all()
    linked_article = next((article for article in articles if article.article_id == article_id), None)
    context: dict[str, object] = {
        "全站文章资料库": [_article_context(article) for article in articles],
    }
    if linked_article is not None:
        context["当前关联文章"] = _article_context(linked_article)
    return context


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
    return _today_checklist_response(sorted_articles, viewed_ids)


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


@router.get("/discover", response_model=DiscoverContentResponse)
def get_discover_content(db: Session = Depends(get_db)) -> DiscoverContentResponse:
    topics = list_categories(db)
    features = db.query(ContentFeature).order_by(ContentFeature.sort_order, ContentFeature.id).all()
    updates = (
        db.query(ContentArticle)
        .filter(ContentArticle.is_latest.is_(True))
        .order_by(ContentArticle.sort_order, ContentArticle.id)
        .limit(10)
        .all()
    )
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
        selected_date = date.today()

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

    try:
        result = ask_ai(question, context=_build_ask_context(db, payload.article_id))
    except AIClientError as exc:
        logger.warning("Ark AI request failed: %s", exc)
        fallback = _local_answer(db, question)
        if fallback is None:
            fallback = AiAnswerResponse(
                answer="外部 AI 服务暂时不可用。你可以先根据页面中的文章和来源继续阅读，稍后再试。",
                sources="见闻本地应急回复",
            )
        _save_ai_usage(db, current_user, question, fallback.answer, fallback.sources)
        return fallback

    if not result.text:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI 未返回有效回答")

    sources = "AI 回答基于公开信息整理，涉及具体办理请以官方来源为准。"
    _save_ai_usage(db, current_user, question, result.text, sources)
    return AiAnswerResponse(
        answer=result.text,
        sources=sources,
    )


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
    try:
        result = ask_ajin(question, history=payload.history)
    except AIClientError as exc:
        logger.warning("Ajin AI request failed: %s", exc)
        fallback = _ajin_fallback_answer(question)
        _save_ai_usage(db, current_user, question, fallback.answer, fallback.sources)
        return fallback

    if not result.text:
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

    _ensure_ai_quota(db, current_user)
    context = _build_ask_context(db, payload.article_id)

    try:
        stream = iter(stream_ask(question, context=context))
        first_chunk = next(stream)
    except StopIteration:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI 未返回有效回答")
    except AIClientError as exc:
        logger.warning("Ark AI stream request failed: %s", exc)
        fallback = _local_answer(db, question)
        if fallback is None:
            fallback = AiAnswerResponse(
                answer="外部 AI 服务暂时不可用。你可以先根据页面中的文章和来源继续阅读，稍后再试。",
                sources="见闻本地应急回复",
            )
        # The first chunk is already assigned below; keep the iterator empty
        # so the fallback is not emitted twice.
        stream = iter(())
        first_chunk = fallback.answer

    def generate():
        chunks: list[str] = [first_chunk]
        used_sources = "AI 回答基于公开信息整理，涉及具体办理请以官方来源为准。"
        yield first_chunk
        try:
            for text in stream:
                chunks.append(text)
                yield text
        except AIClientError as exc:
            logger.warning("Ark AI stream interrupted: %s", exc)
        answer = "".join(chunks).strip()
        if answer:
            _save_ai_usage(db, current_user, question, answer, used_sources)

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
