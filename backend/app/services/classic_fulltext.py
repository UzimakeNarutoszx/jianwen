from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import ssl
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.content import ClassicBook, ClassicBookChapter


@dataclass(frozen=True)
class ChapterSpec:
    title: str
    summary: str
    external_url: str
    content: str | None = None
    next_title: str = ""


@dataclass(frozen=True)
class BookSpec:
    book_id: str
    title: str
    author: str
    category: str
    description: str
    cover_image: str
    source_org: str
    external_url: str
    sort_order: int
    chapters: tuple[ChapterSpec, ...]


@dataclass(frozen=True)
class EmbeddedPageSpec:
    book_id: str
    url: str
    title_prefix: str = ""
    order_start: int = 1


@dataclass(frozen=True)
class QstheoryBookSpec:
    book_id: str
    url: str
    content_id: str
    expected_pages: int
    volume_label: str


PARTY_URL = "https://www.12371.cn/special/zggcdzc/zggcdzcqw/"
LEAGUE_URL = "https://www.gqt.org.cn/tngz/zc/202204/t20220419_787355.htm"
MANIFESTO_URL = "https://news.12371.cn/2018/04/24/ARTI1524553638408468.shtml"


STATIC_BOOKS: tuple[BookSpec, ...] = (
    BookSpec(
        book_id="party-constitution",
        title="中国共产党章程",
        author="中国共产党",
        category="党章团章",
        description="中国共产党的根本法规，集中规定党的性质、指导思想、组织制度、党员权利义务等基本内容。",
        cover_image="/static/images/共产党.png",
        source_org="共产党员网",
        external_url=PARTY_URL,
        sort_order=1,
        chapters=(
            ChapterSpec("总纲", "理解党的性质、指导思想、奋斗目标和基本路线。", PARTY_URL, next_title="第一章 党 员"),
            ChapterSpec("第一章 党员", "了解党员条件、义务、权利和发展党员要求。", PARTY_URL, next_title="第二章 党的组织制度"),
            ChapterSpec("第二章 党的组织制度", "了解民主集中制和党的组织原则。", PARTY_URL, next_title="第三章 党的中央组织"),
            ChapterSpec("第三章 党的中央组织", "了解党的全国代表大会、中央委员会等中央组织规则。", PARTY_URL, next_title="第四章 党的地方组织"),
            ChapterSpec("第四章 党的地方组织", "了解地方各级代表大会和地方委员会的基本规则。", PARTY_URL, next_title="第五章 党的基层组织"),
            ChapterSpec("第五章 党的基层组织", "了解基层党组织设置、职责和工作要求。", PARTY_URL, next_title="第六章 党的干部"),
            ChapterSpec("第六章 党的干部", "了解党的干部标准、选拔和管理要求。", PARTY_URL, next_title="第七章 党的纪律"),
            ChapterSpec("第七章 党的纪律", "了解党的纪律要求和处分规则。", PARTY_URL, next_title="第八章 党的纪律检查机关"),
            ChapterSpec("第八章 党的纪律检查机关", "了解纪律检查机关的设置和职责。", PARTY_URL, next_title="第九章 党 组"),
            ChapterSpec("第九章 党组", "了解党组的设置、任务和领导关系。", PARTY_URL, next_title="第十章 党和共产主义青年团的关系"),
            ChapterSpec("第十章 党和共产主义青年团的关系", "了解党对共青团的领导和团组织职责。", PARTY_URL, next_title="第十一章 党徽党旗"),
            ChapterSpec("第十一章 党徽党旗", "了解党徽党旗的基本规范。", PARTY_URL),
        ),
    ),
    BookSpec(
        book_id="league-constitution",
        title="中国共产主义青年团章程",
        author="中国共产主义青年团",
        category="党章团章",
        description="共青团的基本章程，适合了解团的性质、组织制度、团员要求和青年工作基础。",
        cover_image="/static/images/公共生活.png",
        source_org="中国共青团网",
        external_url=LEAGUE_URL,
        sort_order=2,
        chapters=(
            ChapterSpec("总则", "了解共青团性质、任务和行动指南。", LEAGUE_URL, next_title="第一章 团员"),
            ChapterSpec("第一章 团员", "了解团员条件、义务和权利。", LEAGUE_URL, next_title="第二章 团的组织制度"),
            ChapterSpec("第二章 团的组织制度", "了解团组织运行原则。", LEAGUE_URL, next_title="第三章 团的中央组织"),
            ChapterSpec("第三章 团的中央组织", "了解团的全国代表大会和中央委员会。", LEAGUE_URL, next_title="第四章 团的地方组织、解放军和武警部队中团的组织"),
            ChapterSpec("第四章 团的地方组织、解放军和武警部队中团的组织", "了解地方团组织和军队团组织规则。", LEAGUE_URL, next_title="第五章 团的基层组织"),
            ChapterSpec("第五章 团的基层组织", "了解基层团组织设置和职责。", LEAGUE_URL, next_title="第六章 团的干部"),
            ChapterSpec("第六章 团的干部", "了解团干部要求和管理。", LEAGUE_URL, next_title="第七章 团的纪律"),
            ChapterSpec("第七章 团的纪律", "了解团的纪律和处分规则。", LEAGUE_URL, next_title="第八章 团旗、团徽、团歌"),
            ChapterSpec("第八章 团旗、团徽、团歌", "了解团的标识和象征。", LEAGUE_URL, next_title="第九章 团的经费"),
            ChapterSpec("第九章 团的经费", "了解团的经费来源和使用。", LEAGUE_URL, next_title="第十章 团同少年先锋队的关系"),
            ChapterSpec("第十章 团同少年先锋队的关系", "了解共青团和少先队的工作关系。", LEAGUE_URL),
        ),
    ),
    BookSpec(
        book_id="communist-manifesto",
        title="共产党宣言",
        author="马克思、恩格斯",
        category="马克思主义经典",
        description="马克思主义经典文本之一，适合作为理解科学社会主义和共产党人理论源流的入门读物。",
        cover_image="/static/images/政策解读.png",
        source_org="共产党员网",
        external_url=MANIFESTO_URL,
        sort_order=3,
        chapters=(
            ChapterSpec("一、资产者和无产者", "从阶级关系和资本主义发展理解现代社会矛盾。", MANIFESTO_URL, next_title="二、无产者和共产党人"),
            ChapterSpec("二、无产者和共产党人", "理解共产党人与无产阶级运动的关系。", MANIFESTO_URL, next_title="三、社会主义的和共产主义的文献"),
            ChapterSpec("三、社会主义的和共产主义的文献", "了解不同社会主义思潮的批判与区分。", MANIFESTO_URL, next_title="四、共产党人对各种反对党派的态度"),
            ChapterSpec("四、共产党人对各种反对党派的态度", "理解共产党人在不同政治条件下的策略。", MANIFESTO_URL),
        ),
    ),
    BookSpec(
        book_id="selected-works-mao",
        title="毛泽东选集",
        author="毛泽东",
        category="中国化时代化马克思主义",
        description="收录毛泽东同志在中国革命各时期的重要著作，适合按历史阶段和问题意识阅读。",
        cover_image="/static/images/共产党.png",
        source_org="共产党员网",
        external_url="https://www.12371.cn/special/mzdxj/dyj/",
        sort_order=4,
        chapters=(),
    ),
    BookSpec(
        book_id="selected-works-deng",
        title="邓小平文选",
        author="邓小平",
        category="中国化时代化马克思主义",
        description="理解邓小平理论的重要文本入口，适合结合改革开放和社会主义现代化建设历史阅读。",
        cover_image="/static/images/党和国家.png",
        source_org="共产党员网",
        external_url="https://www.12371.cn/special/dxpwx/d3j/",
        sort_order=5,
        chapters=(),
    ),
)


