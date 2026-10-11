"""见闻宣传片 v2：30 秒快节奏卡点版，深浅色交替，大幅度动效。

逐帧合成（numpy + Pillow），每个镜头是一个函数 shot(t_local, dur) -> RGB Image，
时间轴按《雨》117.5 BPM 拍点（0.5 秒一拍，8.0 秒 drop）排布。输出 PNG 管道给 ffmpeg。
用法: python3 promo/v2/compose.py [--preview]   （--preview 半分辨率、每 2 帧取 1）
"""
import json
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
V = ROOT / "output/promo-video"
CAP = V / "capture"
RENDER = V / "render"
FONTS = V / "fonts/SubsetOTF/CN"
OUT = V / "v2"
W, H, FPS, DUR = 1080, 1920, 30, 30.0

INK = (20, 33, 43)
DEEP = (8, 14, 20)
BLUE = (31, 95, 122)
TEAL = (126, 184, 209)
GOLD = (212, 170, 78)
PAPER = (245, 247, 244)
MIST = (237, 245, 247)

MARKS = json.loads((CAP / "marks.json").read_text())


# ---------- 缓动 ----------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_expo(x):
    x = clamp(x)
    return 1 if x == 1 else 1 - 2 ** (-10 * x)


def ease_in_out_cubic(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=1.7):
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def spring(x, freq=4.5, damp=6.0):
    """0→1 带过冲的弹簧，用于标题砸入"""
    x = clamp(x)
    return 1 - math.exp(-damp * x) * math.cos(2 * math.pi * freq * x)


# ---------- 素材 ----------
@lru_cache(maxsize=None)
def font(weight, size):
    return ImageFont.truetype(str(FONTS / f"SourceHanSansCN-{weight}.otf"), size)


class Clip:
    """顺序解码录屏视频；按时间取帧，缓存最近一帧"""

    def __init__(self, name):
        self.name = name
        self.cut_in = MARKS[name]["cut_in"]
        self.path = CAP / f"{name}.mp4"
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height", "-of", "csv=p=0", str(self.path)], capture_output=True, text=True)
        self.w, self.h = map(int, probe.stdout.strip().split(","))
        self.frames = {}

    def at(self, t):
        """t 为从 cut_in 起的秒数"""
        idx = max(0, int(round((self.cut_in + t) * FPS)))
        if idx not in self.frames:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{idx / FPS:.3f}", "-i", str(self.path),
                                  "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 capture_output=True).stdout
            if len(raw) < self.w * self.h * 3:
                return self.at(t - 1 / FPS)
            if len(self.frames) > 90:
                self.frames.clear()
            self.frames[idx] = Image.frombytes("RGB", (self.w, self.h), raw[: self.w * self.h * 3])
        return self.frames[idx]


@lru_cache(maxsize=None)
def render_frame(shot, n):
    files = sorted((RENDER / shot).glob("f_*.png"))
    return Image.open(files[min(n, len(files) - 1)]).convert("RGB")
# ---------- 画面工具 ----------
def canvas(color):
    return Image.new("RGB", (W, H), color)


