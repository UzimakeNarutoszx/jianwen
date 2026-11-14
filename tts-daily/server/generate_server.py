#!/usr/bin/env python3
"""见闻每日朗读 · 服务器端生成（edge-tts + ffmpeg），不再依赖 Mac。

替代原来必须在 Mac（Apple Silicon / mlx-audio）上跑的 Qwen3-TTS 流水线：
  GET /api/v1/content/today → 逐篇 detail → textnorm 数字规范化
  → 按段落调用 edge-tts（微软神经网络中文声音）→ ffmpeg 段间 0.6s 拼接
  → loudnorm 统一响度 → 24kHz 单声道 64kbps mp3
  → 写 <out>/<date>/manifest.json（格式见 docs/today-audio-contract.md）

声音 id 保持不变（jianwen / dylan），前端不用改；音色换成 edge-tts 的
zh-CN-XiaoxiaoNeural / zh-CN-YunxiNeural。

用法:
  generate_server.py                          # 今天（Asia/Shanghai 06:00 换日）
  generate_server.py --date 2026-11-10
  generate_server.py --date 2026-11-10 --limit-articles 1 --voices jianwen
  generate_server.py --out /opt/jianwen/tts/staging --no-prune   # 试生成，不动线上
  generate_server.py --force                  # 已有 manifest 也重做
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import textnorm  # noqa: E402  数字规范化（纯标准库）

API = "http://127.0.0.1:8000"
DEFAULT_OUT = Path("/opt/jianwen/backend/uploads/tts")
TZ = ZoneInfo("Asia/Shanghai")
VERSION = "edge1"  # 流程版本，变了会体现在日志里

# id, 前端显示名, edge-tts 声音, 语速
VOICES = [
    ("jianwen", "见闻", "zh-CN-XiaoxiaoNeural", "+6%"),
    ("dylan", "男声", "zh-CN-YunxiNeural", "+6%"),
]
MAX_CHARS = 80
SECTION_GAP = 0.6
SR = 24000


def log(msg):
    print(f"[{datetime.now(TZ):%H:%M:%S}] {msg}", flush=True)


# ---------- 文本（与 Mac 版一致） ----------

def strip_markdown(text):
    """去掉 markdown 符号和 URL，只留可朗读的文字。"""
    s = text.replace("\r\n", "\n")
    s = re.sub(r"```.*?```", "", s, flags=re.S)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"(?:https?://|www\.)\S+", "", s)
    s = re.sub(r"^\s{0,3}(?:#{1,6}|>|[-*+]|\d+[.)])\s*", "", s, flags=re.M)
    s = re.sub(r"[*_`~|]+", "", s)
    s = re.sub(r"[ \t　]+", " ", s)
    return s.strip()


def split_sentences(block):
    """按 。！？；… 切句；单句超 80 字按 ，、： 再切，仍超就硬切。"""
    out = []
    for raw in re.findall(r"[^。！？；…\n]+[。！？；…]*", block):
        s = raw.strip(" \t，,、。")
        if not s:
            continue
        for piece in _fit(s):
            out.append(piece)
    return out


def _fit(s):
    if len(s) <= MAX_CHARS:
        return [s]
    parts, buf = [], ""
    for seg in re.findall(r"[^，、：,]+[，、：,]?", s):
        while len(seg) > MAX_CHARS:
            if buf:
                parts.append(buf)
                buf = ""
            parts.append(seg[:MAX_CHARS])
            seg = seg[MAX_CHARS:]
        if len(buf) + len(seg) <= MAX_CHARS:
            buf += seg
        else:
            if buf:
                parts.append(buf)
            buf = seg
    if buf:
        parts.append(buf)
    return [p.strip(" \t，,、：") for p in parts if p.strip(" \t，,、：")]


def article_sections(article):
    """按约定顺序拼段落：title、summary 各条、（每个 section 的 heading 和 body）。"""
    sections = []
    title = strip_markdown(article.get("title") or "")
    if title:
        sections.append([title])
    summary = [strip_markdown(x) for x in (article.get("summary") or [])]
    summary = [x for x in summary if x]
    if summary:
        sections.append(summary)
    for sec in article.get("sections") or []:
        blocks = [strip_markdown(sec.get("heading") or ""), strip_markdown(sec.get("body") or "")]
        blocks = [b for b in blocks if b]
        if blocks:
            sections.append(blocks)
    return sections


def section_texts(article):
    """每段合成一次：段内各块用「。」连起来，整段做数字规范化。"""
    texts = []
    for section in article_sections(article):
        joined = "。".join(x.rstrip("。！？；…") for x in section)
        if joined:
            texts.append(textnorm.normalize(joined + "。"))
    return texts


# ---------- 网络 ----------

def http_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "jianwen-tts-daily/edge"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def load_articles(date, limit):
    listing = http_json(f"{API}/api/v1/content/today")
    if isinstance(listing, dict):
        listing = listing.get("items") or listing.get("articles") or []
    ids = [x.get("article_id") or x.get("id") for x in listing if (x.get("article_id") or x.get("id"))]
    if limit:
        ids = ids[:limit]
    log(f"{date} 列表 {len(ids)} 篇：" + "、".join(ids))
    articles, skipped = [], 0
    for aid in ids:
        # article_id 形如 ai-daily-20261109-1：日期对不上（当天内容还没更新）就不发
        m = re.search(r"(20\d{6})", str(aid))
        if m and m.group(1) != date.replace("-", ""):
            skipped += 1
            continue
        try:
            detail = http_json(f"{API}/api/v1/content/articles/{aid}")
            articles.append(detail)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            log(f"取文章失败 {aid}: {exc}")
    if skipped:
        log(f"跳过 {skipped} 篇日期不是 {date} 的文章")
    if limit:
        articles = articles[:limit]
    return articles


# ---------- 合成 ----------

async def _synth(text, voice, rate, path):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(path))


def synth(text, voice, rate, path, tries=3):
    last = None
    for i in range(tries):
        try:
            asyncio.run(_synth(text, voice, rate, path))
            if path.exists() and path.stat().st_size > 1000:
                return
            last = RuntimeError(f"输出过小 {path.stat().st_size if path.exists() else 0}B")
        except Exception as exc:  # noqa: BLE001  网络/服务端错误都重试
            last = exc
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"edge-tts 合成失败：{last}")


def ffmpeg(args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def silence(path, seconds):
    ffmpeg(["-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", str(seconds),
            "-ar", str(SR), "-ac", "1", "-b:a", "64k", str(path)])


def concat_mp3(parts, out, lead_gap=True):
    """按顺序拼接，段间插 SECTION_GAP 静音；统一响度并输出 24k/单声道/64k。"""
    gap = out.with_suffix(".gap.mp3")
    if lead_gap:
        silence(gap, SECTION_GAP)
        segments = []
        for i, p in enumerate(parts):
            if i:
                segments.append(gap)
            segments.append(p)
    else:
        segments = list(parts)
    listfile = out.with_suffix(".txt")
    listfile.write_text("".join(f"file '{s}'\n" for s in segments), encoding="utf-8")
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listfile),
            "-af", "loudnorm=I=-18:TP=-1.5:LRA=11",
            "-ar", str(SR), "-ac", "1", "-b:a", "64k", str(out)])
    listfile.unlink(missing_ok=True)
    gap.unlink(missing_ok=True)


def probe_duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nw=1:nk=1", str(path)])
    return round(float(out.strip()), 1)


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:10]


# ---------- 输出 ----------

def generate_voice(article, voice_id, voice_name, rate, workdir):
    texts = section_texts(article)
    if not texts:
        raise RuntimeError("没有可朗读的文本")
    parts = []
    for i, text in enumerate(texts):
        part = workdir / f"s{i:02d}.mp3"
        synth(text, voice_name, rate, part)
        parts.append(part)
    out = workdir / f"{voice_id}.mp3"
    concat_mp3(parts, out)
    for p in parts:
        p.unlink(missing_ok=True)
    return out


def chown_tree(root):
    try:
        import pwd
        uid = pwd.getpwnam("jianwen").pw_uid
        gid = pwd.getpwnam("jianwen").pw_gid
    except KeyError:
        return
    for p in [root, *root.rglob("*")]:
        try:
            os.chown(p, uid, gid)
        except OSError:
            pass


def prune(out, keep=7):
    dirs = sorted([d for d in out.iterdir() if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name)],
                  reverse=True)
    for d in dirs[keep:]:
        log(f"清理旧音频 {d}")
        shutil.rmtree(d, ignore_errors=True)


def build_continuous(day, date, records, voices):
    """把当天各篇按顺序拼成每声音一条连续音轨，供熄屏/后台不依赖 JS 连播。"""
    result = {}
    for voice_id, label, voice_name, rate in voices:
        parts, segments, cursor = [], [], 0.0
        for rec in records:
            info = (rec.get("audio") or {}).get(voice_id)
            if not info:
                continue
            mp3 = day / rec["article_id"] / f"{voice_id}.mp3"
            if not mp3.exists():
                continue
            try:
                dur = float(info.get("duration") or 0) or probe_duration(mp3)
            except Exception:
                continue
            if parts:
                cursor += SECTION_GAP
            segments.append({
                "article_id": rec["article_id"],
                "start": round(cursor, 1),
                "end": round(cursor + dur, 1),
            })
            cursor += dur
            parts.append(mp3)
        if not parts:
            continue
        out = day / f"continuous-{voice_id}.mp3"
        try:
            if len(parts) == 1:
                shutil.copyfile(parts[0], out)
            else:
                concat_mp3(parts, out)
        except Exception as exc:  # noqa: BLE001  连续轨失败不影响单篇
            log(f"continuous {voice_id} 生成失败：{exc}")
            continue
        result[voice_id] = {
            "url": f"/uploads/tts/{date}/continuous-{voice_id}.mp3?v={digest(out)}",
            "duration": probe_duration(out),
            "segments": segments,
        }
        log(f"continuous {voice_id}: {result[voice_id]['duration']}s / {len(segments)} 篇")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--limit-articles", type=int, default=0)
    ap.add_argument("--voices", default=",".join(v[0] for v in VOICES))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-prune", action="store_true")
    ap.add_argument("--continuous-only", action="store_true", help="只根据已有单篇音频重建连续音轨")
    args = ap.parse_args()

    now = datetime.now(TZ)
    date = args.date or (now - timedelta(days=1) if now.hour < 6 else now).strftime("%Y-%m-%d")
    out = Path(args.out)
    day = out / date
    manifest_path = day / "manifest.json"
    wanted = {v.strip() for v in args.voices.split(",") if v.strip()}
    voices = [v for v in VOICES if v[0] in wanted]
    if not voices:
        raise SystemExit(f"未知声音 {args.voices}，可选：{[v[0] for v in VOICES]}")

    if args.continuous_only:
        if not manifest_path.exists():
            log(f"{manifest_path} 不存在，无法只重建连续音轨")
            return 1
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = manifest.get("articles") or []
        used = {vid for rec in records for vid in (rec.get("audio") or {})}
        continuous = build_continuous(day, date, records, [v for v in VOICES if v[0] in used])
        if not continuous:
            log("没有可拼接的音频")
            return 1
        manifest["continuous"] = continuous
        tmp = day / "manifest.json.tmp"
        tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tmp.replace(manifest_path)
        chown_tree(day)
        log(f"连续音轨已写入 {manifest_path}")
        return 0

    if manifest_path.exists() and not args.force:
        log(f"{manifest_path} 已存在，跳过（--force 可重做）")
        return 0

    log(f"开始 {date} · 版本 {VERSION} · 声音 {[v[0] for v in voices]}")
    articles = load_articles(date, args.limit_articles)
    if not articles:
        log(f"没有 {date} 的文章，退出（等下一班定时任务）")
        return 2

    day.mkdir(parents=True, exist_ok=True)
    records, failed = [], 0
    for idx, article in enumerate(articles):
        aid = str(article.get("article_id") or article.get("id"))
        title = article.get("title") or ""
        log(f"[{idx + 1}/{len(articles)}] {aid} {title}")
        work = day / aid
        work.mkdir(parents=True, exist_ok=True)
        audio = {}
        for voice_id, label, voice_name, rate in voices:
            t0 = time.time()
            try:
                generate_voice(article, voice_id, voice_name, rate, work)
                mp3 = work / f"{voice_id}.mp3"
                audio[voice_id] = {"url": f"/uploads/tts/{date}/{aid}/{voice_id}.mp3?v={digest(mp3)}",
                                   "duration": probe_duration(mp3)}
                log(f"  {voice_id}: {audio[voice_id]['duration']}s（{time.time() - t0:.1f}s）")
            except Exception as exc:  # noqa: BLE001  单个声音失败不影响其他声音
                failed += 1
                log(f"  {voice_id} 失败：{exc}")
        if audio:
            records.append({"article_id": aid, "title": title, "position": idx, "audio": audio})
        else:
            shutil.rmtree(work, ignore_errors=True)

    if not records:
        log("所有文章都失败，不写 manifest")
        return 3

    continuous = build_continuous(day, date, records, voices)
    manifest = {
        "date": date,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "voices": [{"id": v[0], "label": v[1]} for v in voices],
        "articles": records,
    }
    if continuous:
        manifest["continuous"] = continuous
    tmp = day / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(manifest_path)
    chown_tree(day)
    log(f"manifest 已写入 {manifest_path}（{len(records)} 篇，失败 {failed} 个声音）")
    if not args.no_prune:
        prune(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