EMBEDDED_PAGE_SOURCES: tuple[EmbeddedPageSpec, ...] = (
    EmbeddedPageSpec("selected-works-mao", "https://www.12371.cn/special/mzdxj/dyj/", "第一卷"),
    EmbeddedPageSpec("selected-works-mao", "https://www.12371.cn/special/mzdxj/dej/", "第二卷"),
    EmbeddedPageSpec("selected-works-mao", "https://www.12371.cn/special/mzdxj/d3j/", "第三卷"),
    EmbeddedPageSpec("selected-works-mao", "https://www.12371.cn/special/mzdxj/d4j/", "第四卷"),
    EmbeddedPageSpec("selected-works-deng", "https://www.12371.cn/special/dxpwx/d1j/", "第一卷"),
    EmbeddedPageSpec("selected-works-deng", "https://www.12371.cn/special/dxpwx/d2j/", "第二卷"),
    EmbeddedPageSpec("selected-works-deng", "https://www.12371.cn/special/dxpwx/d3j/", "第三卷"),
)


QSTHEORY_SOURCES: tuple[QstheoryBookSpec, ...] = (
    QstheoryBookSpec("selected-works-mao", "https://www.qstheory.cn/books/2019-07/31/c_1119448591.htm", "1119448591", 28, "第一卷"),
    QstheoryBookSpec("selected-works-mao", "https://www.qstheory.cn/books/2019-07/31/c_1119478087.htm", "1119478087", 40, "第二卷"),
    QstheoryBookSpec("selected-works-mao", "https://www.qstheory.cn/books/2019-07/31/c_1119479227.htm", "1119479227", 31, "第三卷"),
    QstheoryBookSpec("selected-works-mao", "https://www.qstheory.cn/books/2019-07/31/c_1119479873.htm", "1119479873", 70, "第四卷"),
    QstheoryBookSpec("selected-works-deng", "https://www.qstheory.cn/books/2019-07/31/c_1119483619.htm", "1119483619", 44, "第一卷"),
    QstheoryBookSpec("selected-works-deng", "https://www.qstheory.cn/books/2019-07/31/c_1119484755.htm", "1119484755", 61, "第二卷"),
    QstheoryBookSpec("selected-works-deng", "https://www.qstheory.cn/books/2019-07/31/c_1119485398.htm", "1119485398", 120, "第三卷"),
)

