from __future__ import annotations

from datetime import date, datetime, time, timedelta
from html import unescape
import json
import logging
import re
import threading
import urllib.error
import urllib.request
import ssl
from zoneinfo import ZoneInfo

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.content import ContentArticle, DailyArticleSet
from app.services.breaking_news import scheduled_breaking_news_refresh
from app.services.seed_content import CATEGORIES
from services.ai import AIClientError, ask as ask_ai


logger = logging.getLogger(__name__)

DAILY_ARTICLE_COUNT = 5
CONTENT_TIMEZONE = ZoneInfo("Asia/Shanghai")
CONTENT_ROLLOVER_HOUR = 6
AI_ARTICLE_ID_PREFIX = "ai-daily"
MIN_SECTION_LENGTH = 160
IDEAL_SECTION_LENGTH = 210
MAX_SECTION_LENGTH = 300
ARTICLE_SECTION_COUNT = 3
SOURCE_TIMEOUT_SECONDS = 10
SCHEDULER_POLL_SECONDS = 60
# 同一内容日期最多尝试生成 3 次，失败后不再无限重试（否则每 5 分钟打一次源站和 AI）。
DAILY_REFRESH_MAX_ATTEMPTS = 3
# 重大会议抓取不需要每分钟一次，按小时节流即可。
BREAKING_NEWS_REFRESH_MINUTES = 60
SOURCE_LIST_URLS = (
    "https://www.gov.cn/yaowen/liebiao/YAOWENLIEBIAO.json",
    "https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json",
)
PROHIBITED_CLICHES = (
    "在时代浪潮中",
    "意义重大",
    "值得我们深思",
    "让我们拭目以待",
    "后续可关注",
)
TRADEOFF_MARKERS = ("但", "不过", "风险", "难点", "成本", "约束", "取决于", "关键在于")
# Daily articles must land in the discover-page channels, otherwise a channel
# filter (/articles?category=…) can never match them.
CHANNEL_CATEGORIES = [name for name, _image, _is_priority in CATEGORIES]
DEFAULT_IMAGE_BY_CATEGORY = {
    "党和国家": "/static/images/党和国家.jpg",
    "共产党": "/static/images/共产党.jpg",
    "时政大事": "/static/images/政策解读.jpg",
    "就业": "/static/images/就业.jpg",
    "住房": "/static/images/住房.jpg",
    "科技": "/static/images/科技产业.jpg",
    "医保": "/static/images/医保社保.jpg",
    "消费": "/static/images/消费补贴.jpg",
    "城市生活": "/static/images/公共生活.jpg",
}
# AI output from older prompts still carries the retired six-category names.
CATEGORY_ALIASES = {
    "青年就业": "就业",
    "科技产业": "科技",
    "AI技术": "科技",
}
# Retired names whose keyword pass found nothing fall back to a channel.
CATEGORY_FALLBACKS = {
    "民生政策": "城市生活",
}
KEYWORD_CATEGORY_RULES = (
    ("住房", ("住房", "房贷", "公积金", "租房")),
    ("医保", ("医保", "医疗", "社保", "养老", "药")),
    ("消费", ("消费", "补贴", "以旧换新", "价格")),
    ("就业", ("就业", "招聘", "毕业生", "岗位")),
    ("共产党", ("党建", "党员", "党章")),
)
DEFAULT_CATEGORY = "时政大事"
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


def read_daily_articles(db: Session, content_date: date | None = None) -> list[ContentArticle]:
    """Read today's article set without ever generating content.

    Request handlers must stay read-only: a missing set falls back to the most
    recent published day and finally to the local seed pool. Generation (source
    fetching + AI calls) is triggered only by the scheduler thread.
    """
    selected_date = content_date or get_content_date()
    articles = _daily_articles_for_date(db, selected_date)
    if articles:
        return articles[:DAILY_ARTICLE_COUNT]
    latest_articles = _latest_available_articles(db, selected_date)
    if latest_articles:
        return latest_articles[:DAILY_ARTICLE_COUNT]
    return _fallback_articles(db, selected_date)


