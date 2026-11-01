"""重大会议置顶：确定性匹配官方来源，不做 AI 推断，也不在请求里联网。

流程固定为「抓官方索引 → 抓原文 → 标题或正文同时命中会议名和召开日期 → 落库」，
任何一步失败只记日志，不影响每日文章生成。
"""
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

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.breaking_news import BreakingNews


logger = logging.getLogger(__name__)
CONTENT_TIMEZONE = ZoneInfo("Asia/Shanghai")
DEFAULT_IMAGE = "/static/images/共产党.jpg"
STATUS_ONGOING = "进行中"
STATUS_CLOSED = "已闭幕"
MAX_RESPONSE_BYTES = 3_000_000
MAX_ARTICLE_FETCHES = 12
MIN_SUMMARY_LENGTH = 20
MAX_SUMMARY_LENGTH = 300
# 官方只报到开幕日时结束日期未知，按 5 天估算会期（只影响状态与置顶窗口）。
UNKNOWN_END_DAYS = 5

# 官方来源与域名白名单：不在表内的域名一律丢弃。
SOURCE_DOMAINS = {
    "中国政府网": ("gov.cn",),
    "新华社": ("news.cn", "xinhuanet.com"),
    "人民日报": ("people.com.cn", "people.cn"),
}
ALLOWED_DOMAINS = tuple(dict.fromkeys(domain for domains in SOURCE_DOMAINS.values() for domain in domains))
SOURCE_FEEDS = (
    ("中国政府网", "https://www.gov.cn/yaowen/liebiao/YAOWENLIEBIAO.json", "json"),
    ("新华社", "https://www.news.cn/politics/", "html"),
    ("人民日报", "https://www.people.com.cn/", "html"),
)

_NUM = r"[一二三四五六七八九十0-9]+"
# 会议类型与名称识别规则，参考旧版 PATTERNS，按“完整名 → 简称”的顺序匹配。
MEETING_PATTERNS = (
    (
        "中央全会",
        re.compile(rf"(?:中国共产党)?第(?P<term>{_NUM})届(?:中国共产党)?中央委员会第(?P<session>{_NUM})次全体会议"),
    ),
    ("中央全会", re.compile(rf"第?(?P<term>{_NUM})届第?(?P<session>{_NUM})中全会")),
    ("全国党代会", re.compile(rf"中国共产党第(?P<session>{_NUM})次全国代表大会")),
    (
        "全国人代会",
        re.compile(rf"第(?P<term>{_NUM})届全国人民代表大会第(?P<session>{_NUM})次会议"),
    ),
    (
        "全国政协会议",
        re.compile(
            rf"(?:中国人民政治协商会议)?第(?P<term>{_NUM})届全国(?:委员会|政协)(?:第(?P<session>{_NUM})次会议)?"
        ),
    ),
    # 常见写法「全国政协十四届三次会议」把届次放在“全国政协”之后。
    ("全国政协会议", re.compile(rf"全国政协(?:第)?(?P<term>{_NUM})届(?:第)?(?P<session>{_NUM})次?会议")),
    ("中央经济工作会议", re.compile(r"中央经济工作会议")),
    ("中央农村工作会议", re.compile(r"中央农村工作会议")),
)
# 无届次的例会必须带年份，否则不同年份的会议会合并成一张卡片。
YEARLY_EVENT_TYPES = ("中央经济工作会议", "中央农村工作会议")

_DATE_PATTERN = re.compile(r"(?:(?P<year>20\d{2})年)?(?P<month>\d{1,2})月(?P<day>\d{1,2})日")
# 只有“26日”没有月份的写法，后面必须紧跟会议动作才算会议日期。
_DAY_ONLY_PATTERN = re.compile(r"(?<![月\d])(?P<day>\d{1,2})日")
_DAY_ACTION_PATTERN = re.compile(r"\s*(?:上午|下午|晚间|晚上)?\s*(?:在.{0,20}?)?(?:开幕|闭幕|举行|召开|开幕会|闭幕会)")
_RANGE_PATTERN = re.compile(
    r"(?:(?P<year>20\d{2})年)?(?P<start_month>\d{1,2})月(?P<start_day>\d{1,2})日"
    r"\s*(?:至|到|—|–|-|－|~)\s*"
    r"(?:(?:(?P<end_year>20\d{2})年)?(?P<end_month>\d{1,2})月)?(?P<end_day>\d{1,2})日"
)
_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_NUMERALS = "零一二三四五六七八九十"

