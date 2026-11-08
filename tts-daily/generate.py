#!/usr/bin/env python3
"""今日朗读：逐句合成 4 种声音的 mp3，写 manifest.json（格式见 docs/today-audio-contract.md）。

流程：GET /api/v1/content/today → 逐篇 GET /api/v1/content/articles/{id} → 拼朗读文本
（去 markdown 和 URL）→ 按 。！？； 切句、每段 ≤80 字 → 每句单独合成 → 句间 0.25s、
段落间 0.6s 静音 → ffmpeg 拼接转 mp3（单声道 24kHz 64kbps）→ ffprobe 读时长写 manifest。

jianwen 用 1.7B Base 模型做 ICL 克隆，其余三个用 0.6B CustomVoice。每种模型只加载一次。
缓存键 = 文本 + 声音 + 模型 + 流程版本，文本和声音没变就跳过；单个声音失败只记日志。

用法:
  tts-daily/generate.py                          # 今天（Asia/Shanghai 06:00 换日）全部文章 4 个声音
  tts-daily/generate.py --limit-articles 1 --max-sentences 3   # 调试：只做第一篇前 3 句
  tts-daily/generate.py --from-json /tmp/today-full.json       # 离线：用本地 JSON 代替 API
（脚本会自己切到 ~/.local/share/qwen3-tts/venv/bin/python 执行。）
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import traceback
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
VENV_PY = Path.home() / ".local/share/qwen3-tts/venv/bin/python"
BASE_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"
CUSTOM_MODEL = "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-4bit"
# 克隆参考音频（ref.wav + 同名 ref.txt）放在私有目录，通过环境变量指定。
REF_AUDIO = Path(os.environ.get("JIANWEN_VOICE_REF_DIR", "voice_ref")) / "ref.wav"
REF_TEXT = REF_AUDIO.with_suffix(".txt")
VOICES = [("jianwen", "见闻"), ("dylan", "男声·京味")]  # vivian / uncle_fu 2026-11-08 听感不佳已停用
# 成片后处理：按声音变速（uncle_fu 原生只有 ~2.3 字/秒）+ 统一响度（-18 LUFS，峰值 ≤ -1.5 dBTP，防削波）
TEMPO = {"jianwen": 1.0, "dylan": 1.0}
POST_VERSION = "post1"


def post_filter(voice):
    chain = [f"atempo={TEMPO.get(voice, 1.0)}"] if TEMPO.get(voice, 1.0) != 1.0 else []
    chain.append("loudnorm=I=-18:TP=-1.5:LRA=11")
    return ",".join(chain)
CUSTOM_SPEAKER = {"vivian": "Vivian", "uncle_fu": "Uncle_Fu", "dylan": "Dylan"}
SENT_GAP, SECTION_GAP = 0.25, 0.6
MAX_CHARS = 80
SR = 24000
PAD = 0.03  # 去静音后两端各留 30ms，避免咬掉字头
VERSION = "v1"  # 改动合成流程就 +1，旧缓存自动失效
TZ = ZoneInfo("Asia/Shanghai")


def ensure_runtime():
    """不在 qwen3-tts 的 venv 里就用 venv 的解释器重跑自己。"""
    try:
        import mlx.core  # noqa: F401
        import numpy  # noqa: F401
        import soundfile  # noqa: F401
    except ImportError:
        if Path(sys.executable).resolve() != VENV_PY.resolve() and VENV_PY.exists():
            os.execv(str(VENV_PY), [str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]])
        raise SystemExit(f"缺 mlx/numpy/soundfile：请用 {VENV_PY} 运行本脚本")


def log(msg):
    print(f"[{datetime.now(TZ):%H:%M:%S}] {msg}", flush=True)


# ---------- 文本 ----------

def strip_markdown(text):
    """去掉 markdown 符号和 URL，只留可朗读的文字。"""
    s = text.replace("\r\n", "\n")
    s = re.sub(r"```.*?```", "", s, flags=re.S)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)          # 图片
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)      # 链接留文字
    s = re.sub(r"<[^>]+>", "", s)                        # html 标签
    s = re.sub(r"(?:https?://|www\.)\S+", "", s)         # 裸 URL
    s = re.sub(r"^\s{0,3}(?:#{1,6}|>|[-*+]|\d+[.)])\s*", "", s, flags=re.M)  # 标题/引用/列表
    s = re.sub(r"[*_`~|]+", "", s)                       # 强调、行内代码、表格竖线
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
        while len(seg) > MAX_CHARS:  # 没有标点的长串，硬切
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


def build_sentences(article, max_sentences=None):
    """返回 [(text, gap_after)]，最后一个 gap 为 None。"""
    rows = []  # [(text, is_section_start)]
    for section in article_sections(article):
        first = True
        for block in section:
            for sent in split_sentences(block):
                rows.append((sent, first))
                first = False
    if max_sentences:
        rows = rows[:max_sentences]
    out = []
    for i, (text, _) in enumerate(rows):
        gap = None
        if i + 1 < len(rows):
            gap = SECTION_GAP if rows[i + 1][1] else SENT_GAP
        out.append((text, gap))
    return out


# ---------- 数据 ----------

def http_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "jianwen-tts-daily/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def load_articles(api_base, date, from_json, limit):
    if from_json:
        data = json.loads(Path(from_json).read_text(encoding="utf-8"))
        items = data.get("articles") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise SystemExit(f"{from_json} 里没有 articles 列表")
        articles = [a for a in items if a.get("sections")]
        empty = len(items) - len(articles)
        if empty:
            log(f"跳过 {empty} 篇缺 sections 的条目（--from-json 需要完整文章 JSON）")
    else:
        listing = http_json(f"{api_base}/api/v1/content/today")
        if isinstance(listing, dict):
            listing = listing.get("items") or listing.get("articles") or []
        ids = [x["article_id"] for x in listing if x.get("article_id")]
        if limit:  # 列表就截断，别去请求用不到的文章详情
            ids = ids[:limit]
        log(f"{date} 列表 {len(ids)} 篇：" + "、".join(ids))
        articles = []
        for aid in ids:
            try:
                articles.append(http_json(f"{api_base}/api/v1/content/articles/{aid}"))
            except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
                log(f"取文章失败 {aid}: {exc}")
    if limit:
        articles = articles[:limit]
    return articles


# ---------- 合成 ----------

def default_date():
    now = datetime.now(TZ)
    return (now - timedelta(days=1) if now.hour < 6 else now).strftime("%Y-%m-%d")


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE)


def probe_duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def probe_stream(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a:0",
                                   "-show_entries", "stream=sample_rate,channels,bit_rate",
                                   "-of", "default=nw=1", str(path)]).decode()
    return dict(line.split("=", 1) for line in out.strip().splitlines() if "=" in line)


class Synth:
    """按需加载模型，每种模型只加载一次。"""

    def __init__(self):
        self.models = {}
        self.np = self.sf = self.mx = None
        self.ref = None
        if REF_AUDIO.is_file() and REF_TEXT.is_file():
            self.ref = (REF_AUDIO, REF_TEXT.read_text(encoding="utf-8").strip())
        else:
            log(f"警告：克隆参考缺失（{REF_AUDIO} / {REF_TEXT}），jianwen 将无法生成")

    def model(self, name, model_id):
        if name not in self.models:
            if self.mx is None:
                import mlx.core as mx
                import numpy as np
                import soundfile as sf
                from mlx_audio.tts.utils import load_model  # noqa: F401
                self.mx, self.np, self.sf = mx, np, sf
                self.load = load_model
            log(f"加载模型 {model_id} …")
            t0 = time.time()
            self.models[name] = self.load(model_id)
            log(f"加载完成 {model_id}（{time.time() - t0:.1f}s）")
        return self.models[name]

    def synth(self, text, voice, raw_path):
        """合成一句到 raw_path（模型原始采样率 wav）。"""
        if voice == "jianwen":
            model = self.model("base", BASE_MODEL)
            kw = dict(lang_code="Chinese", max_tokens=1200, temperature=.65,
                      ref_audio=str(self.ref[0]), ref_text=self.ref[1])
        else:
            model = self.model("custom", CUSTOM_MODEL)
            kw = dict(voice=CUSTOM_SPEAKER[voice], lang_code="Chinese",
                      max_tokens=max(240, min(1024, len(text) * 10)), temperature=.65)
        mx, np, sf = self.mx, self.np, self.sf
        mx.random.seed(42)  # 固定种子，同一句每次都一样，缓存才有意义
        chunks, rate = [], SR
        for result in model.generate(text=text, **kw):
            mx.eval(result.audio)
            chunks.append(np.array(result.audio))
            rate = result.sample_rate
        if not chunks:
            raise RuntimeError(f"模型没有返回音频: {text}")
        sf.write(str(raw_path), np.concatenate(chunks), rate, format="WAV")


def trim_pad(path, np, sf):
    """Qwen 输出两端各带 0.4–0.6s 静音，只留 30ms，句间静音才准。"""
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    a = np.abs(x).max(axis=1)
    if a.max() <= 0:
        return
    idx = np.nonzero(a > a.max() * 0.01)[0]
    lo = max(int(idx[0]) - int(sr * PAD), 0)
    hi = min(int(idx[-1]) + int(sr * PAD) + 1, len(x))
    sf.write(str(path), x[lo:hi], sr, format="WAV", subtype="PCM_16")


def silence_wav(cache, seconds, np, sf):
    path = cache / f"sil-{seconds:.2f}.wav"
    if not path.exists():
        sf.write(str(path), np.zeros(int(SR * seconds), dtype="float32"), SR,
                 format="WAV", subtype="PCM_16")
    return path


def make_mp3(sentences, voice, synth, cache, mp3_path, timing):
    """逐句合成（带缓存）→ 拼静音 → mp3。返回 (耗时秒, 合成句数)。"""
    parts, n_synth, t_spent = [], 0, 0.0
    for text, gap in sentences:
        digest = hashlib.sha256(f"{text}|{voice}|{VERSION}".encode()).hexdigest()[:16]
        wav = cache / f"{digest}.wav"
        if not wav.exists():
            raw = cache / f"{digest}.raw.wav"
            t0 = time.time()
            synth.synth(text, voice, raw)
            run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-ar", SR, "-ac", 1,
                 "-c:a", "pcm_s16le", wav])
            trim_pad(wav, synth.np, synth.sf)
            raw.unlink(missing_ok=True)
            dt = time.time() - t0
            n_synth += 1
            t_spent += dt
            timing.append((len(text), dt))
            log(f"    {voice} {len(text):>2}字 {dt:5.2f}s  {text[:24]}")
        parts.append(wav)
        if gap:
            parts.append(silence_wav(cache, gap, synth.np, synth.sf))
    listfile = cache / f"list-{mp3_path.stem}-{hashlib.sha256(str(mp3_path).encode()).hexdigest()[:8]}.txt"
    listfile.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-af", post_filter(voice), "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k", mp3_path])
    listfile.unlink(missing_ok=True)
    return t_spent, n_synth


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", default="http://127.0.0.1:8000")
    ap.add_argument("--date", default=default_date(), help="日期目录（默认 Asia/Shanghai 06:00 换日）")
    ap.add_argument("--voices", default=",".join(v for v, _ in VOICES), help="逗号分隔的声音 id")
    ap.add_argument("--from-json", help="本地文章 JSON（列表或 {articles:[...]}），代替 API")
    ap.add_argument("--limit-articles", type=int, default=0)
    ap.add_argument("--max-sentences", type=int, default=0, help="调试：每篇最多合成前 N 句")
    ap.add_argument("--out", type=Path, default=HERE / "out")
    args = ap.parse_args()

    voices = [v.strip() for v in args.voices.split(",") if v.strip()]
    bad = [v for v in voices if v not in dict(VOICES)]
    if bad:
        ap.error(f"未知声音 {bad}，可选：{[v for v, _ in VOICES]}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        ap.error(f"--date 需要 YYYY-MM-DD，收到 {args.date}")

    articles = load_articles(args.api_base.rstrip("/"), args.date, args.from_json, args.limit_articles)
    if not articles:
        raise SystemExit("没有可合成的文章")

    day_dir = args.out / args.date
    cache = args.out / "cache"
    cache.mkdir(parents=True, exist_ok=True)

    synth = Synth()
    if "jianwen" in voices and not synth.ref:
        log("缺克隆参考音频，跳过 jianwen，其余声音照常生成")
        voices = [v for v in voices if v != "jianwen"]
        if not voices:
            raise SystemExit("没有可用的声音")

    timing = []
    entries, failed = [], 0
    t_start = time.time()
    for pos, art in enumerate(articles):
        aid = art.get("article_id") or art.get("id")
        if not aid:
            log("跳过没有 article_id 的条目")
            continue
        sentences = build_sentences(art, args.max_sentences or None)
        log(f"[{pos + 1}/{len(articles)}] {aid} 共 {len(sentences)} 句 / {sum(len(t) for t, _ in sentences)} 字")
        audio = {}
        for voice in voices:
            mp3 = day_dir / aid / f"{voice}.mp3"
            keyfile = day_dir / aid / f".{voice}.key"
            key = hashlib.sha256(json.dumps(
                dict(v=VERSION, post=POST_VERSION, af=post_filter(voice), voice=voice, sents=sentences), ensure_ascii=False).encode()).hexdigest()
            try:
                if mp3.exists() and keyfile.exists() and keyfile.read_text() == key:
                    log(f"    {voice} 命中缓存 {mp3.name}")
                else:
                    spent, n = make_mp3(sentences, voice, synth, cache, mp3, timing)
                    keyfile.write_text(key)
                    log(f"    {voice} 完成 {n} 句合成 {spent:.1f}s → {mp3}")
                st = probe_stream(mp3)
                audio[voice] = {"url": f"/uploads/tts/{args.date}/{aid}/{voice}.mp3",
                                "duration": round(probe_duration(mp3), 1)}
                log(f"    {voice} {audio[voice]['duration']}s "
                    f"{st.get('sample_rate')}Hz {st.get('channels')}ch {st.get('bit_rate')}bps")
            except Exception as exc:  # 单个声音失败只记日志，不中断整体
                failed += 1
                traceback.print_exc()
                log(f"    {voice} 失败：{type(exc).__name__}: {exc}")
        if audio:
            entries.append({"article_id": aid, "title": art.get("title") or "",
                            "position": pos, "audio": audio})

    manifest = {
        "date": args.date,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "voices": [{"id": v, "label": l} for v, l in VOICES if v in voices],
        "articles": entries,
    }
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    elapsed = time.time() - t_start
    total_chars = sum(c for c, _ in timing)
    avg = (sum(d for _, d in timing) / len(timing)) if timing else 0.0
    log(f"完成：{len(entries)} 篇 / {len(timing)} 句新合成 / 失败 {failed} 个声音 / 总 {elapsed:.1f}s")
    if timing:
        log(f"实测：平均每句 {avg:.2f}s（{total_chars} 字，{total_chars / max(sum(d for _, d in timing), .01):.1f} 字/秒）")
        # 整篇估算：一篇≈62 句，一天 5 篇，4 个声音
        n_sent = len(build_sentences(articles[0]))
        log(f"预估整篇（按 {n_sent} 句 × 4 声音）：{n_sent * 4 * avg / 60:.1f} 分钟；"
            f"全天 5 篇：{5 * n_sent * 4 * avg / 60:.0f} 分钟（首次无缓存）")
    print(f"manifest → {day_dir / 'manifest.json'}", flush=True)
    if failed and not entries:
        raise SystemExit(1)


if __name__ == "__main__":
    ensure_runtime()
    main()