def grain(img, amount=6, seed=0):
    """细噪点，避免大色块显得廉价"""
    rng = np.random.default_rng(seed)
    a = np.asarray(img).astype(np.int16)
    a = a + rng.integers(-amount, amount + 1, size=(H, W, 1), dtype=np.int16)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def place(base, img, cx, cy, scale=1.0, angle=0.0, alpha=1.0, shadow=0):
    """把 img 按中心点、缩放、旋转贴到 base 上"""
    if scale <= 0.01 or alpha <= 0.01:
        return base
    w, h = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    im = img.resize((w, h), Image.BICUBIC).convert("RGBA")
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im.putalpha(a)
    x, y = int(cx - im.width / 2), int(cy - im.height / 2)
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.45)))
        sh = sh.filter(ImageFilter.GaussianBlur(shadow))
        base.paste(sh, (x + shadow // 3, y + shadow), sh)
    base.paste(im, (x, y), im)
    return base


def rounded_mask(size, r):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=255)
    return m


def screen(clip, t, crop=None, radius=56):
    """录屏帧裁成圆角屏幕卡片；crop=(x,y,w,h) 为原始帧坐标"""
    im = clip.at(t)
    if crop:
        x, y, w, h = crop
        im = im.crop((x, y, x + w, y + h))
    im = im.convert("RGBA")
    im.putalpha(rounded_mask(im.size, int(radius * im.width / 780)))
    return im


def motion_blur(img, strength, vertical=True):
    """快速位移时的方向模糊：把图像沿运动方向平均几次"""
    if strength < 2:
        return img
    a = np.asarray(img).astype(np.float32)
    acc = np.zeros_like(a)
    n = 7
    for i in range(n):
        d = int((i - n // 2) * strength / n)
        acc += np.roll(a, d, axis=0 if vertical else 1)
    return Image.fromarray((acc / n).astype(np.uint8))


def text(draw, xy, s, size, weight="Bold", fill=PAPER, anchor="la", spacing=0):
    f = font(weight, size)
    if spacing:
        x, y = xy
        for ch in s:
            draw.text((x, y), ch, font=f, fill=fill, anchor=anchor)
            x += draw.textlength(ch, font=f) + spacing
    else:
        draw.text(xy, s, font=f, fill=fill, anchor=anchor)


def slam_text(base, lines, t, color, size=150, weight="Heavy", y0=760, stagger=0.12, accent=None):
    """逐行砸入：从 1.6 倍缩到 1 倍并带弹簧过冲，同时淡入"""
    for i, line in enumerate(lines):
        lt = t - i * stagger
        if lt <= 0:
            continue
        k = clamp(lt / 0.35)
        s = 1.6 - 0.6 * spring(k, freq=2.2, damp=7)
        f = font(weight, size)
        tw = int(ImageDraw.Draw(base).textlength(line, font=f)) + 20
        layer = Image.new("RGBA", (tw, int(size * 1.4)), (0, 0, 0, 0))
        fill = accent if (accent and i == len(lines) - 1) else color
        ImageDraw.Draw(layer).text((10, 0), line, font=f, fill=fill)
        place(base, layer, W / 2, y0 + i * size * 1.25 + size * 0.6, scale=s, alpha=clamp(k * 2.5))
    return base


def flash(img, amount):
    """白闪：卡在 drop 和重拍上"""
    if amount <= 0:
        return img
    return Image.blend(img, canvas((255, 255, 255)), clamp(amount))
# ---------- 镜头 ----------
# 每个镜头: (起点秒, 时长秒, 函数)。拍点 0.5 秒一拍，8.0 秒是 drop。
ASK_D = TODAY_D = ART_D = ASK_L = TODAY_L = ART_L = DISC = WEB = None


def load_clips():
    global ASK_D, TODAY_D, ART_D, ASK_L, TODAY_L, ART_L, DISC, WEB
    ASK_D, TODAY_D, ART_D = Clip("ask-dark"), Clip("today-dark"), Clip("article-dark")
    ASK_L, TODAY_L, ART_L = Clip("ask"), Clip("today"), Clip("article")
    DISC, WEB = Clip("discover"), Clip("web")


def impact(img, t, hits, zoom=0.0):
    """整帧缓推 + 冲击抖动：hits 为冲击时刻列表"""
    dx = dy = 0.0
    for h in hits:
        u = t - h
        if 0 <= u < 0.4:
            amp = 26 * math.exp(-11 * u)
            dx += amp * math.sin(70 * u)
            dy += amp * 0.6 * math.cos(55 * u)
    s = 1 + zoom
    if s == 1 and not dx and not dy:
        return img
    big = img.resize((int(W * s), int(H * s)), Image.BICUBIC)
    x0 = int((big.width - W) / 2 - dx)
    y0 = int((big.height - H) / 2 - dy)
    x0, y0 = max(0, min(big.width - W, x0)), max(0, min(big.height - H, y0))
    if big.width == W:
        out = canvas(img.getpixel((5, 5)))
        out.paste(img, (int(dx), int(dy)))
        return out
    return big.crop((x0, y0, x0 + W, y0 + H))


def s_hook(t, d):
    """0–2s 深色：问题砸字，最后一行金色"""
    img = canvas(DEEP)
    dr = ImageDraw.Draw(img)
    # 左上角细标签，0.1 秒内出现
    text(dr, (88, 300), "青年就业支持计划", 40, "Medium", fill=TEAL)
    slam_text(img, ["和你", "有关系吗？"], t - 0.05, PAPER, size=170, y0=720, stagger=0.5, accent=GOLD)
    # 底部扫描线进度，制造"马上揭晓"的紧张感
    dr.rectangle((88, 1340, 88 + int(904 * clamp(t / d)), 1346), fill=GOLD)
    img = impact(img, t, [0.12, 0.62], zoom=0.06 * t / d + 0.02)
    return grain(img, 5, int(t * FPS))


def s_ask_type(t, d):
    """2–4s 深色问问：手机从下方甩入，镜头推到输入框"""
    img = canvas(DEEP)
    k = ease_out_expo(t / 0.45)
    y = H / 2 + (1 - k) * 1500
    scr = screen(ASK_D, 1.2 + t * 1.6)
    scale = 1.02 + 0.35 * ease_in_out_cubic(t / d)
    # 推近时把焦点往下移到输入框区域
    cy = y - 260 * ease_in_out_cubic(t / d)
    img = place(img, scr, W / 2, cy, scale=scale, shadow=40)
    return motion_blur(img, (1 - k) * 90)


def s_answer(t, d):
    """4–8s 深色：回答流式出现，镜头沿回答缓慢上推，金句放大"""
    img = canvas(DEEP)
    scr = screen(ASK_D, 5.6 + t * 0.9)
    k = ease_in_out_cubic(t / d)
    img = place(img, scr, W / 2, H / 2 + 120 - 260 * k, scale=1.25 + 0.25 * k, shadow=30)
    # 上方压暗渐变，给标签留位置
    top = Image.new("L", (1, H))
    top.putdata([int(235 * clamp(1 - y / 620)) for y in range(H)])
    img.paste(canvas(DEEP), (0, 0), top.resize((W, H)))
    dr = ImageDraw.Draw(img)
    text(dr, (88, 270), "AI 问问 · 带依据回答", 40, "Medium", fill=TEAL)
    # 6–8s 的 4 拍逐拍闪出关键词，节奏逼近 drop
    words = ["先分清", "方向", "不是", "到手的钱"]
    if t >= 2.0:
        i = min(3, int((t - 2.0) / 0.5))
        s = 1.25 - 0.25 * ease_out_expo(((t - 2.0) % 0.5) / 0.25)
        layer = Image.new("RGBA", (980, 200), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((490, 100), words[i], font=font("Heavy", 128), fill=GOLD if i == 3 else PAPER, anchor="mm")
        place(img, layer, W / 2, 470, scale=s)
        img = impact(img, t, [2.0, 2.5, 3.0, 3.5], zoom=0.03)
    return img


def s_drop(t, d):
    """8–10s drop：白闪切浅色，品牌大字 + 手机从大到小落位"""
    img = canvas(MIST)
    k = ease_out_expo(t / 0.6)
    scr = screen(TODAY_L, 0.2 + t)
    img = place(img, scr, W / 2, 1150 + (1 - k) * 200, scale=1.9 - 0.95 * k, angle=-8 * (1 - k), shadow=36)
    dr = ImageDraw.Draw(img)
    layer = Image.new("RGBA", (1000, 300), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((500, 150), "见闻", font=font("Heavy", 230), fill=INK, anchor="mm")
    place(img, layer, W / 2, 470, scale=1.0 + 0.5 * (1 - spring(clamp(t / 0.5), 2, 7)))
    text(dr, (W // 2, 640), "每天 5 件事 · 看懂和你有关的变化", 44, "Medium", fill=BLUE, anchor="ma")
    return flash(img, 1 - t / 0.18)
def feature(clip, label, title, dark, crop=None, start=0.0, speed=1.0, swing=1):
    """功能镜头模板：甩入手机 + 推近局部 + 顶部标签和标题逐字砸入"""
    bg, fg, sub = (DEEP, PAPER, TEAL) if dark else (MIST, INK, BLUE)

    def shot(t, d):
        img = canvas(bg)
        k = ease_out_expo(t / 0.35)
        # 横向甩入，方向交替
        x = W / 2 + swing * (1 - k) * 1300
        z = ease_in_out_cubic(t / d)
        scr = screen(clip, start + t * speed, crop=crop, radius=36)
        base = 1000 / scr.width
        img = place(img, scr, x, 1010 - 40 * z, scale=base * (1.0 + 0.1 * z), angle=swing * -4 * (1 - k), shadow=34)
        img = motion_blur(img, (1 - k) * 110, vertical=False)
        dr = ImageDraw.Draw(img)
        text(dr, (88, 280), label, 38, "Medium", fill=sub)
        dr.rectangle((88, 336, 88 + int(64 * k), 342), fill=GOLD)
        slam_text(img, [title], t - 0.08, fg, size=104, weight="Heavy", y0=360)
        return img

    return shot


def s_split(t, d):
    """手机 + 网页同进度：两张卡片对撞"""
    img = canvas(DEEP)
    k = ease_out_back(t / 0.5, 1.3)
    web = screen(WEB, 4.0 + t, radius=20)
    ph = screen(DISC, 9.0 + t * 0.5)
    img = place(img, web, W / 2 - (1 - k) * 1200, 860, scale=1000 / web.width, shadow=30)
    img = place(img, ph, W / 2 + 270 + (1 - k) * 900, 1150, scale=0.42, angle=6 * (1 - k), shadow=30)
    dr = ImageDraw.Draw(img)
    text(dr, (88, 280), "手机 + 网页", 38, "Medium", fill=TEAL)
    slam_text(img, ["同一份进度"], t - 0.08, PAPER, size=104, y0=360)
    return img


def s_ajin(t, d):
    """阿烬：Blender 深色转台，灯亮起时金色标题"""
    n = int(t * FPS) + 30  # 跳过熄灯的前 1 秒
    img = render_frame("ajin_dark", n).copy()
    dr = ImageDraw.Draw(img)
    text(dr, (88, 280), "唯一硬件 · 阿烬", 38, "Medium", fill=GOLD)
    slam_text(img, ["陪你把问题", "想清楚"], t - 0.2, PAPER, size=100, y0=360, stagger=0.25, accent=GOLD)
    return img


def s_outro(t, d):
    """片尾浅色：品牌 + 口号 + 行动引导"""
    img = canvas(PAPER)
    dr = ImageDraw.Draw(img)
    layer = Image.new("RGBA", (900, 300), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((450, 150), "见闻", font=font("Heavy", 210), fill=INK, anchor="mm")
    place(img, layer, W / 2, 720, scale=1.25 - 0.25 * spring(clamp(t / 0.5), 2, 7))
    text(dr, (W // 2, 890), "JIANWEN", 36, "Medium", fill=BLUE, anchor="ma")
    dr.rectangle((W // 2 - 44, 950, W // 2 + 44, 956), fill=GOLD)
    a = clamp((t - 0.3) / 0.3)
    for i, line in enumerate(("以政策照见时代", "以思考丰盈灵魂")):
        text(dr, (W // 2, 1000 + i * 76), line, 50, "Regular", fill=tuple(int(c * a + 245 * (1 - a)) for c in INK), anchor="ma")
    # 行动引导按钮
    if t > 0.8:
        b = ease_out_back((t - 0.8) / 0.4)
        btn = Image.new("RGBA", (620, 120), (0, 0, 0, 0))
        bd = ImageDraw.Draw(btn)
        bd.rounded_rectangle((0, 0, 619, 119), 60, fill=BLUE)
        bd.text((310, 60), "搜索「见闻」开始阅读", font=font("Bold", 46), fill=PAPER, anchor="mm")
        place(img, btn, W / 2, 1280, scale=b)
    return flash(img, 1 - t / 0.15)


def timeline():
    return [
        (0.0, 2.0, s_hook),
        (2.0, 2.0, s_ask_type),
        (4.0, 4.0, s_answer),
        (8.0, 2.0, s_drop),
        (10.0, 2.5, feature(TODAY_L, "今日", "5 件事", dark=False, crop=(0, 60, 780, 720), start=0.0, speed=0.5, swing=1)),
        (12.5, 2.5, feature(ART_D, "文章", "先看结论", dark=True, crop=(0, 90, 780, 720), start=2.5, speed=0.6, swing=-1)),
        (15.0, 2.0, feature(ART_L, "依据", "来源可查", dark=False, crop=(0, 770, 780, 800), start=9.6, speed=0.3, swing=1)),
        (17.0, 2.5, feature(TODAY_D, "深色模式", "夜里也好读", dark=True, crop=(0, 100, 780, 720), start=2.0, speed=0.5, swing=-1)),
        (19.5, 2.5, feature(DISC, "经典阅读", "读原文", dark=False, crop=(0, 200, 780, 720), start=8.0, speed=0.8, swing=1)),
        (22.0, 2.5, s_split),
        (24.5, 3.0, s_ajin),
        (27.5, 2.5, s_outro),
    ]


# 每个镜头切点的白闪 / 黑闪强度，卡在 drop 后的小节首拍
def cut_flash(t, cuts):
    for c in cuts:
        if c >= 8.0 and 0 <= t - c < 0.1:
            return 0.55 * (1 - (t - c) / 0.1)
    return 0.0


# ---------- 旁白字幕 ----------
def load_captions():
    caps = []
    for line in (ROOT / "promo/v2/lines.txt").read_text().splitlines():
        if "|" not in line:
            continue
        key, at, txt = line.split("|", 2)
        if key in ("hook", "drop"):
            continue  # 画面上已有同样的大字，不重复出字幕
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(OUT / f"narration/{key}.aiff")], capture_output=True, text=True).stdout)
        # 按标点拆成短句，每段按字数分配时长：一行 4–9 个字，逐段出现
        parts = [p for p in __import__("re").split(r"(?<=[，。？！：])", txt) if p.strip()]
        total = sum(len(p) for p in parts)
        t0 = float(at)
        for p in parts:
            d = dur * len(p) / total
            caps.append((t0, t0 + d, p.rstrip("，。：")))
            t0 += d
    return caps


def draw_caption(img, t, caps, dark):
    for a, b, txt in caps:
        if a <= t < b:
            k = ease_out_expo((t - a) / 0.15)
            f = font("Bold", 58)
            dr = ImageDraw.Draw(img)
            tw = dr.textlength(txt, font=f)
            layer = Image.new("RGBA", (int(tw) + 72, 104), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.rounded_rectangle((0, 0, layer.width - 1, 103), 26, fill=(*(PAPER if dark else INK), 235))
            ld.text((36, 52), txt, font=f, fill=INK if dark else PAPER, anchor="lm")
            # 字幕底边贴 78% 安全线，横向不超过 86%
            place(img, layer, min(W / 2, W * 0.86 - layer.width / 2 - 8), H * 0.78 - 70 - (1 - k) * 30, alpha=k)
    return img


def main():
    preview = "--preview" in sys.argv
    load_clips()
    shots = timeline()
    cuts = [s for s, _, _ in shots]
    caps = load_captions()
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / ("picture_preview.mp4" if preview else "picture.mp4")
    step = 2 if preview else 1
    size = (W // 2, H // 2) if preview else (W, H)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
                           "-r", str(FPS // step), "-i", "-", "-c:v", "libx264", "-crf", "16" if not preview else "23",
                           "-preset", "medium", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    total = int(DUR * FPS)
    for n in range(0, total, step):
        t = n / FPS
        for start, dur, fn in shots:
            if start <= t < start + dur:
                img = fn(t - start, dur)
                break
        img = flash(img, cut_flash(t, cuts))
        dark = np.asarray(img.resize((54, 96))).mean() < 128
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