QSTHEORY_EXPECTED_FULL_TEXT_COUNTS = {
    "selected-works-mao": 158,
    "selected-works-deng": 224,
}


def has_complete_qstheory_full_text(db: Session, book_id: str) -> bool:
    expected_count = QSTHEORY_EXPECTED_FULL_TEXT_COUNTS.get(book_id)
    return bool(expected_count and existing_full_text_count(db, book_id) >= expected_count)


def import_classic_full_texts(db: Session) -> None:
    for book in STATIC_BOOKS:
        upsert_book(db, book)
        if not book.chapters:
            continue
        if book.chapters and existing_full_text_count(db, book.book_id) >= len(book.chapters):
            chapters = existing_chapters_as_specs(db, book.book_id)
        else:
            chapters = resolve_static_chapters(book)
        prepare_chapter_orders(db, book.book_id)
        for order, chapter in enumerate(chapters, start=1):
            upsert_chapter(db, book.book_id, chapter, order)
        prune_empty_stale_chapters(db, book.book_id, [chapter.title for chapter in chapters])

    resolved_chapters = resolve_qstheory_chapters(db)
    if not all(
        existing_full_text_count(db, book_id) >= expected_count
        for book_id, expected_count in QSTHEORY_EXPECTED_FULL_TEXT_COUNTS.items()
    ):
        for book_id, chapters in resolve_embedded_chapters().items():
            resolved_chapters.setdefault(book_id, chapters)

    for book_id, chapters in resolved_chapters.items():
        remove_known_stale_chapters(db, book_id)
        prepare_chapter_orders(db, book_id)
        for order, chapter in enumerate(chapters, start=1):
            upsert_chapter(db, book_id, chapter, order)
        prune_empty_stale_chapters(db, book_id, [chapter.title for chapter in chapters])

    db.commit()


def upsert_book(db: Session, book: BookSpec) -> None:
    record = db.query(ClassicBook).filter(ClassicBook.book_id == book.book_id).first()
    data = {
        "book_id": book.book_id,
        "title": book.title,
        "author": book.author,
        "category": book.category,
        "description": book.description,
        "cover_image": book.cover_image,
        "source_org": book.source_org,
        "external_url": book.external_url,
        "is_featured": True,
        "sort_order": book.sort_order,
    }
    if record is None:
        db.add(ClassicBook(**data))
        db.flush()
        return
    for key, value in data.items():
        setattr(record, key, value)
    db.flush()


def resolve_static_chapters(book: BookSpec) -> list[ChapterSpec]:
    pages: dict[str, str] = {}
    chapters: list[ChapterSpec] = []
    for chapter in book.chapters:
        content = chapter.content
        if content is None:
            text = pages.setdefault(chapter.external_url, fetch_page_text(chapter.external_url))
            content = extract_section(text, chapter.title, chapter.next_title)
        chapters.append(
            ChapterSpec(
                title=chapter.title,
                summary=chapter.summary,
                external_url=chapter.external_url,
                content=content or None,
                next_title=chapter.next_title,
            )
        )
    return chapters