def ensure_daily_articles(db: Session, content_date: date | None = None) -> list[ContentArticle]:
    """Backwards-compatible read-only entry point used by request handlers."""
    return read_daily_articles(db, content_date)


def generate_daily_articles(
    db: Session, content_date: date | None = None, *, retry_fallback: bool = False
) -> list[ContentArticle]:
    """Generate and persist the article set for one content date.

    Only the scheduler thread should call this. Failures roll back so a partly
    written set is never mixed with the fallback pool in one commit.
    """
    selected_date = content_date or get_content_date()
    articles = _daily_articles_for_date(db, selected_date)
    if len(articles) >= DAILY_ARTICLE_COUNT and (
        not retry_fallback or all(_stored_article_is_valid(a, selected_date) for a in articles)
    ):
        return articles[:DAILY_ARTICLE_COUNT]
    try:
        articles = _generate_ai_articles(db, selected_date)
    except Exception:
        logger.exception("AI daily article generation raised for %s", selected_date)
        articles = []

    if len(articles) < DAILY_ARTICLE_COUNT:
        # Always roll back the generation attempt: a half-upserted AI set must
        # never be committed together with the fallback pool.
        db.rollback()
        existing_articles = _daily_articles_for_date(db, selected_date)
        if len(existing_articles) >= DAILY_ARTICLE_COUNT:
            return existing_articles[:DAILY_ARTICLE_COUNT]
        logger.warning("AI daily articles unavailable or incomplete; using fallback pool")
        articles = _fallback_articles(db, selected_date)

    try:
        _replace_daily_set(db, selected_date, articles[:DAILY_ARTICLE_COUNT])
    except IntegrityError:
        # A concurrent writer already stored this date; re-read instead of 500.
        db.rollback()
        logger.warning("Daily article set for %s conflicted with a concurrent write", selected_date)
        return _daily_articles_for_date(db, selected_date)[:DAILY_ARTICLE_COUNT]
    except Exception:
        db.rollback()
        logger.exception("Storing daily article set failed for %s", selected_date)
        return _daily_articles_for_date(db, selected_date)[:DAILY_ARTICLE_COUNT]
    return _daily_articles_for_date(db, selected_date)


def _replace_daily_set(db: Session, content_date: date, articles: list[ContentArticle]) -> None:
    db.query(DailyArticleSet).filter(DailyArticleSet.content_date == content_date).delete()
    db.flush()
    for position, article in enumerate(articles, start=1):
        db.add(DailyArticleSet(content_date=content_date, article_id=article.article_id, position=position))
    db.commit()


def _latest_available_articles(db: Session, content_date: date) -> list[ContentArticle]:
    latest_date = (
        db.query(DailyArticleSet.content_date)
        .filter(DailyArticleSet.content_date < content_date)
        .order_by(DailyArticleSet.content_date.desc())
        .first()
    )
    if latest_date is None:
        return []
    return _daily_articles_for_date(db, latest_date[0])


def scheduled_daily_article_refresh() -> bool:
    with SessionLocal() as db:
        selected_date = get_content_date()
        articles = generate_daily_articles(db, selected_date, retry_fallback=True)
        return len(articles) == DAILY_ARTICLE_COUNT and all(
            _stored_article_is_valid(article, selected_date) for article in articles
        )


