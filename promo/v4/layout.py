"""v3 版式系统：固定竖屏网格 + 高辨识度标题块 + 图标信息条 + 背景动态纹理。

网格（1080×1920）：
  0–230     顶部平台遮挡区：品牌细条 + 进度条 + 背景纹理
  240–575   标题区：标签 + 实色标题块（与画面内容完全分离）
  600–1250  主画面区：屏幕卡片 / 产品，两侧浮动图标徽章
  1270–1354 图标信息条
  1380–1480 字幕区（底部 78% 安全线以上）
  1500–1920 底部遮挡区：只有背景纹理，被平台界面挡住也不影响理解
"""
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
V = ROOT / "output/promo-video"
FONTS = V / "fonts/SubsetOTF/CN"
ICONS = V / "v2/assets/icons"
W, H = 1080, 1920

INK = (20, 33, 43)
DEEP = (8, 14, 20)
BLUE = (31, 95, 122)
TEAL = (126, 184, 209)
GOLD = (212, 170, 78)
PAPER = (245, 247, 244)
MIST = (237, 245, 247)

TITLE_Y = 270
MAIN_TOP, MAIN_BOTTOM = 610, 1450
CHIPS_Y = 1472
CAPTION_Y = 1630


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_expo(x):
    x = clamp(x)
    return 1 if x == 1 else 1 - 2 ** (-10 * x)


def ease_out_back(x, s=1.7):
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def spring(x, freq=2.2, damp=7.0):
    x = clamp(x)
    return 1 - math.exp(-damp * x) * math.cos(2 * math.pi * freq * x)


@lru_cache(maxsize=None)
def font(weight, size):
    return ImageFont.truetype(str(FONTS / f"SourceHanSansCN-{weight}.otf"), size)


@lru_cache(maxsize=None)
def icon(name, size, color):
    """Lucide 图标：由 promo/v3/icons.cjs 用 Chrome 预渲染成白色 PNG，这里按需缩放并着色"""
    path = ICONS / "png" / f"{name}.png"
    if not path.exists():
        return None
    im = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
    solid = Image.new("RGBA", im.size, (*color, 255))
    solid.putalpha(im.getchannel("A"))
    return solid


def paste(base, im, x, y, alpha=1.0):
    if im is None or alpha <= 0.01:
        return
    if alpha < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    base.paste(im, (int(x), int(y)), im)


def background(dark, t, seed=0):
    """背景：底色 + 缓慢漂移的点阵网格 + 一道斜向光带，保证画面上下都不空"""
    bg = DEEP if dark else MIST
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    dot = (26, 40, 52) if dark else (214, 226, 230)
    off = (t * 40) % 60
    for y in range(-60, H + 60, 60):
        for x in range(0, W + 60, 60):
            d.ellipse((x - off - 2, y + off - 2, x - off + 2, y + off + 2), fill=dot)
    # 斜光带：从左上缓慢扫过
    band = Image.new("L", (W, H), 0)
    bd = ImageDraw.Draw(band)
    cx = -400 + (t * 260 + seed * 300) % (W + 800)
    bd.polygon([(cx, 0), (cx + 260, 0), (cx + 260 - 900, H), (cx - 900, H)], fill=38 if dark else 60)
    band = band.filter(ImageFilter.GaussianBlur(60))
    glow = Image.new("RGB", (W, H), BLUE if dark else (255, 255, 255))
    img.paste(glow, (0, 0), band)
    return img


def title_block(base, label, lines, t, dark, icon_name=None, accent_last=True):
    """高辨识度标题：实色块承载大字，与画面内容分离。
    块从左侧擦入（0.25s），文字随后弹入；标签带图标。"""
    fg_block = GOLD if dark else INK
    fg_text = INK if dark else PAPER
    k = ease_out_expo(t / 0.25)
    d = ImageDraw.Draw(base)
    # 标签行：图标 + 小字
    lx = 88
    ic = icon(icon_name, 52, TEAL if dark else BLUE) if icon_name else None
    if ic is not None:
        paste(base, ic, lx, TITLE_Y - 4, alpha=k)
        lx += 66
    d.text((lx, TITLE_Y + 22), label, font=font("Bold", 40), fill=TEAL if dark else BLUE, anchor="lm")
    # 每行一个实色块
    size = (112 if max(len(l) for l in lines) <= 5 else 96) if len(lines) == 1 else 92
    f = font("Heavy", size)
    y = TITLE_Y + 70
    for i, line in enumerate(lines):
        lt = clamp((t - 0.06 - i * 0.12) / 0.3)
        if lt <= 0:
            y += size + 36
            continue
        tw = d.textlength(line, font=f)
        bw = int((tw + 72) * ease_out_expo(lt))
        is_accent = accent_last and i == len(lines) - 1 and len(lines) > 1
        block = (BLUE if dark else GOLD) if is_accent else fg_block
        txt = PAPER if is_accent and dark else (INK if is_accent else fg_text)
        d.rectangle((88, y, 88 + bw, y + size + 24), fill=block)
        if bw > tw * 0.6:
            bh = size + 24
            layer = Image.new("RGBA", (int(tw) + 40, bh), (0, 0, 0, 0))
            # 按字形实际墨迹的上下边居中（anchor=lm 以字体度量居中，中文会偏下）
            gt, gb = f.getbbox(line)[1], f.getbbox(line)[3]
            ImageDraw.Draw(layer).text((0, (bh - (gb - gt)) / 2 - gt), line, font=f, fill=txt)
            # 文字从块内下方弹到正中，超出色块的部分被图层边界裁掉
            dy = int((1 - spring(clamp((lt - 0.3) / 0.7))) * 50)
            shifted = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            shifted.paste(layer, (0, dy))
            base.paste(shifted, (88 + 36, y), shifted)
        y += size + 36
    return y  # 标题区底边，供调用方核对不压主画面


def chips(base, items, t, dark, start=0.3):
    """底部图标信息条：圆角胶囊，逐个弹出"""
    d = ImageDraw.Draw(base)
    f = font("Medium", 34)
    x = 88
    for i, (ic_name, label) in enumerate(items):
        k = ease_out_back(clamp((t - start - i * 0.1) / 0.3), 1.4)
        if k <= 0:
            continue
        tw = d.textlength(label, font=f)
        w = int(tw + 112)
        chip = Image.new("RGBA", (w, 84), (0, 0, 0, 0))
        cd = ImageDraw.Draw(chip)
        cd.rounded_rectangle((0, 0, w - 1, 83), 42, fill=(*(INK if not dark else (24, 38, 50)), 255),
                             outline=(*GOLD, 255) if i == 0 else None, width=3)
        ic = icon(ic_name, 40, GOLD)
        if ic is not None:
            chip.paste(ic, (24, 22), ic)
        cd.text((76, 42), label, font=f, fill=PAPER, anchor="lm")
        s = max(0.01, k)
        chip = chip.resize((max(1, int(w * s)), max(1, int(84 * s))), Image.BICUBIC)
        base.paste(chip, (int(x + (w - chip.width) / 2), int(CHIPS_Y + (84 - chip.height) / 2)), chip)
        x += w + 18
        if x > W * 0.86:
            break


def progress_dots(base, idx, total, dark):
    """顶部细进度：当前镜头位置，填补顶部空白又不抢眼"""
    d = ImageDraw.Draw(base)
    seg = (W - 176) / total
    for i in range(total):
        c = GOLD if i <= idx else ((40, 56, 70) if dark else (205, 218, 223))
        d.rounded_rectangle((88 + i * seg + 4, 150, 88 + (i + 1) * seg - 4, 156), 3, fill=c)
