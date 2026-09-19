from __future__ import annotations

from datetime import date, datetime, time, timedelta
import json
import logging
import re
import threading
import time as time_module
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.content import ContentArticle, DailyArticleSet
from services.ai import AIClientError, ask as ask_ai


logger = logging.getLogger(__name__)

DAILY_ARTICLE_COUNT = 5
CONTENT_TIMEZONE = ZoneInfo("Asia/Shanghai")
CONTENT_ROLLOVER_HOUR = 6
AI_ARTICLE_ID_PREFIX = "ai-daily"
DEFAULT_IMAGE_BY_CATEGORY = {
    "党和国家": "/static/images/党和国家.png",
    "时政大事": "/static/images/政策解读.png",
    "民生政策": "/static/images/社会民生.png",
    "青年就业": "/static/images/就业.png",
    "科技产业": "/static/images/AI技术.png",
    "城市生活": "/static/images/社会民生.png",
}
DEFAULT_CATEGORIES = list(DEFAULT_IMAGE_BY_CATEGORY)
_scheduler_stop_event = threading.Event()
_scheduler_thread: threading.Thread | None = None


def get_content_datetime(now: datetime | None = None) -> datetime:
    current = now or datetime.now(CONTENT_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=CONTENT_TIMEZONE)
    else:
        current = current.astimezone(CONTENT_TIMEZONE)
    return current


def get_content_date(now: datetime | None = None) -> date:
    current = get_content_datetime(now)
    if current.time() < time(CONTENT_ROLLOVER_HOUR, 0):
        return (current - timedelta(days=1)).date()
    return current.date()


def ensure_daily_articles(db: Session, content_date: date | None = None) -> list[ContentArticle]:
    selected_date = content_date or get_content_date()
    articles = _daily_articles_for_date(db, selected_date)
    if len(articles) >= DAILY_ARTICLE_COUNT:
        return articles[:DAILY_ARTICLE_COUNT]

    db.query(DailyArticleSet).filter(DailyArticleSet.content_date == selected_date).delete()
    db.flush()

    articles = _generate_ai_articles(db, selected_date)
    if len(articles) < DAILY_ARTICLE_COUNT:
        logger.warning("AI daily articles unavailable or incomplete; using fallback pool")
        articles = _fallback_articles(db, selected_date)

    for position, article in enumerate(articles[:DAILY_ARTICLE_COUNT], start=1):
        db.add(DailyArticleSet(content_date=selected_date, article_id=article.article_id, position=position))
    db.commit()
    return _daily_articles_for_date(db, selected_date)


def scheduled_daily_article_refresh() -> None:
    with SessionLocal() as db:
        ensure_daily_articles(db, get_content_date())


def start_daily_article_scheduler() -> None:
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return

    _scheduler_stop_event.clear()
    _scheduler_thread = threading.Thread(target=_daily_article_scheduler_loop, name="daily-article-scheduler", daemon=True)
    _scheduler_thread.start()


def stop_daily_article_scheduler() -> None:
    _scheduler_stop_event.set()


def _daily_article_scheduler_loop() -> None:
    while not _scheduler_stop_event.is_set():
        wait_seconds = max(1, (_next_rollover_datetime() - get_content_datetime()).total_seconds())
        if _scheduler_stop_event.wait(wait_seconds):
            break
        try:
            scheduled_daily_article_refresh()
        except Exception:
            logger.exception("Scheduled daily article refresh failed")
        time_module.sleep(1)


def _next_rollover_datetime(now: datetime | None = None) -> datetime:
    current = get_content_datetime(now)
    rollover = current.replace(hour=CONTENT_ROLLOVER_HOUR, minute=0, second=0, microsecond=0)
    if current >= rollover:
        rollover = rollover + timedelta(days=1)
    return rollover


def _daily_articles_for_date(db: Session, content_date: date) -> list[ContentArticle]:
    rows = (
        db.query(DailyArticleSet)
        .filter(DailyArticleSet.content_date == content_date)
        .order_by(DailyArticleSet.position, DailyArticleSet.id)
        .all()
    )
    return [row.article for row in rows if row.article is not None]


def _fallback_articles(db: Session, content_date: date) -> list[ContentArticle]:
    candidates = (
        db.query(ContentArticle)
        .filter(ContentArticle.is_today.is_(True))
        .order_by(ContentArticle.today_order, ContentArticle.sort_order, ContentArticle.id)
        .all()
    )
    if not candidates:
        return []

    offset = int(content_date.strftime("%Y%m%d")) % len(candidates)
    return [candidates[(offset + index) % len(candidates)] for index in range(min(DAILY_ARTICLE_COUNT, len(candidates)))]


def _generate_ai_articles(db: Session, content_date: date) -> list[ContentArticle]:
    try:
        result = ask_ai(_daily_article_prompt(content_date), context=_daily_article_context(db), max_tokens=3500)
    except TypeError:
        result = ask_ai(_daily_article_prompt(content_date), context=_daily_article_context(db))
    except AIClientError as exc:
        logger.warning("AI daily article generation failed: %s", exc)
        return []

    try:
        payload = _extract_json_payload(result.text)
    except ValueError as exc:
        logger.warning("AI daily article payload invalid: %s", exc)
        return []

    records = payload.get("articles") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        return []

    articles: list[ContentArticle] = []
    for position, raw in enumerate(records[:DAILY_ARTICLE_COUNT], start=1):
        if not isinstance(raw, dict):
            continue
        article = _upsert_ai_article(db, content_date, position, raw)
        if article is not None:
            articles.append(article)

    db.flush()
    return articles


