from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import re
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.content import ContentArticle, ContentCategory, ClassicBook, ClassicBookChapter
from app.models.profile import UserAiUsageRecord, UserBrowsingHistory, UserReadingPosition
from app.models.reading import ArticleReadingDay, ReadingBatch, ReadingInterval
from app.models.user import User
from app.schemas.weekly import ReadingActivityRequest

BEIJING = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc


def utc_naive(value):
    return value.astimezone(UTC).replace(tzinfo=None)


def record_activity(db: Session, user: User, payload: ReadingActivityRequest):
    start, end = utc_naive(payload.started_at), utc_naive(payload.ended_at)
    now = datetime.now(UTC).replace(tzinfo=None)
    if end > now + timedelta(seconds=5) or start < now - timedelta(days=7):
        raise HTTPException(422, "阅读时间超出允许范围，请校准设备时间")
    # Serialize all tabs/devices for this user, including the initial empty ledger.
    db.query(User).filter(User.id == user.id).with_for_update().populate_existing().one()
    # Locking reads also bypass MySQL repeatable-read snapshots from authentication.
    if db.query(ReadingBatch.id).filter_by(user_id=user.id, batch_id=payload.batch_id).with_for_update().first():
        return {"accepted_seconds": 0, "duplicate": True}
    if payload.kind == "article":
        content = db.query(ContentArticle).filter_by(article_id=payload.content_id).first()
        book = None
    else:
        try:
            chapter_id = int(payload.content_id)
        except ValueError:
            raise HTTPException(422, "章节编号无效")
        if not 0 < chapter_id <= 2147483647:
            raise HTTPException(422, "章节编号无效")
        content = db.query(ClassicBookChapter).filter_by(id=chapter_id, book_id=payload.book_id).first()
        book = db.query(ClassicBook).filter_by(book_id=payload.book_id).first()
    if content is None or (payload.kind == "classic" and book is None):
        raise HTTPException(404, "阅读内容不存在")
    remaining = [(start, end)]
    overlaps = db.query(ReadingInterval).filter(
        ReadingInterval.user_id == user.id, ReadingInterval.started_at < end, ReadingInterval.ended_at > start
    ).with_for_update().all()
    for previous in overlaps:
        pieces = []
        for left, right in remaining:
            if previous.ended_at <= left or previous.started_at >= right:
                pieces.append((left, right))
            else:
                if left < previous.started_at:
                    pieces.append((left, previous.started_at))
                if right > previous.ended_at:
                    pieces.append((previous.ended_at, right))
        remaining = pieces
    db.add(ReadingBatch(user_id=user.id, batch_id=payload.batch_id))
    total = 0
    for left, right in remaining:
        # Midnight boundaries belong to the user's report timezone, never host time.
        while left < right:
            day = left.replace(tzinfo=UTC).astimezone(BEIJING).date()
            midnight = utc_naive(datetime.combine(day + timedelta(days=1), time.min, BEIJING))
            stop = min(right, midnight)
            db.add(ReadingInterval(
                user_id=user.id, kind=payload.kind, content_id=payload.content_id,
                book_id=payload.book_id if book else None, title=content.title,
                book_title=book.title if book else None,
                topic=(content.category or content.topic or "其他") if not book else None,
                scroll_progress=payload.scroll_progress, started_at=left, ended_at=stop,
            ))
            total += (stop - left).total_seconds()
            left = stop
    db.commit()
    return {"accepted_seconds": round(total, 3), "duplicate": False}


