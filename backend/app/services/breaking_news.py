"""Deterministic national-conference reporting; no AI or user-request network I/O."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
import logging
import re
import ssl
import urllib.request
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import certifi
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.breaking_news import BreakingNews, BreakingNewsSync

logger = logging.getLogger(__name__)
TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_IMAGE = "/static/images/共产党.png"
# Use live index pages rather than obsolete RSS endpoints.
SOURCE_FEEDS = (
    ("中国政府网", "https://www.gov.cn/yaowen/liebiao/YAOWENLIEBIAO.json", "json"),
    ("新华社", "https://www.news.cn/politics/", "html"),
    ("人民日报", "https://www.people.com.cn/", "html"),
)
# Official event notices may leave the rolling home-page indexes before the event
# starts. Keep confirmed, stable article URLs as a small fallback index until the
# source exposes a searchable feed.
SOURCE_ARTICLE_FALLBACKS = (
    ("新华社", "https://www.news.cn/politics/20260921/f4717ffcaca041aca87806099ec0138e/c.html", "决定中国共产党第二十届中央委员会第五次全体会议于10月26日至29日在北京召开"),
    ("人民日报", "https://paper.people.com.cn/rmrb/pc/content/202609/22/content_30182375.html", "中国共产党第二十届中央委员会第五次全体会议于10月26日至29日在北京召开"),
)
DOMAINS = {"中国政府网": ("gov.cn",), "新华社": ("news.cn", "xinhuanet.com"), "人民日报": ("people.com.cn", "people.cn")}
NUM = r"[一二三四五六七八九十百零〇0-9]+"
IDENTITIES = (
    ("中央全会", rf"(?:中国共产党)?(?:第)?({NUM})届(?:中国共产党)?(?:中央委员会|中央)?(?:第)?({NUM})次?全(?:体)?会议?"),
    ("全国人代会", rf"(?:第)?({NUM})届全国人民代表大会(?:第)?({NUM})次会议"),
    ("全国党代会", rf"中国共产党第({NUM})次全国代表大会"),
    ("全国政协会议", rf"(?:中国人民政治协商会议)?(?:第)?({NUM})届全国(?:政协|委员会)(?:第)?({NUM})次会议"),
    ("中央政治局会议", r"(?:中共中央|中央)政治局会议"),
    ("中央经济工作会议", r"中央经济工作会议"),
    ("中央农村工作会议", r"中央农村工作会议"),
)


def local_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(TZ)
    return current.replace(tzinfo=TZ) if current.tzinfo is None else current.astimezone(TZ)


def allowed_url(source: str, url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and not parsed.username and parsed.port in (None, 443) and any(
        host == domain or host.endswith("." + domain) for domain in DOMAINS.get(source, ()))


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, source):
        self.source = source

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(self.source, newurl):
            raise ValueError("redirect outside source whitelist")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(source: str, url: str) -> str:
    if not allowed_url(source, url):
        raise ValueError("URL outside source whitelist")
    opener = urllib.request.build_opener(SafeRedirect(source), urllib.request.HTTPSHandler(
        context=ssl.create_default_context(cafile=certifi.where())))
    with opener.open(urllib.request.Request(url, headers={"User-Agent": "Jianwen/1.0"}), timeout=settings.BREAKING_NEWS_TIMEOUT_SECONDS) as response:
        data = response.read(3_000_001)
        if len(data) > 3_000_000:
            raise ValueError("source response too large")
        charset = response.headers.get_content_charset()
        if not charset:
            match = re.search(rb"charset=[\"']?([a-zA-Z0-9-]+)", data[:4096], re.I)
            charset = match.group(1).decode() if match else "utf-8"
        return data.decode(charset, errors="replace")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.meta, self.paragraphs = [], {}, []
        self.anchor, self.paragraph, self.skip = None, None, 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "meta":
            self.meta[(values.get("name") or values.get("property") or "").lower()] = values.get("content", "")
        if tag == "a":
            self.anchor = [values.get("href", ""), []]
        if tag == "p":
            self.paragraph = []

    def handle_data(self, data):
        if self.skip:
            return
        if self.anchor is not None:
            self.anchor[1].append(data)
        if self.paragraph is not None:
            self.paragraph.append(data)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag == "a" and self.anchor is not None:
            self.links.append((self.anchor[0], clean("".join(self.anchor[1]))))
            self.anchor = None
        if tag == "p" and self.paragraph is not None:
            self.paragraphs.append(clean("".join(self.paragraph)))
            self.paragraph = None


def clean(value) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def parse_time(value) -> datetime | None:
    match = re.search(r"(20[0-9]{2})[-/年]?([01][0-9])[-/月]?([0-3][0-9])(?:[T 日]+([0-2][0-9]):([0-5][0-9])(?::([0-5][0-9]))?)?", str(value or ""))
    if not match:
        return None
    try:
        return datetime(*[int(v or 0) for v in match.groups()], tzinfo=TZ)
    except ValueError:
        return None


def identity(title: str, published: datetime):
    normalized = re.sub(r"\s+", "", title).replace("五中全会", "五次全体会议").replace("四中全会", "四次全体会议").replace("三中全会", "三次全体会议").replace("六中全会", "六次全体会议").replace("七中全会", "七次全体会议").replace("二中全会", "二次全体会议")
    shorthand = re.search(rf"({NUM})中全会", re.sub(r"\s+", "", title))
    if shorthand:
        return "中央全会", hashlib.sha256(("中央全会:" + str(published.year) + ":" + shorthand.group(1)).encode()).hexdigest()[:32]
    for kind, pattern in IDENTITIES:
        match = re.search(pattern, normalized)
        if not match:
            continue
        # Recurring unnumbered conferences require an explicit day to avoid merging
        # two different meetings in the same year. Numbered sessions have stable IDs.
        discriminator = f"{published.year}:{match.group(2)}" if kind == "中央全会" else ("-".join(match.groups()) or published.date().isoformat())
        return kind, hashlib.sha256((kind + ":" + discriminator).encode()).hexdigest()[:32]
    return None


def parse_index(source: str, url: str, kind: str, text: str) -> list[dict]:
    if kind == "json":
        raw = json.loads(text)
        if not isinstance(raw, list):
            raise ValueError("invalid index JSON")
        return [{"source": source, "title": clean(r.get("TITLE")), "url": r.get("URL", ""), "date": r.get("DOCRELPUBTIME", "")} for r in raw if isinstance(r, dict)]
    parser = PageParser()
    parser.feed(text)
    output = []
    for href, title in parser.links:
        link = urljoin(url, href)
        # Several official pages emit http links; fetch the same official path over TLS.
        if link.startswith("http://"):
            link = "https://" + link[7:]
        published = parse_time(link)
        if title and published and allowed_url(source, link):
            output.append({"source": source, "title": title, "url": link, "date": published.isoformat()})
    return output


def parse_article(record: dict, text: str) -> dict | None:
    parser = PageParser()
    parser.feed(text)
    published = next((value for value in (parse_time(parser.meta.get(key)) for key in (
        "publishdate", "pubdate", "publish_date", "article:published_time", "date")) if value), None) or parse_time(record["date"])
    # Some newspaper templates carry stale metadata; prefer the date encoded in
    # the official URL when it is newer and plausible.
    url_date = parse_time(record.get("url", ""))
    if url_date and (published is None or published.year < 2020):
        published = url_date
    if not published:
        return None
    event = identity(record["title"], published)
    if not event:
        return None
    paragraphs = [p for p in parser.paragraphs if len(p) >= 35 and not any(s in p for s in ("版权所有", "责任编辑", "互联网新闻信息服务"))]
    # Extract actual source text, never infer facts or substitute a navigation title.
    excerpt = next((p for p in paragraphs if identity(p, published) == event), None)
    if not excerpt:
        return None
    return {**record, "published_at": published.isoformat(), "summary": excerpt[:600], "event_type": event[0], "event_key": event[1]}


def fetch_source_items(now: datetime | None = None) -> list[dict]:
    current = local_now(now)
    records, failures = [], []
    enabled = settings.BREAKING_NEWS_SOURCES.split(",")
    for source, url, kind in SOURCE_FEEDS:
        if source not in enabled:
            continue
        try:
            entries = parse_index(source, url, kind, _fetch(source, url))
            seen = set()
            candidates = []
            for item in entries:
                published = parse_time(item["date"])
                if item["url"] in seen or not allowed_url(source, item["url"]) or not published:
                    continue
                seen.add(item["url"])
                if not current - timedelta(days=7) <= published <= current or not identity(item["title"], published):
                    continue
                candidates.append(item)
            for item in candidates[:12]:
                try:
                    article = parse_article(item, _fetch(source, item["url"]))
                    if article:
                        records.append(article)
                except (OSError, ValueError) as exc:
                    failures.append(source + ": article unavailable")
                    logger.warning("Breaking-news article unavailable (%s): %s", item["url"], exc)
        except (OSError, ValueError) as exc:
            failures.append(source + ": index unavailable")
            logger.warning("Breaking-news index unavailable (%s): %s", source, exc)
    for source, article_url, title in SOURCE_ARTICLE_FALLBACKS:
        if source not in enabled:
            continue
        try:
            article = parse_article({"source": source, "title": title, "url": article_url, "date": ""}, _fetch(source, article_url))
            if article and article["url"] not in {item.get("url") for item in records}:
                records.append(article)
        except (OSError, ValueError) as exc:
            logger.warning("Breaking-news fallback unavailable (%s): %s", article_url, exc)
    if failures:
        logger.warning("Breaking-news partial fetch: %s", "; ".join(failures))
    return records


def ongoing_until(sources: list[dict], now: datetime) -> datetime | None:
    # Only an explicit, currently valid conference date range can extend the pin.
    # '召开' by itself is not evidence that a meeting remains underway.
    ends = []
    for source in sources:
        text = source.get("summary", "")
        for match in re.finditer(r"([0-9]{1,2})月([0-9]{1,2})日(?:至|到)[ ]*(?:([0-9]{1,2})月)?([0-9]{1,2})日", text):
            month, day, end_month, end_day = [int(v) if v else None for v in match.groups()]
            try:
                start = datetime(now.year, month, day, tzinfo=TZ)
                end = datetime(now.year, end_month or month, end_day, 23, 59, 59, tzinfo=TZ)
                if start <= now + timedelta(hours=72) <= end + timedelta(hours=72) and (end - start).days <= 30:
                    ends.append(end.replace(tzinfo=None))
            except ValueError:
                continue
    return max(ends) if ends else None


def refresh_breaking_news(db: Session, now: datetime | None = None, records: list[dict] | None = None) -> int:
    current = local_now(now)
    incoming = fetch_source_items(current) if records is None else records
    grouped = {}
    for item in incoming:
        published = parse_time(item.get("published_at"))
        source, url = item.get("source"), item.get("url", "")
        event = identity(item.get("title", ""), published) if published else None
        if not event or not allowed_url(source, url) or not item.get("summary") or not current - timedelta(days=180) <= published <= current:
            continue
        grouped.setdefault(event[1], []).append({**item, "event_type": event[0]})
    count = 0
    for key, items in grouped.items():
        row = db.query(BreakingNews).filter_by(event_key=key).first()
        previous = (row.sources or []) if row else []
        by_source = {}
        for item in previous + [{"name": i["source"], "title": i["title"], "url": i["url"], "summary": i["summary"], "published_at": i["published_at"]} for i in items]:
            published = parse_time(item.get("published_at"))
            if not published or published < current - timedelta(days=180):
                continue
            name = item["name"]
            if name not in by_source or published > parse_time(by_source[name]["published_at"]):
                by_source[name] = item
        sources = sorted(by_source.values(), key=lambda s: s["published_at"], reverse=True)
        if len(sources) < 2:
            continue
        latest = max(parse_time(s["published_at"]) for s in sources).replace(tzinfo=None)
        if row is None:
            row = BreakingNews(event_key=key, first_confirmed_at=current.replace(tzinfo=None))
            db.add(row)
        row.title, row.event_type = items[0]["title"], items[0]["event_type"]
        row.sources = sources
        row.summary = "\n\n".join(s["name"] + "：" + s["summary"] for s in sources)
        row.latest_reported_at, row.image = latest, DEFAULT_IMAGE
        row.ongoing_until = ongoing_until(sources, current)
        row.is_ongoing = row.ongoing_until is not None
        row.is_visible = True
        count += 1
    db.commit()
    logger.info("Breaking-news refresh finished: %s confirmed events", count)
    return count


def active_breaking_news(db: Session, now: datetime | None = None) -> list[BreakingNews]:
    current = local_now(now).replace(tzinfo=None)
    return db.query(BreakingNews).filter(BreakingNews.is_visible.is_(True), or_(
        BreakingNews.latest_reported_at >= current - timedelta(hours=settings.BREAKING_NEWS_RETENTION_HOURS),
        BreakingNews.ongoing_until >= current,
    )).order_by(BreakingNews.latest_reported_at.desc(), BreakingNews.id.desc()).all()


def scheduled_refresh(content_date: date) -> None:
    """Durable daily claim: reloads don't duplicate successful runs; failures retry."""
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        now = local_now().replace(tzinfo=None)
        job = db.query(BreakingNewsSync).filter_by(content_date=content_date).first()
        if job is None:
            try:
                db.add(BreakingNewsSync(content_date=content_date, status="pending"))
                db.commit()
            except IntegrityError:
                db.rollback()
        eligible = and_(BreakingNewsSync.content_date == content_date, BreakingNewsSync.status != "completed",
            or_(BreakingNewsSync.lease_until.is_(None), BreakingNewsSync.lease_until <= now))
        lease = (now + timedelta(minutes=15)).replace(microsecond=0)
        claimed = db.query(BreakingNewsSync).filter(eligible).update({"status": "running", "lease_until": lease}, synchronize_session=False)
        db.commit()
        if not claimed:
            return
        try:
            refresh_breaking_news(db)
            db.query(BreakingNewsSync).filter_by(content_date=content_date, lease_until=lease).update(
                {"status": "completed", "last_success_at": now, "error": None, "lease_until": None}, synchronize_session=False)
            db.commit()
        except Exception as exc:
            db.rollback()
            db.query(BreakingNewsSync).filter_by(content_date=content_date, lease_until=lease).update(
                {"status": "failed", "error": str(exc)[:1000], "lease_until": now + timedelta(minutes=5)}, synchronize_session=False)
            db.commit()
            logger.exception("Breaking-news refresh failed; daily articles remain committed")

