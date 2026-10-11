"""见闻宣传片 v4：30 秒卡点版。固定网格 + 实色标题块 + 图标 + 背景动态，修正 v2 的空洞和跑版。

复用 v2 的录屏解码、贴图、模糊、冲击抖动等工具；版式全部走 layout.py 的网格。
用法: python3 promo/v4/compose.py [--preview]
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import importlib.util  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
# v2 的模块也叫 compose.py，按路径加载避免和本文件重名
_spec = importlib.util.spec_from_file_location("compose_v2", Path(__file__).resolve().parents[1] / "v2/compose.py")
v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2)
from layout import (BLUE, CAPTION_Y, DEEP, GOLD, INK, MAIN_BOTTOM, MAIN_TOP, MIST, PAPER, TEAL, H, W,  # noqa: E402
                    background, chips, clamp, ease_out_back, ease_out_expo, font, icon, paste, progress_dots,
                    spring, title_block)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/promo-video/v4"
FPS, DUR = 30, 30.0
VOICE = "zh-CN-YunjianNeural"


def main_card(base, clip, t_src, crop, x_off=0.0, angle=0.0, zoom=1.0, radius=40, max_h=None):
    """主画面卡片：等比缩放填满主画面区，卡片外加金色描边和投影"""
    scr = v2.screen(clip, t_src, crop=crop, radius=radius)
    framed = Image.new("RGBA", (scr.width + 16, scr.height + 16), (0, 0, 0, 0))
    ImageDraw.Draw(framed).rounded_rectangle((0, 0, framed.width - 1, framed.height - 1), radius + 8, fill=(*INK, 255))
    framed.paste(scr, (8, 8), scr)
    scr = framed
    box_w, box_h = 940, max_h or (MAIN_BOTTOM - MAIN_TOP)
    s = min(box_w / scr.width, box_h / scr.height) * zoom
    cx = W / 2 + x_off
    cy = (MAIN_TOP + MAIN_BOTTOM) / 2
    v2.place(base, scr, cx, cy, scale=s, angle=angle, shadow=36)
    return base


def badge(base, name, x, y, t, dark, delay=0.0, size=96):
    """主画面两侧的浮动图标徽章：弹入后轻微上下浮动"""
    k = ease_out_back(clamp((t - delay) / 0.35), 1.6)
    if k <= 0:
        return
    bob = 8 * np.sin(2 * np.pi * (t * 0.8 + delay))
    s = int(size * k)
    if s < 4:
        return
    disc = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(disc).ellipse((0, 0, s - 1, s - 1), fill=(*GOLD, 255))
    ic = icon(name, int(s * 0.52), INK)
    if ic is not None:
        disc.paste(ic, (int(s * 0.24), int(s * 0.24)), ic)
    base.paste(disc, (int(x - s / 2), int(y - s / 2 + bob)), disc)
CLIPS = {}


def clip(name):
    if name not in CLIPS:
        CLIPS[name] = v2.Clip(name)
    return CLIPS[name]


def s_hook(t, d):
    """0–4s 深色钩子：问题标题块 + 真实 AI 回答卡片推入"""
    img = background(True, t, 0)
    title_block(img, "青年就业支持计划", ["和你", "有关系吗？"], t, True, "message-circle-question-mark")
    k = ease_out_expo(clamp((t - 0.45) / 0.45))
    if k > 0:
        main_card(img, clip("ask-dark"), 5.6 + max(0, t - 0.5) * 1.2, (0, 300, 780, 1150),
                  x_off=(1 - k) * 1100, angle=-5 * (1 - k), zoom=0.92 + 0.06 * clamp((t - 0.9) / 3.1))
        img = v2.motion_blur(img, (1 - k) * 100, vertical=False)
        badge(img, "bot", 150, MAIN_TOP + 40, t, True, delay=0.8)
        badge(img, "sparkles", W - 150, MAIN_BOTTOM - 60, t, True, delay=0.95, size=80)
    chips(img, [("shield-check", "带依据回答"), ("zap", "流式生成")], t, True, start=1.0)
    return v2.impact(img, t, [0.06, 0.18, 0.95], zoom=0.02)


def s_beats(t, d):
    """4–8s 深色：4 拍关键词，每拍一个实色块砸入，卡片在下方持续滚动"""
    img = background(True, t + 4, 0)
    words = [("先分清", INK, GOLD), ("方向", PAPER, BLUE), ("不等于", INK, GOLD), ("到手的钱", PAPER, BLUE)]
    i = min(3, int(t / 1.0))
    lt = t - i * 1.0
    label, txt_c, blk_c = words[i]
    dr = ImageDraw.Draw(img)
    ic = icon("target", 52, TEAL)
    paste(img, ic, 88, 266)
    dr.text((154, 292), "AI 先帮你拆清楚", font=font("Bold", 40), fill=TEAL, anchor="lm")
    f = font("Heavy", 150)
    tw = dr.textlength(label, font=f)
    s = 1.35 - 0.35 * spring(clamp(lt / 0.35))
    blk = Image.new("RGBA", (int(tw) + 96, 220), (*blk_c, 255))
    ImageDraw.Draw(blk).text((48, 110), label, font=f, fill=txt_c, anchor="lm")
    v2.place(img, blk, W / 2, 480, scale=s)
    main_card(img, clip("ask-dark"), 6.6 + t * 0.6, (0, 260, 780, 1150), zoom=0.9)
    chips(img, [("list-checks", f"第 {i + 1} 点"), ("file-check", "来自资料库")], 1.0, True, start=0)
    img = v2.impact(img, t, [0.0, 1.0, 2.0, 3.0], zoom=0.02)
    return v2.flash(img, 0.35 * (1 - lt / 0.08)) if lt < 0.08 else img


def s_drop(t, d):
    """8–10s drop：白闪切浅色，品牌大字块 + 手机落位 + 图标环绕"""
    img = background(False, t, 1)
    dr = ImageDraw.Draw(img)
    k = ease_out_expo(t / 0.5)
    blk = Image.new("RGBA", (620, 250), (*INK, 255))
    ImageDraw.Draw(blk).text((310, 125), "见闻", font=font("Heavy", 200), fill=PAPER, anchor="mm")
    v2.place(img, blk, W / 2, 400, scale=1.5 - 0.5 * spring(clamp(t / 0.45)))
    gold = Image.new("RGBA", (760, 84), (*GOLD, 255))
    ImageDraw.Draw(gold).text((380, 42), "每天 5 件事 · 看懂和你有关的变化", font=font("Bold", 40), fill=INK, anchor="mm")
    v2.place(img, gold, W / 2 - (1 - ease_out_expo(clamp((t - 0.15) / 0.3))) * 1200, 570)
    main_card(img, clip("today"), 0.3 + t, (0, 40, 780, 1000), zoom=0.92 + 0.6 * (1 - k), angle=-6 * (1 - k))
    for j, (n, x, y) in enumerate([("newspaper", 140, 800), ("calendar-check", W - 140, 880), ("trending-up", 150, 1320), ("layers", W - 150, 1280)]):
        badge(img, n, x, y, t, False, delay=0.25 + j * 0.08, size=88)
    chips(img, [("newspaper", "今日 5 件"), ("calendar-check", "每天 06:00 更新")], t, False, start=0.5)
    return v2.flash(img, 1 - t / 0.18)


def feature(clip_name, label, lines, icon_name, dark, crop, start, speed, chip_items, badges, swing=1, max_h=None):
    def shot(t, d):
        img = background(dark, t, 2 if dark else 3)
        title_block(img, label, lines, t, dark, icon_name)
        k = ease_out_expo(t / 0.35)
        main_card(img, clip(clip_name), start + t * speed, crop, x_off=swing * (1 - k) * 1200,
                  angle=swing * -5 * (1 - k), zoom=0.94 + 0.06 * clamp(t / d), max_h=max_h)
        img = v2.motion_blur(img, (1 - k) * 110, vertical=False)
        for j, (n, x, y) in enumerate(badges):
            badge(img, n, x, y, t, dark, delay=0.3 + j * 0.1, size=84)
        chips(img, chip_items, t, dark, start=0.35)
        return img
    return shot
def s_web_mobile(t, d):
    """手机浏览器打开网页版：深色背景上的浏览器手机框"""
    img = background(True, t, 4)
    title_block(img, "手机浏览器也能看", ["网页版", "随手打开"], t, True, "smartphone")
    k = ease_out_back(clamp(t / 0.45), 1.2)
    scr = v2.screen(clip("web-mobile"), 1.6 + t * 1.4, crop=(0, 0, 780, 1450), radius=40)
    s = (MAIN_BOTTOM - MAIN_TOP) / scr.height * 0.98
    v2.place(img, scr, W / 2 + (1 - k) * 900, (MAIN_TOP + MAIN_BOTTOM) / 2, scale=s * (0.6 + 0.4 * k), angle=8 * (1 - k), shadow=36)
    badge(img, "link", 200, MAIN_TOP + 80, t, True, delay=0.35)
    badge(img, "book-open", W - 200, MAIN_BOTTOM - 100, t, True, delay=0.45)
    chips(img, [("smartphone", "手机浏览器"), ("link", "无需安装")], t, True, start=0.4)
    return img


def s_sync(t, d):
    """浅色：电脑 + 手机同进度，两张卡片对撞"""
    img = background(False, t, 5)
    title_block(img, "电脑网页版", ["大屏读", "进度存账号"], t, False, "monitor")
    k = ease_out_back(clamp(t / 0.5), 1.3)
    web = v2.screen(clip("web"), 4.0 + t, radius=18)
    v2.place(img, web, W / 2 - 60 - (1 - k) * 1200, 900, scale=900 / web.width, shadow=30)
    ph = v2.screen(clip("discover"), 9.0 + t * 0.4)
    v2.place(img, ph, W / 2 + 270 + (1 - k) * 900, 1180, scale=0.42, angle=5 * (1 - k), shadow=30)
    chips(img, [("monitor", "电脑网页"), ("layers", "登录后同步位置")], t, False, start=0.4)
    return img


def s_ajin(t, d):
    # 渲染帧放大 1.14 倍并上移，让阿烬主体紧贴标题区下沿，减少中间空档
    src = v2.render_frame("ajin_dark", int(t * FPS) + 30)
    z = 1.14
    big = src.resize((int(W * z), int(H * z)), Image.BICUBIC)
    x0 = (big.width - W) // 2
    y0 = int((big.height - H) / 2 + 150)
    img = big.crop((x0, y0, x0 + W, y0 + H))
    title_block(img, "唯一硬件", ["阿烬", "陪你想清楚"], t, True, "bot")
    chips(img, [("sparkles", "AI 陪伴"), ("message-circle-question-mark", "随时追问")], t, True, start=0.5)
    return img


def s_outro(t, d):
    img = background(False, t, 6)
    dr = ImageDraw.Draw(img)
    blk = Image.new("RGBA", (620, 250), (*INK, 255))
    ImageDraw.Draw(blk).text((310, 125), "见闻", font=font("Heavy", 200), fill=PAPER, anchor="mm")
    v2.place(img, blk, W / 2, 560, scale=1.3 - 0.3 * spring(clamp(t / 0.45)))
    dr.text((W // 2, 750), "JIANWEN", font=font("Medium", 36), fill=BLUE, anchor="ma")
    dr.rectangle((W // 2 - 44, 812, W // 2 + 44, 818), fill=GOLD)
    a = clamp((t - 0.25) / 0.3)
    for i, line in enumerate(("以政策照见时代", "以思考丰盈灵魂")):
        dr.text((W // 2, 870 + i * 78), line, font=font("Regular", 50), fill=tuple(int(c * a + 237 * (1 - a)) for c in INK), anchor="ma")
    for j, n in enumerate(("newspaper", "message-circle-question-mark", "book-open", "smartphone", "monitor")):
        badge(img, n, 220 + j * 160, 1150, t, False, delay=0.4 + j * 0.07, size=112)
    if t > 0.8:
        b = ease_out_back((t - 0.8) / 0.4)
        btn = Image.new("RGBA", (680, 120), (0, 0, 0, 0))
        bd = ImageDraw.Draw(btn)
        bd.rounded_rectangle((0, 0, 679, 119), 60, fill=BLUE)
        ic = icon("search", 52, PAPER)
        if ic is not None:
            btn.paste(ic, (56, 34), ic)
        bd.text((380, 60), "搜索「见闻」开始阅读", font=font("Bold", 44), fill=PAPER, anchor="mm")
        v2.place(img, btn, W / 2, 1340, scale=b)
    return v2.flash(img, 1 - t / 0.15)


def dynamic(fn, push=0.07, whip=True, direction=1):
    """给镜头加两层运动：全程缓推 + 轻微摆动；最后 0.18 秒横向甩出带运动模糊，衔接下一个镜头"""
    def shot(t, d):
        img = fn(t, d)
        u = clamp(t / d)
        z = 1 + push * u
        ang = 1.2 * np.sin(2 * np.pi * u) * direction
        big = img.resize((int(W * z), int(H * z)), Image.BICUBIC).rotate(ang, resample=Image.BICUBIC)
        x0, y0 = (big.width - W) // 2, (big.height - H) // 2
        img = big.crop((x0, y0, x0 + W, y0 + H))
        tail = t - (d - 0.18)
        if whip and tail > 0:
            e = (tail / 0.18) ** 2
            shift = int(direction * e * 700)
            moved = Image.new("RGB", (W, H), img.getpixel((4, 4)))
            moved.paste(img, (-shift, 0))
            img = v2.motion_blur(moved, e * 160, vertical=False)
        return img
    return shot


def timeline():
    BL, BR = (130, MAIN_TOP + 60), (W - 130, MAIN_BOTTOM - 80)
    raw = [
        (0.0, 4.0, s_hook),
        (4.0, 4.0, s_beats),
        (8.0, 2.0, s_drop),
        (10.0, 2.5, feature("today", "今日", ["5 件事", "几分钟看懂"], "newspaper", False, (0, 40, 780, 1150), 0.0, 0.5,
                            [("newspaper", "重点简报"), ("trending-up", "理解进度")], [("calendar-check", *BL), ("zap", *BR)], 1)),
        (12.5, 2.5, feature("article-dark", "文章", ["先看", "三句结论"], "quote", True, (0, 40, 780, 1150), 2.5, 0.6,
                            [("list-checks", "三句话总结"), ("target", "影响范围")], [("quote", *BL), ("sparkles", *BR)], -1)),
        (15.0, 2.0, feature("article", "依据", ["来源", "可查"], "shield-check", False, (0, 620, 780, 1050), 9.6, 0.3,
                            [("shield-check", "官方来源"), ("link", "原文链接")], [("file-check", *BL), ("link", *BR)], 1)),
        (17.0, 2.5, s_web_mobile),
        (19.5, 2.5, feature("discover", "经典阅读", ["读原文", "翻页即读"], "book-open", False, (0, 120, 780, 1150), 8.0, 0.8,
                            [("book-open", "党章团章"), ("layers", "分页阅读")], [("book-open", *BL), ("search", *BR)], -1)),
        (22.0, 2.5, s_sync),
        (24.5, 3.0, s_ajin),
        (27.5, 2.5, s_outro),
    ]
    out = []
    for i, (a, d, fn) in enumerate(raw):
        last = i == len(raw) - 1
        # beats 镜头自带逐拍冲击，缓推幅度小一些；片尾不甩出
        out.append((a, d, dynamic(fn, push=0.03 if fn is s_beats else 0.07, whip=not last, direction=1 if i % 2 == 0 else -1)))
    return out
def load_captions():
    """每句旁白按标点拆成短句逐段出现；时长取 edge-tts VTT 的起止，按字数分配"""
    caps = []
    for line in (ROOT / "promo/v4/lines.txt").read_text().splitlines():
        if "|" not in line:
            continue
        key, at, txt = line.split("|", 2)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(OUT / f"tts/{key}.wav")], capture_output=True, text=True).stdout)
        parts = [p.strip("，。？！：") for p in re.split(r"(?<=[，。？！：])", txt) if p.strip("，。？！： ")]
        total = sum(len(p) for p in parts)
        t0 = float(at)
        for p in parts:
            d = dur * len(p) / total
            caps.append((t0, t0 + d + 0.08, p, key))
            t0 += d
    return caps


def draw_caption(img, t, caps, dark):
    for a, b, txt, _ in caps:
        if a <= t < b:
            k = ease_out_expo((t - a) / 0.15)
            f = font("Bold", 56)
            d = ImageDraw.Draw(img)
            tw = d.textlength(txt, font=f)
            layer = Image.new("RGBA", (int(tw) + 72, 100), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.rounded_rectangle((0, 0, layer.width - 1, 99), 24, fill=(*(PAPER if dark else INK), 240))
            ld.text((36, 50), txt, font=f, fill=INK if dark else PAPER, anchor="lm")
            x = min(W / 2, W * 0.86 - layer.width / 2 - 8)
            v2.place(img, layer, x, CAPTION_Y + (1 - k) * 24, alpha=k)
    return img


def main():
    preview = "--preview" in sys.argv
    only = [float(a) for a in sys.argv[1:] if re.fullmatch(r"[0-9.]+", a)]
    shots = timeline()
    cuts = [s for s, _, _ in shots]
    caps = load_captions()
    OUT.mkdir(parents=True, exist_ok=True)
    if only:
        # 指定时间点：只导出单帧 PNG，用于版式检查
        for t in only:
            for i, (s, d, fn) in enumerate(shots):
                if s <= t < s + d:
                    img = fn(t - s, d)
                    progress_dots(img, i, len(shots), np.asarray(img.resize((54, 96))).mean() < 128)
                    draw_caption(img, t, caps, np.asarray(img.resize((54, 96))).mean() < 128)
                    img.save(OUT / f"frame_{t:05.2f}.png")
        return
    step = 2 if preview else 1
    size = (W // 2, H // 2) if preview else (W, H)
    # --part i/n：只渲染第 i 段（共 n 段），多进程并行后再用 concat 拼接
    part = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--part=")), None)
    first, last = 0, int(DUR * FPS)
    if part:
        i, n = map(int, part.split("/"))
        first, last = last * i // n, last * (i + 1) // n
    out = OUT / (f"part_{part.replace('/', 'of')}.mp4" if part else ("picture_preview.mp4" if preview else "picture.mp4"))
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
                           "-r", str(FPS // step), "-i", "-", "-c:v", "libx264", "-crf", "23" if preview else "16",
                           "-preset", "medium", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    total = int(DUR * FPS)
    for n in range(first, last, step):
        t = n / FPS
        for i, (s, d, fn) in enumerate(shots):
            if s <= t < s + d:
                img = fn(t - s, d)
                idx = i
                break
        dark = np.asarray(img.resize((54, 96))).mean() < 128
        progress_dots(img, idx, len(shots), dark)
        img = v2.flash(img, v2.cut_flash(t, cuts))
        img = draw_caption(img, t, caps, dark)
        if preview:
            img = img.resize(size, Image.BILINEAR)
        ff.stdin.write(img.convert("RGB").tobytes())
        if n % 150 == 0:
            print(f"frame {n}/{total}", flush=True)
    ff.stdin.close()
    ff.wait()
    print(out)


if __name__ == "__main__":
    main()