def resolve_embedded_chapters() -> dict[str, list[ChapterSpec]]:
    grouped: dict[str, list[ChapterSpec]] = {}
    for source in EMBEDDED_PAGE_SOURCES:
        try:
            html = fetch_html(source.url)
        except OSError:
            continue
        chapters = extract_embedded_articles(html, source)
        grouped.setdefault(source.book_id, []).extend(chapters)
    return grouped


def resolve_qstheory_chapters(db: Session) -> dict[str, list[ChapterSpec]]:
    grouped: dict[str, list[ChapterSpec]] = {}
    skipped_book_ids = set()
    for book_id, expected_count in QSTHEORY_EXPECTED_FULL_TEXT_COUNTS.items():
        if existing_full_text_count(db, book_id) >= expected_count:
            skipped_book_ids.add(book_id)
    for source in QSTHEORY_SOURCES:
        if source.book_id in skipped_book_ids:
            continue
        try:
            html = fetch_html(source.url, allow_unverified_ssl=True)
        except OSError:
            continue

        page_numbers = discover_qstheory_pages(html, source.content_id, source.expected_pages)
        chapters: list[ChapterSpec] = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(fetch_qstheory_chapter, source, page_number, html if page_number == 1 else None): page_number
                for page_number in page_numbers
            }
            for future in as_completed(futures):
                chapter = future.result()
                if chapter:
                    chapters.append(chapter)
        chapters.sort(key=lambda chapter: page_numbers.index(qstheory_page_number(chapter.external_url)))
        grouped.setdefault(source.book_id, []).extend(dedupe_chapters(chapters))
    return grouped


def existing_full_text_count(db: Session, book_id: str) -> int:
    return (
        db.query(ClassicBookChapter)
        .filter(ClassicBookChapter.book_id == book_id, ClassicBookChapter.content.isnot(None))
        .count()
    )


def existing_chapters_as_specs(db: Session, book_id: str) -> list[ChapterSpec]:
    rows = (
        db.query(ClassicBookChapter)
        .filter(ClassicBookChapter.book_id == book_id)
        .order_by(ClassicBookChapter.chapter_order, ClassicBookChapter.id)
        .all()
    )
    return [
        ChapterSpec(
            title=row.title,
            summary=row.summary or make_summary(row.content or ""),
            external_url=row.external_url or "",
            content=row.content,
        )
        for row in rows
        if row.content and not is_known_stale_chapter(row.title)
    ]


def fetch_qstheory_chapter(source: QstheoryBookSpec, page_number: int, first_page_html: str | None = None) -> ChapterSpec | None:
    page_url = qstheory_page_url(source.url, source.content_id, page_number)
    try:
        page_html = first_page_html if first_page_html is not None else fetch_html(page_url, allow_unverified_ssl=True)
    except OSError:
        return None
    chapter = extract_qstheory_chapter(page_html, page_url)
    if chapter and chapter.title == "注释":
        return ChapterSpec(
            title=f"{source.volume_label} 注释",
            summary=chapter.summary,
            external_url=chapter.external_url,
            content=chapter.content,
        )
    return chapter


def merge_chapters(target: list[ChapterSpec], incoming: Iterable[ChapterSpec]) -> None:
    index_by_title = {normalize_title(chapter.title): index for index, chapter in enumerate(target)}
    for chapter in incoming:
        key = normalize_title(chapter.title)
        existing_index = index_by_title.get(key)
        if existing_index is None:
            index_by_title[key] = len(target)
            target.append(chapter)
            continue
        existing = target[existing_index]
        if chapter.content and not existing.content:
            target[existing_index] = chapter


def upsert_chapter(db: Session, book_id: str, chapter: ChapterSpec, order: int) -> None:
    existing = find_chapter_by_title(db, book_id, chapter.title)
    if existing is None:
        existing = ClassicBookChapter(book_id=book_id, title=chapter.title)
        db.add(existing)
    existing.chapter_order = order
    existing.summary = chapter.summary
    existing.external_url = chapter.external_url
    if chapter.content:
        existing.content = chapter.content
    db.flush()


def prepare_chapter_orders(db: Session, book_id: str) -> None:
    db.execute(
        text(
            "UPDATE classic_book_chapters "
            "SET chapter_order = id + 100000 "
            "WHERE book_id = :book_id"
        ),
        {"book_id": book_id},
    )
    db.expire_all()
    db.flush()