def build_report(db: Session, user: User, week_start: date | None = None):
    today = datetime.now(BEIJING).date()
    current_monday = today - timedelta(days=today.weekday())
    monday = week_start or current_monday
    if monday.weekday() != 0 or monday > current_monday or monday.year < 2000:
        raise HTTPException(422, "请选择不晚于本周的周一日期")
    end_day = monday + timedelta(days=7)
    start = utc_naive(datetime.combine(monday, time.min, BEIJING))
    end = utc_naive(datetime.combine(end_day, time.min, BEIJING))
    rows = db.query(ReadingInterval).filter(
        ReadingInterval.user_id == user.id, ReadingInterval.started_at >= start, ReadingInterval.started_at < end
    ).order_by(ReadingInterval.started_at, ReadingInterval.id).all()
    days = [{"date": (monday + timedelta(days=i)).isoformat(), "articles": 0, "chapters": 0,
             "ask": 0, "ajin": 0, "reading_seconds": 0, "cumulative_seconds": 0} for i in range(7)]
    daily, weekly = {}, {}
    for row in rows:
        day = row.started_at.replace(tzinfo=UTC).astimezone(BEIJING).date().isoformat()
        key = (row.kind, row.content_id)
        item = weekly.setdefault(key, {"kind": row.kind, "content_id": row.content_id, "book_id": row.book_id,
            "title": row.title, "book_title": row.book_title, "topic": row.topic, "seconds": 0,
            "scroll_progress": 0, "dates": []})
        seconds = (row.ended_at - row.started_at).total_seconds()
        item["seconds"] += seconds
        item["scroll_progress"] = row.scroll_progress  # latest recorded position, not completion
        if day not in item["dates"]:
            item["dates"].append(day)
        daily[(day, *key)] = daily.get((day, *key), 0) + seconds
    article_days = set()
    for (day, kind, content_id), seconds in daily.items():
        stat = days[(date.fromisoformat(day) - monday).days]
        stat["reading_seconds"] += seconds
        if kind == "article":
            article_days.add((day, content_id))
        elif round(seconds, 6) >= 30:
            stat["chapters"] += 1
    # A week can reach 30 seconds over several days even when no single day does.
    qualified = [item for item in weekly.values() if item["kind"] == "article" or round(item["seconds"], 6) >= 30]
    articles = [item for item in qualified if item["kind"] == "article"]
    classics = [item for item in qualified if item["kind"] == "classic"]
    for item in qualified:
        item["seconds"] = round(item["seconds"], 3)
    # Existing naive legacy timestamps were written in the backend's local timezone.
    # Convert Beijing boundaries to that same host zone when querying legacy records.
    local_start = datetime.combine(monday, time.min, BEIJING).astimezone().replace(tzinfo=None)
    local_end = datetime.combine(end_day, time.min, BEIJING).astimezone().replace(tzinfo=None)
    questions = []
    records = db.query(UserAiUsageRecord).filter(UserAiUsageRecord.user_id == user.id,
        UserAiUsageRecord.created_at >= local_start, UserAiUsageRecord.created_at < local_end
    ).order_by(UserAiUsageRecord.created_at, UserAiUsageRecord.id).all()
    for row in records:
        stamp = row.created_at.astimezone(BEIJING)
        channel = "ajin" if re.search(r"阿烬|ajin", row.sources or "", re.I) else "ask"
        questions.append({"id": row.id, "question": row.question, "channel": channel, "created_at": stamp.isoformat()})
        days[(stamp.date() - monday).days][channel] += 1
    legacy_articles = db.query(UserBrowsingHistory).filter(UserBrowsingHistory.user_id == user.id,
        UserBrowsingHistory.visited_at >= local_start, UserBrowsingHistory.visited_at < local_end).all()
    # Merge existing history and the durable per-day ledger into ordinary article reads.
    # Old history has no duration; it contributes a count without inventing reading time.
    article_map = {item["content_id"]: item for item in articles}
    daily_reads = db.query(ArticleReadingDay).filter(
        ArticleReadingDay.user_id == user.id, ArticleReadingDay.content_date >= monday,
        ArticleReadingDay.content_date < end_day).order_by(ArticleReadingDay.content_date, ArticleReadingDay.id).all()
    read_sources = [(r.article_id, r.title, r.topic, r.content_date.isoformat()) for r in daily_reads]
    read_sources += [(r.article_id, r.title, r.topic, r.visited_at.astimezone(BEIJING).date().isoformat()) for r in legacy_articles]
    for article_id, title, topic, day in read_sources:
        item = article_map.setdefault(article_id, {"kind": "article", "content_id": article_id,
            "title": title or article_id, "topic": topic or "其他", "seconds": 0, "dates": []})
        if day not in item["dates"]:
            item["dates"].append(day)
        article_days.add((day, article_id))
    articles = list(article_map.values())
    for item in articles:
        item["dates"].sort()
    for day, article_id in article_days:
        days[(date.fromisoformat(day) - monday).days]["articles"] += 1
    legacy = []
    positions = db.query(UserReadingPosition, ClassicBook.title, ClassicBookChapter.title).join(
        ClassicBook, ClassicBook.book_id == UserReadingPosition.book_id).join(
        ClassicBookChapter, ClassicBookChapter.id == UserReadingPosition.chapter_id).filter(
        UserReadingPosition.user_id == user.id, UserReadingPosition.updated_at >= local_start,
        UserReadingPosition.updated_at < local_end).all()
    known_chapters = {r.content_id for r in rows if r.kind == "classic"}
    for position, book_title, title in positions:
        if str(position.chapter_id) not in known_chapters:
            legacy.append({"kind": "classic", "title": title, "book_title": book_title,
                "content_id": str(position.chapter_id), "book_id": position.book_id,
                "scroll_progress": position.scroll_progress, "date": position.updated_at.astimezone(BEIJING).isoformat()})
    counts = Counter(item["topic"] or "其他" for item in articles)
    categories = [r.name for r in db.query(ContentCategory).order_by(ContentCategory.sort_order, ContentCategory.id).all()]
    # Fixed site taxonomy; uncategorized/deleted categories share one final axis.
    categories = [name for name in dict.fromkeys(categories) if name != "其他"] + ["其他"]
    topics = [{"name": name, "count": counts.get(name, 0)} for name in categories]
    topics[-1]["count"] += sum(value for name, value in counts.items() if name not in categories)
    cumulative = 0
    for stat in days:
        cumulative += stat["reading_seconds"]
        stat["reading_seconds"] = round(stat["reading_seconds"], 3)
        stat["cumulative_seconds"] = round(cumulative, 3)
    first = db.query(ReadingInterval).filter_by(user_id=user.id).order_by(ReadingInterval.started_at).first()
    from app.services.issue_threads import weekly_issues
    return {"user": {"id": user.id, "nickname": user.nickname}, "timezone": "Asia/Shanghai",
        "week_start": monday.isoformat(), "week_end": (end_day - timedelta(days=1)).isoformat(),
        "current_week_start": current_monday.isoformat(), "is_current": monday == current_monday,
        "tracking_since": first.started_at.replace(tzinfo=UTC).astimezone(BEIJING).date().isoformat() if first else None,
        "summary": {"articles": len(articles), "chapters": len(classics), "books": len({i["book_id"] for i in classics}),
            "ask": sum(d["ask"] for d in days), "ajin": sum(d["ajin"] for d in days),
            "reading_seconds": round(cumulative, 3),
            "active_days": sum(bool(d["articles"] or d["chapters"] or d["reading_seconds"] or d["ask"] or d["ajin"]) for d in days)},
        "days": days, "topics": topics, "articles": articles, "classics": classics,
        "questions": questions, "legacy": legacy, "issues": weekly_issues(db, user.id, start, end)}
