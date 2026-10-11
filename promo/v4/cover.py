"""v4 封面：抖音 9:16（1080×1920）+ 小红书 3:4（1080×1440），沿用 v4 的配色、标题块、图标和录屏卡片。

用法: python3 promo/v4/cover.py
输出: output/promo-video/v4/cover/cover-9x16.png、cover-3x4.png
"""
import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_spec = importlib.util.spec_from_file_location("compose_v4", HERE / "compose.py")
c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c)
from layout import BLUE, GOLD, INK, PAPER, TEAL, W, background, font, icon  # noqa: E402

OUT = c.OUT / "cover"


def block(d, x, y, text, size, fill, color):
    f = font("Heavy", size)
    tw = d.textlength(text, font=f)
    bh = size + 24
    d.rectangle((x, y, x + tw + 72, y + bh), fill=fill)
    gt, gb = f.getbbox(text)[1], f.getbbox(text)[3]
    d.text((x + 36, y + (bh - (gb - gt)) / 2 - gt), text, font=f, fill=color)
    return y + bh


def cover(height, title_y, card_box, chips_y):
    img = background(True, 0.6, 0).crop((0, 0, W, height)) if height < 1920 else background(True, 0.6, 0)
    d = ImageDraw.Draw(img)
    # 品牌行
    ic = icon("newspaper", 52, GOLD)
    img.paste(ic, (88, title_y - 110), ic)
    d.text((154, title_y - 84), "见闻 · JIANWEN", font=font("Bold", 42), fill=GOLD, anchor="lm")
    # 标题块：金块 + 蓝块
    y = block(d, 88, title_y, "每天 5 件事", 120, GOLD, INK) + 20
    block(d, 88, y, "看懂和你有关的变化", 76, BLUE, PAPER)
    # 录屏卡片（今日页）+ 金色描边
    x0, y0, x1, y1 = card_box
    scr = c.v2.screen(c.clip("today"), 1.0, crop=(0, 40, 780, 1150), radius=40)
    s = min((x1 - x0) / scr.width, (y1 - y0) / scr.height)
    scr = scr.resize((int(scr.width * s), int(scr.height * s)), Image.LANCZOS)
    frame = Image.new("RGBA", (scr.width + 16, scr.height + 16), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle((0, 0, frame.width - 1, frame.height - 1), 48, fill=(*GOLD, 255))
    frame.paste(scr, (8, 8), scr)
    cx = (x0 + x1) // 2
    img.paste(frame, (cx - frame.width // 2, y0), frame)
    # 两侧徽章
    for name, bx, by in (("message-circle-question-mark", 120, y0 + 120), ("shield-check", W - 120, y0 + frame.height - 160)):
        disc = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        ImageDraw.Draw(disc).ellipse((0, 0, 119, 119), fill=(*GOLD, 255))
        g = icon(name, 64, INK)
        disc.paste(g, (28, 28), g)
        img.paste(disc, (bx - 60, by - 60), disc)
    # 底部信息条
    x = 88
    f = font("Medium", 36)
    for name, label in (("newspaper", "每日 5 件"), ("message-circle-question-mark", "AI 追问"), ("shield-check", "来源可查")):
        tw = d.textlength(label, font=f)
        w = int(tw + 116)
        d.rounded_rectangle((x, chips_y, x + w, chips_y + 88), 44, fill=(24, 38, 50), outline=GOLD if x == 88 else None, width=3)
        g = icon(name, 42, GOLD)
        img.paste(g, (x + 26, chips_y + 23), g)
        d.text((x + 80, chips_y + 44), label, font=f, fill=PAPER, anchor="lm")
        x += w + 18
    return img.convert("RGB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # 9:16：标题在上方安全区下沿，卡片占中部，信息条在 78% 安全线以上
    cover(1920, 380, (150, 720, 930, 1420), 1470).save(OUT / "cover-9x16.png")
    # 3:4：同一套元素压缩排布
    cover(1440, 260, (210, 600, 870, 1150), 1260).save(OUT / "cover-3x4.png")
    print(OUT)


if __name__ == "__main__":
    main()