SEED_EVENT_NAME = "中国共产党第二十届中央委员会第五次全体会议"
SEED_START = date(2026, 10, 26)
SEED_END = date(2026, 10, 29)
SEED_RECORD = {
    "event_name": SEED_EVENT_NAME,
    "event_type": "中央全会",
    "start_date": SEED_START,
    "end_date": SEED_END,
    "title": "二十届五中全会公报发布",
    "summary": "会议于10月26日至29日在北京举行，审议通过关于持之以恒推进全面从严治党的决定。",
    "source_name": "人民日报",
    "source_url": "https://cpc.people.com.cn/n1/2026/1029/c64387-40824095.html",
}


def local_now(now: datetime | None = None) -> datetime:
    """北京时间；库里存的是无时区的时间值，比较时统一换算。"""
    current = now or datetime.now(CONTENT_TIMEZONE)
    if current.tzinfo is None:
        return current.replace(tzinfo=CONTENT_TIMEZONE)
    return current.astimezone(CONTENT_TIMEZONE)


def allowed_url(url: str, source_name: str | None = None) -> bool:
    """只接受白名单域名上的 https 直链；给出来源时还必须是该来源的域名。"""
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.port not in (None, 443):
        return False
    domains = SOURCE_DOMAINS.get(source_name or "", ALLOWED_DOMAINS)
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def event_key(event_name: str, start_date: date) -> str:
    """同一场会议（会议名 + 开始日期）共用一把键，后续报道只更新这张卡片。"""
    payload = f"{event_name}|{start_date.isoformat()}".encode()
    return hashlib.sha256(payload).hexdigest()[:32]


def meeting_status(start_date: date, end_date: date | None, now: datetime) -> str:
    """按北京时间判断：会议最后一天之后即为已闭幕。"""
    return STATUS_CLOSED if local_now(now).date() > last_meeting_day(start_date, end_date) else STATUS_ONGOING


def last_meeting_day(start_date: date, end_date: date | None) -> date:
    """会议最后一天。结束日期未知时用保守估计，只影响状态与置顶窗口。

    只确认到开幕日（或闭幕日）时官方尚未给出会期，这里按 ``UNKNOWN_END_DAYS``
    天估算，避免会议第二天就被判为已闭幕；估算值不会下发给前端。
    """
    return end_date or start_date + timedelta(days=UNKNOWN_END_DAYS)


def pin_deadline(row: BreakingNews) -> date:
    """置顶截止日：会议最后一天 + N 天（含第 N 天当天）。"""
    return last_meeting_day(row.start_date, row.end_date) + timedelta(days=settings.BREAKING_NEWS_PIN_DAYS)


def is_pinned(row: BreakingNews, now: datetime | None = None) -> bool:
    """会议期间一直显示；闭幕后继续显示 N 天，之后不再返回。"""
    return local_now(now).date() <= pin_deadline(row)


def active_breaking_news(db: Session, now: datetime | None = None) -> list[BreakingNews]:
    """当前应置顶的会议，最新的在前。只读，绝不联网。"""
    current = local_now(now)
    visible = [row for row in db.query(BreakingNews).all() if is_pinned(row, current)]
    return sorted(visible, key=lambda row: (row.start_date, row.id), reverse=True)


def card_payload(row: BreakingNews, now: datetime | None = None) -> dict:
    """按当前时间重新判定状态，避免调度线程没跑到时接口返回过期状态。"""
    return {
        "id": row.id,
        "event_name": row.event_name,
        "event_type": row.event_type,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "status": meeting_status(row.start_date, row.end_date, now),
        "title": row.title,
        "summary": row.summary,
        "source_name": row.source_name,
        "source_url": row.source_url,
        "image": row.image,
    }


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _sentence_split(text: str) -> list[str]:
    return [part for part in re.split(r"[。！？；\n]+", text) if part.strip()]