def _upsert_ai_article(db: Session, content_date: date, position: int, raw: dict) -> ContentArticle | None:
    title = _clean_text(raw.get("title"), 120)
    desc = _clean_text(raw.get("desc") or raw.get("description"), 220)
    if not title or not desc:
        return None

    category = _normalize_category(raw.get("category"))
    article_id = f"{AI_ARTICLE_ID_PREFIX}-{content_date.strftime('%Y%m%d')}-{position}"
    article = db.query(ContentArticle).filter(ContentArticle.article_id == article_id).first()
    if article is None:
        article = ContentArticle(article_id=article_id)

    article.category = category
    article.topic = _clean_text(raw.get("topic"), 64) or category
    article.title = title
    article.desc = desc
    article.sources = _clean_text(raw.get("sources"), 255) or "AI辅助生成 / 公开信息线索"
    article.read_time = _clean_text(raw.get("read_time"), 32) or "4分钟"
    article.image = _clean_text(raw.get("image"), 255) or DEFAULT_IMAGE_BY_CATEGORY.get(category, "/static/images/政策解读.png")
    article.relation = _clean_text(raw.get("relation"), 255) or "普通读者 / 政策关注者"
    article.summary = _clean_string_list(raw.get("summary"), 3) or [desc]
    article.sections = _clean_sections(raw.get("sections")) or [{"heading": "今日要点", "body": desc}]
    article.references = _clean_references(raw.get("references")) or [
        {"title": "公开信息线索", "org": "AI辅助整理", "date": content_date.isoformat(), "url": "https://www.gov.cn/"}
    ]
    article.is_today = True
    article.is_latest = True
    article.today_order = position
    article.sort_order = 1000 + position
    db.add(article)
    return article


def _daily_article_context(db: Session) -> dict[str, object]:
    categories = sorted({row[0] for row in db.query(ContentArticle.category).filter(ContentArticle.category.is_not(None)).all() if row[0]})
    recent_titles = [
        row[0]
        for row in (
            db.query(ContentArticle.title)
            .filter(ContentArticle.is_today.is_(True))
            .order_by(ContentArticle.today_order, ContentArticle.sort_order, ContentArticle.id)
            .limit(20)
            .all()
        )
    ]
    return {
        "existing_categories": categories or DEFAULT_CATEGORIES,
        "recent_titles": recent_titles,
        "output_rule": "Return strict JSON only. Do not add markdown fences.",
    }


def _daily_article_prompt(content_date: date) -> str:
    return f"""
请为“见闻”APP生成 {content_date.isoformat()} 的今日清单文章，必须正好 5 篇。

范围：党和国家、时政大事、民生政策、青年就业、科技产业、城市生活。
要求：
1. 使用克制、清楚的中文，不要编造具体实时新闻细节。
2. 每篇文章用于公共信息学习和政策理解，避免法律、医疗、投资等专业结论。
3. 只返回 JSON，不要 markdown，不要解释。
4. JSON 结构必须是：
{{
  "articles": [
    {{
      "category": "党和国家",
      "topic": "党和国家",
      "title": "标题",
      "desc": "一句话说明",
      "sources": "中国政府网 / 新华网",
      "read_time": "4分钟",
      "relation": "普通读者 / 政策关注者",
      "summary": ["要点1", "要点2", "要点3"],
      "sections": [
        {{"heading": "小标题1", "body": "正文要点"}},
        {{"heading": "小标题2", "body": "正文要点"}},
        {{"heading": "小标题3", "body": "正文要点"}}
      ],
      "references": [
        {{"title": "参考入口", "org": "机构", "date": "公开发布", "url": "https://www.gov.cn/"}}
      ]
    }}
  ]
}}
""".strip()


def _extract_json_payload(text: str) -> dict | list:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start_candidates = [index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0]
        if not start_candidates:
            raise ValueError("missing JSON object")
        start = min(start_candidates)
        end = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if end <= start:
            raise ValueError("incomplete JSON object")
        return json.loads(cleaned[start : end + 1])


def _clean_text(value: object, max_length: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text[:max_length]


def _normalize_category(value: object) -> str:
    text = _clean_text(value, 64)
    return text if text in DEFAULT_IMAGE_BY_CATEGORY else "时政大事"


def _clean_string_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = _clean_text(item, 120)
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _clean_sections(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    sections = []
    for item in value[:4]:
        if not isinstance(item, dict):
            continue
        heading = _clean_text(item.get("heading"), 80)
        body = _clean_text(item.get("body"), 500)
        if heading or body:
            sections.append({"heading": heading or "要点", "body": body})
    return sections


def _clean_references(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    references = []
    for item in value[:3]:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), 120)
        org = _clean_text(item.get("org"), 80)
        url = _clean_text(item.get("url"), 255)
        if title or org:
            references.append(
                {
                    "title": title or "参考入口",
                    "org": org or "公开来源",
                    "date": _clean_text(item.get("date"), 40) or "公开发布",
                    "url": url if url.startswith(("http://", "https://")) else "https://www.gov.cn/",
                }
            )
    return references