def prune_empty_stale_chapters(db: Session, book_id: str, valid_titles: Iterable[str]) -> None:
    valid = {normalize_title(title) for title in valid_titles}
    chapters = db.query(ClassicBookChapter).filter(ClassicBookChapter.book_id == book_id).all()
    for chapter in chapters:
        if normalize_title(chapter.title) not in valid:
            db.delete(chapter)
    db.flush()


def remove_known_stale_chapters(db: Session, book_id: str) -> None:
    chapters = db.query(ClassicBookChapter).filter(ClassicBookChapter.book_id == book_id).all()
    for chapter in chapters:
        if is_known_stale_chapter(chapter.title):
            db.delete(chapter)
    db.flush()


def is_known_stale_chapter(title: str) -> bool:
    normalized = normalize_title(title)
    stale_titles = {
        "第一卷",
        "第二卷",
        "第三卷",
        "第四卷",
        "毛泽东选集第一卷",
        "毛泽东选集第二卷",
        "毛泽东选集第三卷",
        "毛泽东选集第四卷",
        "邓小平文选第一卷",
        "邓小平文选第二卷",
        "邓小平文选第三卷",
        "注释",
    }
    return normalized in {normalize_title(title) for title in stale_titles}


def fetch_html(url: str, allow_unverified_ssl: bool = False) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    context = ssl._create_unverified_context() if allow_unverified_ssl and url.startswith("https://") else None
    raw = urlopen(request, timeout=20, context=context).read()
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def fetch_page_text(url: str) -> str:
    html = fetch_html(url)
    html = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", html, flags=re.I)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</p>|</div>|</li>|</h[1-6]>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "\n", html)
    text = unescape(html)
    lines = [clean_line(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def discover_qstheory_pages(html: str, content_id: str, expected_pages: int) -> list[int]:
    numbers = {1}
    for match in re.finditer(rf"c_{re.escape(content_id)}_(\d+)\.htm", html):
        numbers.add(int(match.group(1)))
    if max(numbers, default=1) < expected_pages:
        numbers.update(range(1, expected_pages + 1))
    return sorted(numbers)


def qstheory_page_url(base_url: str, content_id: str, page_number: int) -> str:
    if page_number == 1:
        return re.sub(rf"c_{re.escape(content_id)}(?:_\d+)?\.htm$", f"c_{content_id}.htm", base_url)
    return re.sub(rf"c_{re.escape(content_id)}(?:_\d+)?\.htm$", f"c_{content_id}_{page_number}.htm", base_url)


def qstheory_page_number(url: str) -> int:
    match = re.search(r"c_\d+_(\d+)\.htm$", url)
    return int(match.group(1)) if match else 1


def extract_qstheory_chapter(html: str, page_url: str) -> ChapterSpec | None:
    highlight_match = re.search(
        r"<div\s+class=\"highlight\"[^>]*>([\s\S]*?)(?:<div\s+class=\"div_currpage\"|<div\s+width=\"100%\"|</div>\s*</div>\s*<div class=\"clear\")",
        html,
        flags=re.I,
    )
    if not highlight_match:
        return None
    fragment = highlight_match.group(1)
    title = extract_qstheory_title(fragment)
    content = html_fragment_to_text(fragment)
    content = remove_noise(content)
    if not title or len(content) < 120:
        return None
    return ChapterSpec(title=title, summary=make_summary(content), external_url=page_url, content=content)


def extract_qstheory_title(fragment: str) -> str:
    titles = []
    for match in re.finditer(r"<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>", fragment, flags=re.S | re.I):
        title = clean_line(unescape(re.sub(r"<[^>]+>", " ", match.group(1))))
        if title and not is_qstheory_group_title(title):
            titles.append(title.strip("《》"))
    return titles[0] if titles else ""


def is_qstheory_group_title(title: str) -> bool:
    group_titles = (
        "第一次国内革命战争时期",
        "第二次国内革命战争时期",
        "抗日战争时期",
        "解放战争时期",
        "社会主义革命和社会主义建设时期",
    )
    normalized = normalize_title(title).replace("（上）", "").replace("（下）", "")
    return any(normalize_title(group) == normalized for group in group_titles)


def extract_embedded_articles(html: str, source: EmbeddedPageSpec) -> list[ChapterSpec]:
    results: list[ChapterSpec] = []

    blocks = re.findall(
        r"<li[^>]*>[\s\S]*?<a[^>]+href=\"(?P<href>[^\"]+)\"[^>]*>[\s\S]*?<i>\s*\d+\s*</i>(?P<anchor>[\s\S]*?)</a>[\s\S]*?</li>",
        html,
        flags=re.I,
    )
    if not blocks:
        blocks = [
            ("", block)
            for block in re.findall(
                r"<li[^>]*>[\s\S]*?<h3[^>]*title=\"[^\"]+\"[\s\S]*?</li>",
                html,
                flags=re.I,
            )
        ]

    for href, block in blocks:
        title = extract_title_from_block(block)
        if not title or is_noise_title(title):
            continue
        content = extract_text_div(block)
        external_url = source.url if not href or href == "#" else urljoin(source.url, href)
        summary = make_summary(content) if content else f"{source.title_prefix}：《{title}》。"
        results.append(ChapterSpec(title=title, summary=summary, external_url=external_url, content=content or None))
    return dedupe_chapters(results)


def extract_title_from_block(block: str) -> str:
    title_match = re.search(r"<h3[^>]*title=\"([^\"]+)\"", block, flags=re.I)
    if title_match:
        return clean_line(unescape(title_match.group(1)))
    text = unescape(re.sub(r"<[^>]+>", " ", block))
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^\d+\s*", "", text)
    return clean_line(text)


def extract_text_div(block: str) -> str:
    match = re.search(r"<div\s+class=\"text\"[^>]*>([\s\S]*?)</div>", block, flags=re.I)
    if not match:
        return ""
    return html_fragment_to_text(match.group(1))


def html_fragment_to_text(html: str) -> str:
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</p>|</div>|</li>|</h[1-6]>", "\n", html, flags=re.I)
    text = unescape(re.sub(r"<[^>]+>", "\n", html))
    lines = [clean_line(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def extract_section(text: str, title: str, next_title: str = "") -> str:
    start = find_title_index(text, title)
    if start < 0:
        return ""

    end = len(text)
    if next_title:
        next_index = find_title_index(text[start + len(title) :], next_title)
        if next_index >= 0:
            end = start + len(title) + next_index

    section = remove_noise(text[start:end].strip())
    if len(section) < 80:
        return ""
    return section


def find_title_index(text: str, title: str) -> int:
    candidates = [title]
    if " " in title:
        candidates.append(title.replace(" ", "\u3000"))
    if "\u3000" in title:
        candidates.append(title.replace("\u3000", " "))
    compact = re.sub(r"\s+", "", title)
    if compact not in candidates:
        candidates.append(compact)

    for candidate in candidates:
        pattern = title_pattern(candidate)
        matches = list(re.finditer(pattern, text))
        if matches:
            return matches[-1].start()
    return -1


def title_pattern(title: str) -> str:
    chars = [re.escape(char) for char in title if not char.isspace()]
    return r"\s*".join(chars)


def clean_line(line: str) -> str:
    line = line.replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", line).strip()


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", "", title or "")


def find_chapter_by_title(db: Session, book_id: str, title: str) -> ClassicBookChapter | None:
    expected = normalize_title(title)
    chapters = db.query(ClassicBookChapter).filter(ClassicBookChapter.book_id == book_id).all()
    for chapter in chapters:
        if normalize_title(chapter.title) == expected:
            return chapter
    return None


def remove_noise(text: str) -> str:
    stop_patterns = (
        "发布时间：",
        "发布于：",
        "分享",
        "打印",
        "关于我们",
        "联系我们",
        "共产党员网 版权所有",
        "京ICP备",
        "热搜",
    )
    for pattern in stop_patterns:
        index = text.find(pattern)
        if index > 0:
            text = text[:index]
    lines = []
    for line in text.splitlines():
        value = clean_line(line)
        if not value:
            continue
        if value.startswith("http://") or value.startswith("https://"):
            continue
        if re.fullmatch(r"\d+", value):
            continue
        lines.append(value)
    return "\n".join(lines).strip()


def make_summary(content: str) -> str:
    lines = [line for line in content.splitlines() if line.strip()]
    text = next((line for line in lines[1:] if len(line) > 20), lines[0] if lines else "")
    return text[:120]


def is_noise_title(title: str) -> bool:
    if len(title) < 2:
        return True
    noise = ("共产党员网", "习近平党建思想", "注册", "忘记密码", "学习贯彻")
    return any(item in title for item in noise)


def dedupe_chapters(chapters: Iterable[ChapterSpec]) -> list[ChapterSpec]:
    seen: set[str] = set()
    results: list[ChapterSpec] = []
    for chapter in chapters:
        key = normalize_title(chapter.title)
        if key in seen:
            continue
        seen.add(key)
        results.append(chapter)
    return results