def _cn_to_int(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if "十" in text:
        tens, _, ones = text.partition("十")
        tens_value = _CN_DIGITS.get(tens, 1) if tens else 1
        ones_value = _CN_DIGITS.get(ones, 0) if ones else 0
        return tens_value * 10 + ones_value
    if all(char in _CN_DIGITS for char in text):
        total = 0
        for char in text:
            total = total * 10 + _CN_DIGITS[char]
        return total
    return None


def _int_to_cn(value: int) -> str:
    if value < 10:
        return _CN_NUMERALS[value]
    if value < 20:
        return "十" + (_CN_NUMERALS[value - 10] if value > 10 else "")
    return _CN_NUMERALS[value // 10] + "十" + (_CN_NUMERALS[value % 10] if value % 10 else "")


def _event_name_from_match(event_type: str, match: re.Match[str], reference: date) -> str:
    groups = match.groupdict()
    term = _cn_to_int(groups.get("term") or "")
    session = _cn_to_int(groups.get("session") or "")
    if event_type == "中央全会":
        if term is None or session is None:
            return ""
        return f"中国共产党第{_int_to_cn(term)}届中央委员会第{_int_to_cn(session)}次全体会议"
    if event_type == "全国党代会":
        if session is None:
            return ""
        return f"中国共产党第{_int_to_cn(session)}次全国代表大会"
    if event_type == "全国人代会":
        if term is None or session is None:
            return ""
        return f"第{_int_to_cn(term)}届全国人民代表大会第{_int_to_cn(session)}次会议"
    if event_type == "全国政协会议":
        if term is None:
            return ""
        if session is None:
            return f"中国人民政治协商会议第{_int_to_cn(term)}届全国委员会"
        return f"中国人民政治协商会议第{_int_to_cn(term)}届全国委员会第{_int_to_cn(session)}次会议"
    return f"{reference.year}年{event_type}"


def _find_meeting(text: str, reference: date) -> tuple[str, str] | None:
    """返回 (会议全名, 会议类型)；同一段文字按规则表顺序只认第一个匹配。"""
    for event_type, pattern in MEETING_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        name = _event_name_from_match(event_type, match, reference)
        if name:
            return name, event_type
    return None


def _resolve_date(year: int | None, month: int, day: int, reference: date) -> date | None:
    """年份缺失时取离参考日期最近的一年，避免年末预告被算到上一轮会议。"""
    candidates = [year] if year else [reference.year - 1, reference.year, reference.year + 1]
    best: tuple[int, date] | None = None
    for candidate in candidates:
        try:
            resolved = date(candidate, month, day)
        except ValueError:
            continue
        distance = abs((resolved - reference).days)
        if distance > 200:
            continue
        if best is None or distance < best[0]:
            best = (distance, resolved)
    return best[1] if best else None


def find_date_span(text: str, reference: date) -> tuple[date, date] | None:
    """取“X月X日至X日”这样的明确起止区间；没有该写法时返回 None。"""
    for match in _RANGE_PATTERN.finditer(text):
        groups = match.groupdict()
        start = _resolve_date(
            int(groups["year"]) if groups.get("year") else None,
            int(groups["start_month"]),
            int(groups["start_day"]),
            reference,
        )
        if start is None:
            continue
        end_month = int(groups["end_month"]) if groups.get("end_month") else start.month
        end_year = int(groups["end_year"]) if groups.get("end_year") else start.year
        end = _resolve_date(end_year, end_month, int(groups["end_day"]), start)
        if end is None or end < start or (end - start).days > 31:
            continue
        return start, end
    return None


def find_single_date(text: str, reference: date) -> date | None:
    """只有一个明确日期时才返回它；出现多个日期视为有歧义，不猜。"""
    found = {
        resolved
        for resolved in (
            _resolve_date(
                int(match.group("year")) if match.group("year") else None,
                int(match.group("month")),
                int(match.group("day")),
                reference,
            )
            for match in _DATE_PATTERN.finditer(text)
        )
        if resolved is not None
    }
    return found.pop() if len(found) == 1 else None


def find_day_only_date(text: str, reference: date) -> date | None:
    """正文只写“26日开幕”这类（月份在标题或电头里）时，用报道日期的年月补全。

    只接受“X日”紧跟开幕/闭幕/举行/召开这类动作的写法，且与报道日期相差不超过
    31 天；其他日号一律不当成会议日期。
    """
    days = {
        int(match.group("day"))
        for match in _DAY_ONLY_PATTERN.finditer(text)
        if _DAY_ACTION_PATTERN.match(text, match.end())
    }
    if len(days) != 1:
        return None
    try:
        candidate = date(reference.year, reference.month, days.pop())
    except ValueError:
        return None
    return candidate if abs((candidate - reference).days) <= 31 else None


def confirm_event(text: str, reference: date) -> dict | None:
    """确认条件：同一份官方文字里同时出现会议名和召开日期（开幕或闭幕日）。

    只有“决定召开 / 将于近期召开”这类没有具体日期的预告不算确认；单日确认
    只在同一句里既有会议名又只有一个日期时才成立，避免电头日期造成误判。
    """
    cleaned = _clean(text)
    if not cleaned:
        return None
    meeting = _find_meeting(cleaned, reference)
    if meeting is None:
        return None
    span = find_date_span(cleaned, reference)
    if span is None:
        single = None
        for sentence in _sentence_split(cleaned):
            if _find_meeting(sentence, reference) is None:
                continue
            single = find_single_date(sentence, reference) or find_day_only_date(sentence, reference)
            if single is not None:
                break
        if single is None:
            return None
        # 只知道开幕或闭幕日时，结束日期留空（未知可空）。
        span = (single, None)
    start, end = span
    event_name, event_type = meeting
    if event_type in YEARLY_EVENT_TYPES:
        event_name = f"{start.year}年{event_type}"
    return {"event_name": event_name, "event_type": event_type, "start_date": start, "end_date": end}


class PageParser(HTMLParser):
    """只收集链接、meta 和正文段落，避免把导航文案当成事实。"""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.meta: dict[str, str] = {}
        self.paragraphs: list[str] = []
        self._anchor: list | None = None
        self._paragraph: list[str] | None = None
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag in ("script", "style"):
            self._skip += 1
            return
        if tag == "meta":
            key = (values.get("name") or values.get("property") or "").lower()
            if key:
                self.meta[key] = values.get("content", "")
        elif tag == "a":
            self._anchor = [values.get("href", ""), []]
        elif tag == "p":
            self._paragraph = []

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._anchor is not None:
            self._anchor[1].append(data)
        if self._paragraph is not None:
            self._paragraph.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
            return
        if tag == "a" and self._anchor is not None:
            self.links.append((self._anchor[0], _clean("".join(self._anchor[1]))))
            self._anchor = None
        elif tag == "p" and self._paragraph is not None:
            self.paragraphs.append(_clean("".join(self._paragraph)))
            self._paragraph = None


def parse_time(value: object) -> datetime | None:
    match = re.search(
        r"(20\d{2})[-/年]?(\d{1,2})[-/月]?(\d{1,2})(?:[T 日]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?",
        str(value or ""),
    )
    if not match:
        return None
    try:
        return datetime(*[int(part or 0) for part in match.groups()], tzinfo=CONTENT_TIMEZONE)
    except ValueError:
        return None


def _fetch(source_name: str, url: str) -> str:
    """只在后台线程调用；域名不在白名单内直接拒绝，不做重定向跟随。"""
    if not allowed_url(url, source_name):
        raise ValueError("URL outside the official whitelist")
    context = ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request(url, headers={"User-Agent": "Jianwen/1.0"})
    with opener.open(request, timeout=settings.BREAKING_NEWS_TIMEOUT_SECONDS) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("source response too large")
    charset = "utf-8"
    match = re.search(rb"charset=[\"']?([a-zA-Z0-9_-]+)", data[:4096], re.IGNORECASE)
    if match:
        charset = match.group(1).decode("ascii", errors="ignore") or "utf-8"
    return data.decode(charset, errors="replace")


def parse_index(source_name: str, url: str, kind: str, text: str) -> list[dict[str, str]]:
    """解析官方索引页，产出候选条目；非白名单 URL 在这一层就丢掉。"""
    if kind == "json":
        try:
            raw = json.loads(text)
        except ValueError as exc:
            raise ValueError("invalid index JSON") from exc
        if not isinstance(raw, list):
            raise ValueError("invalid index JSON")
        entries = [
            {
                "source_name": source_name,
                "title": _clean(record.get("TITLE")),
                "url": _clean(record.get("URL")),
                "date": _clean(record.get("DOCRELPUBTIME")),
            }
            for record in raw
            if isinstance(record, dict)
        ]
    else:
        parser = PageParser()
        parser.feed(text)
        entries = [
            {
                "source_name": source_name,
                "title": title,
                "url": urljoin(url, href),
                "date": "",
            }
            for href, title in parser.links
        ]
    results = []
    for entry in entries:
        link = entry["url"]
        # 部分官方索引输出 http 链接，同一路径的 https 才是白名单允许的形态。
        if link.startswith("http://"):
            link = "https://" + link[len("http://"):]
        if not entry["title"] or not allowed_url(link, source_name):
            continue
        entry["url"] = link
        if not entry["date"]:
            published = parse_time(link) or parse_time(entry["title"])
            entry["date"] = published.isoformat() if published else ""
        results.append(entry)
    return results


def parse_article(record: dict[str, str], text: str) -> dict | None:
    """从原文确认会议；摘要只取官方原文中含会议名与日期的那一段。"""
    parser = PageParser()
    parser.feed(text)
    published = parse_time(record.get("date"))
    for key in ("publishdate", "pubdate", "publish_date", "article:published_time", "date"):
        if published is not None:
            break
        published = parse_time(parser.meta.get(key))
    if published is None:
        published = parse_time(record.get("url"))
    reference = published.date() if published else local_now().date()

    confirmed = confirm_event(record.get("title", ""), reference)
    # 短段落也可能就是官方原文的关键一句，因此只过滤模板化尾注，不按长度丢段落。
    paragraphs = [
        paragraph
        for paragraph in parser.paragraphs
        if paragraph
        and not any(marker in paragraph for marker in ("版权所有", "责任编辑", "互联网新闻信息服务"))
    ]
    if confirmed is None:
        for paragraph in paragraphs:
            confirmed = confirm_event(paragraph, reference)
            if confirmed is not None:
                break
    if confirmed is None:
        return None

    confirming = [paragraph for paragraph in paragraphs if confirm_event(paragraph, reference) is not None]
    excerpt = next((paragraph for paragraph in confirming if len(paragraph) >= MIN_SUMMARY_LENGTH), "")
    if not excerpt and confirming:
        excerpt = confirming[0]
    return {
        **record,
        **confirmed,
        "title": record.get("title", "") or excerpt[:60],
        "summary": (excerpt or record.get("title", ""))[:MAX_SUMMARY_LENGTH],
        "source_url": record.get("url", ""),
    }


def fetch_confirmed_events(now: datetime | None = None) -> list[dict]:
    """抓取并确认会议；单个来源失败只记日志。只允许后台调度线程调用。"""
    current = local_now(now)
    events: list[dict] = []
    enabled = {name.strip() for name in settings.BREAKING_NEWS_SOURCES.split(",") if name.strip()}
    for source_name, index_url, kind in SOURCE_FEEDS:
        if source_name not in enabled:
            continue
        try:
            entries = parse_index(source_name, index_url, kind, _fetch(source_name, index_url))
        except (OSError, ValueError) as exc:
            logger.warning("Breaking-news index unavailable (%s): %s", source_name, exc)
            continue

        seen: set[str] = set()
        candidates = []
        for entry in entries:
            published = parse_time(entry.get("date"))
            if entry["url"] in seen or published is None:
                continue
            seen.add(entry["url"])
            if not current - timedelta(days=7) <= published <= current + timedelta(days=1):
                continue
            if _find_meeting(_clean(entry["title"]), published.date()) is None:
                continue
            candidates.append(entry)

        for entry in candidates[:MAX_ARTICLE_FETCHES]:
            try:
                article = parse_article(entry, _fetch(source_name, entry["url"]))
            except (OSError, ValueError) as exc:
                logger.warning("Breaking-news article unavailable (%s): %s", entry["url"], exc)
                continue
            if article is not None:
                events.append(article)
    return events


def seed_breaking_news(db: Session) -> bool:
    """库里一条记录都没有时补一条已核实的事实，避免首次抓取前空白。"""
    if db.query(BreakingNews.id).first() is not None:
        return False
    db.add(
        BreakingNews(
            event_key=event_key(SEED_RECORD["event_name"], SEED_RECORD["start_date"]),
            event_name=SEED_RECORD["event_name"],
            event_type=SEED_RECORD["event_type"],
            start_date=SEED_RECORD["start_date"],
            end_date=SEED_RECORD["end_date"],
            status=meeting_status(SEED_RECORD["start_date"], SEED_RECORD["end_date"], local_now()),
            title=SEED_RECORD["title"],
            summary=SEED_RECORD["summary"],
            source_name=SEED_RECORD["source_name"],
            source_url=SEED_RECORD["source_url"],
            image=DEFAULT_IMAGE,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def refresh_breaking_news(
    db: Session, now: datetime | None = None, records: list[dict] | None = None
) -> int:
    """写入确认过的会议。同一场会议只更新状态和结束日期，不新增卡片。"""
    current = local_now(now)
    incoming = fetch_confirmed_events(current) if records is None else records
    touched = 0
    for item in incoming:
        event_name = _clean(item.get("event_name"))
        start_date = item.get("start_date")
        source_url = _clean(item.get("source_url") or item.get("url"))
        if not event_name or not isinstance(start_date, date) or not allowed_url(source_url):
            continue
        end_date = item.get("end_date") if isinstance(item.get("end_date"), date) else None
        key = event_key(event_name, start_date)
        row = db.query(BreakingNews).filter(BreakingNews.event_key == key).first()
        if row is None:
            # 报道只确认到闭幕日时开始日期会落在会期内：并回同一场会议的已有卡片，
            # 仍然按「会议名 + 开始日期」去重，不新增第二张卡片。
            row = next(
                (
                    candidate
                    for candidate in db.query(BreakingNews).filter(BreakingNews.event_name == event_name).all()
                    if candidate.start_date <= start_date <= last_meeting_day(candidate.start_date, candidate.end_date)
                ),
                None,
            )
        if row is None:
            db.add(
                BreakingNews(
                    event_key=key,
                    event_name=event_name,
                    event_type=_clean(item.get("event_type")) or "会议",
                    start_date=start_date,
                    end_date=end_date,
                    status=meeting_status(start_date, end_date, current),
                    title=_clean(item.get("title"))[:255] or event_name,
                    summary=_clean(item.get("summary"))[:MAX_SUMMARY_LENGTH] or None,
                    source_name=_clean(item.get("source_name")) or "官方来源",
                    source_url=source_url,
                    image=DEFAULT_IMAGE,
                )
            )
        else:
            if end_date is not None and row.end_date != end_date:
                row.end_date = end_date
            row.status = meeting_status(row.start_date, row.end_date, current)
        # Production sessions disable autoflush; make this item visible to the
        # next source record while keeping the whole refresh transactional.
        db.flush()
        touched += 1
    db.commit()
    if touched:
        logger.info("Breaking-news refresh stored or refreshed %s conference item(s)", touched)
    return touched


def scheduled_breaking_news_refresh(now: datetime | None = None) -> int:
    """调度线程入口：自己开会话、自己兜住异常，绝不向每日文章抛出。"""
    try:
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            seed_breaking_news(db)
            return refresh_breaking_news(db, now)
    except Exception:
        logger.exception("Scheduled breaking-news refresh failed; daily articles are unaffected")
        return 0