def daily_set_is_complete(content_date: date) -> bool:
    """当日已经存下一整组文章时不再重抓，避免白天中途把当天文章换掉。"""
    try:
        with SessionLocal() as db:
            return len(_daily_articles_for_date(db, content_date)) >= DAILY_ARTICLE_COUNT
    except Exception:
        # 查不出来就当作没存好，让正常的生成流程去处理。
        logger.exception("Failed to check the daily article set for %s", content_date)
        return False


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
    # Polling also recovers from reloads, sleep/wake, and a missed exact 06:00
    # wake-up. A failed refresh is retried only a bounded number of times:
    # an unbounded retry would hit the sources and the AI every poll and could
    # still replace the article set in the middle of the day.
    processed_date: date | None = None
    attempts = 0
    last_breaking_news_at: datetime | None = None
    while not _scheduler_stop_event.is_set():
        # 重大会议置顶跟随同一次轮询刷新，但按小时节流；它自己兜住所有异常，
        # 抓取失败不会影响每日文章。
        now = get_content_datetime()
        if last_breaking_news_at is None or now - last_breaking_news_at >= timedelta(
            minutes=BREAKING_NEWS_REFRESH_MINUTES
        ):
            scheduled_breaking_news_refresh(now)
            last_breaking_news_at = now
        current_date = get_content_date()
        if current_date != processed_date:
            if daily_set_is_complete(current_date):
                # 当天已经存好一整组：不再重抓，否则白天中途可能把当日文章换掉。
                processed_date = current_date
                attempts = 0
                continue
            if attempts >= DAILY_REFRESH_MAX_ATTEMPTS:
                # 已经试满 3 次：放掉当天，等下一个内容日期再试。
                processed_date = current_date
                attempts = 0
                continue
            attempts += 1
            try:
                complete = scheduled_daily_article_refresh()
            except Exception:
                logger.exception("Scheduled daily article refresh failed for %s", current_date)
                complete = False
            if complete:
                processed_date = current_date
                attempts = 0
                continue
            if attempts >= DAILY_REFRESH_MAX_ATTEMPTS:
                logger.warning(
                    "Giving up daily article refresh for %s after %s attempt(s)",
                    current_date,
                    attempts,
                )
                processed_date = current_date
                attempts = 0
                continue
            if _scheduler_stop_event.wait(SCHEDULER_POLL_SECONDS * 5):
                break
            continue

        wait_seconds = min(
            SCHEDULER_POLL_SECONDS,
            max(1, (_next_rollover_datetime() - get_content_datetime()).total_seconds()),
        )
        if _scheduler_stop_event.wait(wait_seconds):
            break


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
    articles: list[ContentArticle] = []
    for row in rows:
        if row.article is None:
            continue
        setattr(row.article, "_daily_position", row.position)
        articles.append(row.article)
    return articles


def _fallback_articles(db: Session, content_date: date) -> list[ContentArticle]:
    candidates = (
        db.query(ContentArticle)
        .filter(ContentArticle.is_today.is_(True))
        .order_by(ContentArticle.today_order, ContentArticle.sort_order, ContentArticle.id)
        .all()
    )
    valid_candidates = [article for article in candidates if _stored_article_is_valid(article, content_date)]
    # Keep the local seed content available when the external AI/source refresh
    # is temporarily unavailable. It is still explicitly marked as today's content.
    candidates = valid_candidates or candidates
    if not candidates:
        return []

    offset = int(content_date.strftime("%Y%m%d")) % len(candidates)
    return [candidates[(offset + index) % len(candidates)] for index in range(min(DAILY_ARTICLE_COUNT, len(candidates)))]


def _generate_ai_articles(db: Session, content_date: date) -> list[ContentArticle]:
    materials = _fetch_recent_policy_materials(content_date)
    if not materials:
        logger.warning("No official materials found for %s or the previous day", content_date)
        return []

    context = _daily_article_context(db)
    context["official_materials"] = materials
    allowed_sources = {item["url"]: item for item in materials}

    for attempt in range(2):
        prompt = _daily_article_prompt(content_date)
        if attempt:
            prompt += "\n\n上一次输出未通过硬性校验。请逐篇检查：正好 5 篇、每篇正好 3 段正文、每段以 190–210 字为最佳，至少 160 字且绝不能超过 300 字、至少点出一个现实难点或风险，且引用只能来自给定素材。"
        try:
            result = ask_ai(prompt, context=context, max_tokens=10000)
        except TypeError:
            result = ask_ai(prompt, context=context)
        except AIClientError as exc:
            logger.warning("AI daily article generation failed: %s", exc)
            return []

        try:
            payload = _extract_json_payload(result.text)
        except ValueError as exc:
            logger.warning("AI daily article payload invalid: %s", exc)
            continue

        records = payload.get("articles") if isinstance(payload, dict) else payload
        if not isinstance(records, list) or len(records) != DAILY_ARTICLE_COUNT:
            logger.warning("AI daily article count invalid: expected %s", DAILY_ARTICLE_COUNT)
            continue

        if not _article_set_is_valid(records, allowed_sources):
            logger.warning("AI daily article payload failed content validation")
            continue

        articles: list[ContentArticle] = []
        for position, raw in enumerate(records, start=1):
            article = _upsert_ai_article(db, content_date, position, raw)
            if article is not None:
                articles.append(article)
        if len(articles) == DAILY_ARTICLE_COUNT:
            db.flush()
            return articles

    return []


