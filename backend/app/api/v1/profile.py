from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.content import ClassicBook, ClassicBookChapter, ContentArticle
from app.models.profile import UserAiUsageRecord, UserBrowsingHistory, UserFavoriteArticle, UserFollowTopic, UserReadingPosition
from app.models.user import User
from app.models.reading import ArticleReadingDay, ReadingInterval
from app.services.daily_articles import ensure_daily_articles
from app.schemas.profile import (
    AiUsageRecordRequest,
    AiUsageRecordResponse,
    ArticleRecordRequest,
    BrowsingHistoryResponse,
    FavoriteArticleResponse,
    FollowTopicsRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    ReadingPositionRequest,
    ReadingPositionResponse,
    TodayChecklistItemResponse,
    TodayChecklistResponse,
)
from app.schemas.user import MessageResponse


router = APIRouter()

ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@router.get("/reading-positions/{book_id}", response_model=ReadingPositionResponse | None)
def get_reading_position(
    book_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserReadingPosition | None:
    if db.query(ClassicBook.id).filter(ClassicBook.book_id == book_id).first() is None:
        raise HTTPException(status_code=404, detail="经典文献不存在")
    return db.query(UserReadingPosition).filter(
        UserReadingPosition.user_id == current_user.id, UserReadingPosition.book_id == book_id
    ).first()


@router.put("/reading-positions/{book_id}", response_model=ReadingPositionResponse)
def save_reading_position(
    book_id: str,
    payload: ReadingPositionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserReadingPosition:
    chapter = db.query(ClassicBookChapter.id).filter(
        ClassicBookChapter.book_id == book_id, ClassicBookChapter.id == payload.chapter_id
    ).first()
    if chapter is None:
        raise HTTPException(status_code=404, detail="当前文献中不存在该章节")
    record = db.query(UserReadingPosition).filter(
        UserReadingPosition.user_id == current_user.id, UserReadingPosition.book_id == book_id
    ).first()
    if record is None:
        record = UserReadingPosition(user_id=current_user.id, book_id=book_id)
    record.chapter_id = payload.chapter_id
    record.scroll_progress = payload.scroll_progress
    record.updated_at = datetime.now()
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _profile_response(db: Session, user: User) -> ProfileResponse:
    followed_topics = [
        row.topic
        for row in (
            db.query(UserFollowTopic)
            .filter(UserFollowTopic.user_id == user.id)
            .order_by(UserFollowTopic.sort_order, UserFollowTopic.id)
            .all()
        )
    ]
    return ProfileResponse(
        id=user.id,
        phone=user.phone,
        nickname=user.nickname,
        avatar_path=user.avatar_path,
        bio=user.bio,
        favorites_count=db.query(func.count(UserFavoriteArticle.id)).filter(UserFavoriteArticle.user_id == user.id).scalar() or 0,
        history_count=db.query(func.count(UserBrowsingHistory.id)).filter(UserBrowsingHistory.user_id == user.id).scalar() or 0,
        ai_records_count=db.query(func.count(UserAiUsageRecord.id)).filter(UserAiUsageRecord.user_id == user.id).scalar() or 0,
        followed_topics=followed_topics,
        created_at=user.created_at,
    )


def _apply_article_payload(record: UserFavoriteArticle | UserBrowsingHistory, payload: ArticleRecordRequest, db: Session) -> None:
    article = db.query(ContentArticle).filter(ContentArticle.article_id == payload.article_id).first()
    for field in ("topic", "title", "desc", "sources", "read_time"):
        value = getattr(payload, field)
        if value is None and article is not None:
            value = getattr(article, field)
            if field == "topic":
                value = value or article.category
        if value is not None:
            setattr(record, field, value)


def _clean_topics(topics: list[str]) -> list[str]:
    cleaned = []
    for topic in topics:
        value = topic.strip()[:64]
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


def _today_checklist_item(article: ContentArticle, viewed_article_ids: set[str]) -> TodayChecklistItemResponse:
    return TodayChecklistItemResponse(
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
        viewed=article.article_id in viewed_article_ids,
    )


@router.get("/me", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfileResponse:
    return _profile_response(db, current_user)


@router.patch("/me", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    if payload.nickname is not None:
        current_user.nickname = payload.nickname
    if payload.bio is not None:
        current_user.bio = payload.bio

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _profile_response(db, current_user)


@router.get("/topics", response_model=list[str])
def list_follow_topics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    return [
        row.topic
        for row in (
            db.query(UserFollowTopic)
            .filter(UserFollowTopic.user_id == current_user.id)
            .order_by(UserFollowTopic.sort_order, UserFollowTopic.id)
            .all()
        )
    ]


@router.put("/topics", response_model=list[str])
def save_follow_topics(
    payload: FollowTopicsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    topics = _clean_topics(payload.topics)
    db.query(UserFollowTopic).filter(UserFollowTopic.user_id == current_user.id).delete()
    for index, topic in enumerate(topics):
        db.add(UserFollowTopic(user_id=current_user.id, topic=topic, sort_order=index))
    db.commit()
    return topics


@router.get("/today-checklist", response_model=TodayChecklistResponse)
def get_today_checklist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TodayChecklistResponse:
    articles = ensure_daily_articles(db)
    article_ids = [article.article_id for article in articles]
    viewed_article_ids = {
        row.article_id
        for row in (
            db.query(UserBrowsingHistory.article_id)
            .filter(UserBrowsingHistory.user_id == current_user.id, UserBrowsingHistory.article_id.in_(article_ids))
            .all()
        )
    }
    items = [_today_checklist_item(article, viewed_article_ids) for article in articles]
    read_count = sum(1 for item in items if item.viewed)
    return TodayChecklistResponse(
        articles=items,
        total_count=len(items),
        read_count=read_count,
        is_complete=bool(items) and read_count == len(items),
    )


@router.post("/me/avatar", response_model=ProfileResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="头像仅支持 jpg、png、webp 格式")
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传图片文件")

    avatar_dir = Path(settings.UPLOAD_DIR) / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"user_{current_user.id}_{uuid4().hex}{extension}"
    avatar_file = avatar_dir / filename

    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="头像大小不能超过 2MB")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="头像文件不能为空")

    avatar_file.write_bytes(content)
    current_user.avatar_path = f"/uploads/avatars/{filename}"
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _profile_response(db, current_user)


@router.get("/favorites", response_model=list[FavoriteArticleResponse])
def list_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserFavoriteArticle]:
    return (
        db.query(UserFavoriteArticle)
        .filter(UserFavoriteArticle.user_id == current_user.id)
        .order_by(desc(UserFavoriteArticle.created_at))
        .all()
    )


@router.get("/favorites/{article_id}", response_model=FavoriteArticleResponse | None)
def get_favorite_status(
    article_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserFavoriteArticle | None:
    return (
        db.query(UserFavoriteArticle)
        .filter(UserFavoriteArticle.user_id == current_user.id, UserFavoriteArticle.article_id == article_id)
        .first()
    )


@router.post("/favorites", response_model=FavoriteArticleResponse, status_code=status.HTTP_201_CREATED)
def save_favorite(
    payload: ArticleRecordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserFavoriteArticle:
    record = (
        db.query(UserFavoriteArticle)
        .filter(UserFavoriteArticle.user_id == current_user.id, UserFavoriteArticle.article_id == payload.article_id)
        .first()
    )
    if record is None:
        record = UserFavoriteArticle(user_id=current_user.id, article_id=payload.article_id)
    _apply_article_payload(record, payload, db)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/favorites/{article_id}", response_model=MessageResponse)
def delete_favorite(
    article_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    record = (
        db.query(UserFavoriteArticle)
        .filter(UserFavoriteArticle.user_id == current_user.id, UserFavoriteArticle.article_id == article_id)
        .first()
    )
    if record:
        db.delete(record)
        db.commit()
    return MessageResponse(message="收藏已取消")


@router.get("/history", response_model=list[BrowsingHistoryResponse])
def list_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserBrowsingHistory]:
    return (
        db.query(UserBrowsingHistory)
        .filter(UserBrowsingHistory.user_id == current_user.id)
        .order_by(desc(UserBrowsingHistory.visited_at))
        .limit(80)
        .all()
    )


@router.post("/history", response_model=BrowsingHistoryResponse, status_code=status.HTTP_201_CREATED)
def save_history(
    payload: ArticleRecordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserBrowsingHistory:
    db.query(User).filter(User.id == current_user.id).with_for_update().one()
    record = (
        db.query(UserBrowsingHistory)
        .filter(UserBrowsingHistory.user_id == current_user.id, UserBrowsingHistory.article_id == payload.article_id)
        .with_for_update().first()
    )
    if record is None:
        record = UserBrowsingHistory(user_id=current_user.id, article_id=payload.article_id)
    _apply_article_payload(record, payload, db)
    record.visited_at = datetime.now()
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    daily = db.query(ArticleReadingDay).filter_by(
        user_id=current_user.id, article_id=payload.article_id, content_date=day
    ).with_for_update().first()
    if daily is None:
        daily = ArticleReadingDay(user_id=current_user.id, article_id=payload.article_id, content_date=day)
    daily.title = record.title or payload.article_id
    daily.topic = record.topic
    db.add(daily)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/history", response_model=MessageResponse)
def clear_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    db.query(User).filter(User.id == current_user.id).with_for_update().one()
    db.query(UserBrowsingHistory).filter(UserBrowsingHistory.user_id == current_user.id).delete()
    db.query(ReadingInterval).filter(ReadingInterval.user_id == current_user.id, ReadingInterval.kind == "article").delete()
    db.query(ArticleReadingDay).filter(ArticleReadingDay.user_id == current_user.id).delete()
    db.commit()
    return MessageResponse(message="浏览记录已清空")


@router.get("/ai-records", response_model=list[AiUsageRecordResponse])
def list_ai_records(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserAiUsageRecord]:
    return (
        db.query(UserAiUsageRecord)
        .filter(UserAiUsageRecord.user_id == current_user.id)
        .order_by(desc(UserAiUsageRecord.created_at))
        .limit(80)
        .all()
    )


@router.post("/ai-records", response_model=AiUsageRecordResponse, status_code=status.HTTP_201_CREATED)
def save_ai_record(
    payload: AiUsageRecordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserAiUsageRecord:
    record = UserAiUsageRecord(
        user_id=current_user.id,
        question=payload.question,
        answer=payload.answer,
        sources=payload.sources,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/ai-records", response_model=MessageResponse)
def clear_ai_records(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    db.query(UserAiUsageRecord).filter(UserAiUsageRecord.user_id == current_user.id).delete()
    db.commit()
    return MessageResponse(message="问问记录已清空")