def _upsert_ai_article(db: Session, content_date: date, position: int, raw: dict) -> ContentArticle | None:
    title = _clean_text(raw.get("title"), 120)
    desc = _clean_text(raw.get("desc") or raw.get("description"), 220)
    if not title or not desc:
        return None

    category = _normalize_category(raw.get("category"), title, desc)
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
    article.image = _clean_text(raw.get("image"), 255) or DEFAULT_IMAGE_BY_CATEGORY.get(
        category, "/static/images/政策解读.jpg"
    )
    article.relation = _clean_text(raw.get("relation"), 255) or "普通读者 / 政策关注者"
    article.summary = _clean_string_list(raw.get("summary"), 3) or [desc]
    article.sections = _clean_sections(raw.get("sections"))
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
    stored_categories = {
        row[0]
        for row in db.query(ContentArticle.category).filter(ContentArticle.category.is_not(None)).all()
        if row[0]
    }
    categories = [name for name in CHANNEL_CATEGORIES if name in stored_categories]
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
        "existing_categories": categories or CHANNEL_CATEGORIES,
        "recent_titles": recent_titles,
        "output_rule": "Return strict JSON only. Do not add markdown fences.",
    }


def _daily_article_prompt(content_date: date) -> str:
    previous_date = content_date - timedelta(days=1)
    channel_list = "、".join(CHANNEL_CATEGORIES)
    return f"""
请为“见闻”APP生成 {content_date.isoformat()} 的今日清单文章，必须正好 5 篇。

范围：{channel_list}。
分类规则：category 字段必须从上句列出的 {len(CHANNEL_CATEGORIES)} 个频道中原样选一个，逐字照抄，不得自造、缩写、改写或使用其他分类名；尽量让 5 篇分布在不同频道。
素材边界：
1. 只能使用 context.official_materials 中的事实，素材发布日期必须是 {content_date.isoformat()} 或 {previous_date.isoformat()}。
2. 不得用常识补写素材中没有的数字、人名、地点、政策条款或因果结论。references 的 title、date、url 必须与给定素材一致。

写作硬性标准：
1. 每篇正好 3 个 sections，每个 body 只写一个完整段落。每段去掉空白后以 190–210 个可见字符为最佳，硬性范围是 160–300 个可见字符；超过 300 会被程序直接拒绝。
2. 不要停在“政策说了什么”，而要回答“它要解决什么矛盾、执行时卡在哪里、普通人如何判断效果”。把素材中已确认的事实与你的分析分开；分析可以做有条件的推理，但不得把推理写成已发生的事实。
3. 第一段讲清核心事实和真正的问题：不只列数字，还要说明政策针对的现实痛点，哪些是已公布安排，哪些仍未明确。
4. 第二段拆解执行机制和利益关系：根据素材，至少从资金来源、成本分担、责任主体、受益与承担者、后续运维、地方执行差异中选两项分析。素材有具体城市或项目就用来验证；没有就不得自编案例。
5. 第三段做平衡判断：既说可能改善什么，也至少点出一个可能的代价、风险或受损群体，再给出 2–3 个可验证的判断标准，例如资金落实、实际完工率、维护成本、居民参与或受益差异。最后一句必须给出该篇自己的明确判断，不得只说“后续可关注”。
6. 普通人优先：少用政策术语，必须使用时立即用白话解释；句子尽量短，每句只表达一层意思。不默认读者了解政策背景。
7. 不得写“在时代浪潮中”“意义重大”“值得我们深思”“让我们拭目以待”“后续可关注”等套话，不得用空洞排比、口号或无信息量的结尾。
8. relation 是“影响范围”，只列 2–4 个与该篇事件直接相关的人群或领域，用 / 分隔，不得套用“普通读者 / 政策关注者”。
9. sections.heading 同时构成“阅读路线”，必须根据该篇文章的具体内容写成 6–14 个字的动作型小标题，不得五篇雷同。
10. summary 只写 3 条简洁事实，每条 18–40 字；desc 为 35–70 字的事实摘要。
11. 使用克制、清楚的中文，用于公共信息学习和政策理解，避免法律、医疗、投资等专业结论。
12. 只返回 JSON，不要 markdown，不要解释。JSON 结构必须是：
{{
  "articles": [
    {{
      "category": "党和国家",
      "topic": "党和国家",
      "title": "标题",
      "desc": "一句话说明",
      "sources": "中国政府网 / 新华网",
      "read_time": "4分钟",
      "relation": "受影响人群1 / 受影响领域2",
      "summary": ["简洁事实1", "简洁事实2", "简洁事实3"],
      "sections": [
        {{"heading": "看清事实与问题", "body": "190–210字、最多300字的单段正文"}},
        {{"heading": "拆解执行与利益", "body": "190–210字、最多300字的单段正文"}},
        {{"heading": "权衡收益与风险", "body": "190–210字、最多300字的单段正文"}}
      ],
      "references": [
        {{"title": "必须与素材标题一致", "org": "中国政府网", "date": "{content_date.isoformat()}", "url": "必须与素材URL一致"}}
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


def _normalize_category(value: object, title: object = None, desc: object = None) -> str:
    """Map any stored/AI category name onto one of the discover channels.

    ``title``/``desc`` are used to re-classify retired categories and unknown
    values by keyword; without them those fall back to a channel guess.
    """
    text = _clean_text(value, 64)
    if text in CHANNEL_CATEGORIES:
        return text
    alias = CATEGORY_ALIASES.get(text)
    if alias is not None:
        return alias
    haystack = f"{_clean_text(title, 120)} {_clean_text(desc, 220)}"
    for category, keywords in KEYWORD_CATEGORY_RULES:
        if any(keyword in haystack for keyword in keywords):
            return category
    return CATEGORY_FALLBACKS.get(text, DEFAULT_CATEGORY)


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
    for item in value[:ARTICLE_SECTION_COUNT]:
        if not isinstance(item, dict):
            continue
        heading = _clean_text(item.get("heading"), 80)
        body = _clean_text(item.get("body"), 1200)
        if heading or body:
            sections.append({"heading": heading or "要点", "body": body})
    return sections


def _article_payload_is_valid(raw: object, allowed_sources: dict[str, dict[str, str]]) -> bool:
    if not isinstance(raw, dict):
        return False
    if not _clean_text(raw.get("title"), 120) or not _clean_text(raw.get("desc") or raw.get("description"), 220):
        return False
    serialized = json.dumps(raw, ensure_ascii=False)
    if any(phrase in serialized for phrase in PROHIBITED_CLICHES):
        return False

    relation_parts = [part.strip() for part in _clean_text(raw.get("relation"), 255).split("/") if part.strip()]
    if not 2 <= len(relation_parts) <= 4:
        return False

    summary = _clean_string_list(raw.get("summary"), 3)
    if len(summary) != 3:
        return False

    sections = _clean_sections(raw.get("sections"))
    if len(sections) != ARTICLE_SECTION_COUNT:
        return False
    for section in sections:
        paragraphs = [part.strip() for part in re.split(r"\n+", section["body"]) if part.strip()]
        if len(paragraphs) != 1:
            return False
        character_count = _section_character_count(paragraphs[0])
        if not MIN_SECTION_LENGTH <= character_count <= MAX_SECTION_LENGTH:
            return False

    analytical_text = "".join(section["body"] for section in sections[1:])
    if not any(marker in analytical_text for marker in TRADEOFF_MARKERS):
        return False

    references = raw.get("references")
    if not isinstance(references, list) or not references:
        return False
    for reference in references:
        if not isinstance(reference, dict):
            return False
        material = allowed_sources.get(_clean_text(reference.get("url"), 500))
        if material is None:
            return False
        if _clean_text(reference.get("date"), 40) != material["date"]:
            return False
        if _clean_text(reference.get("title"), 200) != material["title"]:
            return False
    return True


def _article_set_is_valid(records: list[object], allowed_sources: dict[str, dict[str, str]]) -> bool:
    if not all(_article_payload_is_valid(raw, allowed_sources) for raw in records):
        return False
    typed_records = [raw for raw in records if isinstance(raw, dict)]
    titles = [_clean_text(raw.get("title"), 120) for raw in typed_records]
    relations = [_clean_text(raw.get("relation"), 255) for raw in typed_records]
    reading_routes = [
        tuple(section["heading"] for section in _clean_sections(raw.get("sections")))
        for raw in typed_records
    ]
    return len(set(titles)) == len(records) and len(set(relations)) == len(records) and len(set(reading_routes)) == len(records)


def _stored_article_is_valid(article: ContentArticle, content_date: date) -> bool:
    sections = _clean_sections(article.sections)
    if len(sections) != ARTICLE_SECTION_COUNT:
        return False
    if any(
        not MIN_SECTION_LENGTH <= _section_character_count(section["body"]) <= MAX_SECTION_LENGTH
        for section in sections
    ):
        return False
    allowed_dates = {content_date.isoformat(), (content_date - timedelta(days=1)).isoformat()}
    references = article.references if isinstance(article.references, list) else []
    return bool(references) and all(
        isinstance(reference, dict)
        and _clean_text(reference.get("date"), 40) in allowed_dates
        and _clean_text(reference.get("url"), 500).startswith("https://www.gov.cn/")
        for reference in references
    )


def _chinese_character_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))


def _section_character_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _fetch_recent_policy_materials(content_date: date) -> list[dict[str, str]]:
    allowed_dates = {content_date.isoformat(), (content_date - timedelta(days=1)).isoformat()}
    entries: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for list_url in SOURCE_LIST_URLS:
        try:
            request = urllib.request.Request(list_url, headers={"User-Agent": "Jianwen/1.0"})
            context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=context)
            ) if context else urllib.request.build_opener()
            with opener.open(request, timeout=SOURCE_TIMEOUT_SECONDS) as response:
                records = json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.URLError) as exc:
            logger.warning("Official material list unavailable (%s): %s", list_url, exc)
            continue

        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            published = _clean_text(record.get("DOCRELPUBTIME"), 40)
            url = _clean_text(record.get("URL"), 500)
            title = _clean_text(record.get("TITLE"), 200)
            if published not in allowed_dates or not title or not url.startswith("https://www.gov.cn/") or url in seen_urls:
                continue
            seen_urls.add(url)
            entries.append({"title": title, "date": published, "url": url, "excerpt": ""})

    materials = entries[:12]
    for material in materials:
        material["excerpt"] = _fetch_official_excerpt(material["url"])
    return materials


def _fetch_official_excerpt(url: str) -> str:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Jianwen/1.0"})
        context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context)
        ) if context else urllib.request.build_opener()
        with opener.open(request, timeout=SOURCE_TIMEOUT_SECONDS) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except (OSError, urllib.error.URLError) as exc:
        logger.warning("Official material page unavailable (%s): %s", url, exc)
        return ""

    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL)
    cleaned: list[str] = []
    for paragraph in paragraphs:
        text = unescape(re.sub(r"<[^>]+>", "", paragraph))
        text = re.sub(r"\s+", " ", text).strip()
        if _chinese_character_count(text) >= 20:
            cleaned.append(text)
        if sum(len(item) for item in cleaned) >= 3000:
            break
    return "\n".join(cleaned)[:3500]


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
