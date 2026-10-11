"""生成宣传片字幕和标题卡 PNG（1080×1920 透明底），以及叠加时间表 captions.json。

本机 ffmpeg 没有 libass，字幕改为图片叠加。字体用思源黑体（SIL OFL），
放在 output/promo-video/fonts/SubsetOTF/CN/。
用法: python3 promo/captions.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/promo-video/captions"
FONTS = ROOT / "output/promo-video/fonts/SubsetOTF/CN"
W, H = 1080, 1920

INK = (20, 33, 43)
BLUE = (31, 95, 122)
GOLD = (212, 170, 78)
PAPER = (245, 247, 244)

# 安全区：上 12%、下 22%、右 14% 留给平台界面
SAFE_LEFT, SAFE_RIGHT = 64, int(W * 0.86)
SUB_Y = int(H * 0.78) - 40  # 字幕底边贴近下方安全线

# 镜头标题卡：时间（秒）、标签、主标题
TITLES = [
    (0.3, 3.8, "JIANWEN", "每天 5 件事，看懂和你有关的变化"),
    (4.4, 8.5, "今日", "用几分钟，看懂今天"),
    (14.4, 18.5, "文章", "先给结论，再看依据"),
    (24.4, 28.5, "AI 问问", "不懂就问，回答带来源"),
    (34.4, 38.5, "发现 · 经典", "按兴趣，读原文"),
    (42.9, 47.0, "网页版", "手机和网页，同一份进度"),
    (50.4, 55.6, "阿烬", "一个陪你想清楚的伙伴"),
]

# 旁白起始时间（毫秒），与 promo/mix.sh 一致
VOICE_AT = dict(hook=500, today=4500, article=14500, ask=24500, discover=34500, web=43000, ajin=50500, outro=56000)


def font(weight, size):
    return ImageFont.truetype(str(FONTS / f"SourceHanSansCN-{weight}.otf"), size)


def wrap(draw, text, fnt, max_w):
    """按像素宽度换行，标点不放行首"""
    lines, line = [], ""
    for ch in text:
        trial = line + ch
        if draw.textlength(trial, font=fnt) > max_w and line:
            if ch in "，。？！、；：）」":
                line = trial
                continue
            lines.append(line)
            line = ch
        else:
            line = trial
    if line:
        lines.append(line)
    return lines
def subtitle(text, path):
    """旁白字幕：底部安全区内，白字 + 半透明深色圆角底"""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fnt = font("Medium", 46)
    max_w = SAFE_RIGHT - SAFE_LEFT - 64 - 46  # 预留一个字宽给不换行的行尾标点
    lines = wrap(d, text, fnt, max_w)
    line_h = 66
    box_h = line_h * len(lines) + 36
    box_w = max(d.textlength(l, font=fnt) for l in lines) + 64
    x0 = (SAFE_LEFT + SAFE_RIGHT - box_w) / 2
    y0 = SUB_Y - box_h
    d.rounded_rectangle((x0, y0, x0 + box_w, y0 + box_h), radius=22, fill=(*INK, 190))
    for i, l in enumerate(lines):
        tw = d.textlength(l, font=fnt)
        d.text(((SAFE_LEFT + SAFE_RIGHT - tw) / 2, y0 + 16 + i * line_h), l, font=fnt, fill=(255, 255, 255, 255))
    img.save(path)


def title_card(label, text, path):
    """镜头标题：上方安全区下沿，金色小标签 + 深色主标题"""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    top = int(H * 0.12) + 40  # 底板上沿也要在安全线内
    lab = font("Bold", 30)
    d.text((SAFE_LEFT, top), label.upper() if label.isascii() else label, font=lab, fill=(*GOLD, 255))
    d.rectangle((SAFE_LEFT, top + 52, SAFE_LEFT + 56, top + 57), fill=(*GOLD, 255))
    big = font("Bold", 64)
    rows = wrap(d, text, big, SAFE_RIGHT - SAFE_LEFT - 96)
    # 浅色半透明底，标题压在手机或画面上时也能看清
    back_w = max(d.textlength(r, font=big) for r in rows) + 72
    back = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(back).rounded_rectangle((SAFE_LEFT - 32, top - 26, SAFE_LEFT - 32 + back_w, top + 78 + len(rows) * 86 + 14),
                                           radius=26, fill=(*PAPER, 215))
    img = Image.alpha_composite(back, img)
    d = ImageDraw.Draw(img)
    for i, l in enumerate(rows):
        d.text((SAFE_LEFT, top + 78 + i * 86), l, font=big, fill=(*INK, 255))
    img.save(path)


def outro(path):
    """片尾：浅色底 + 品牌名 + 口号"""
    img = Image.new("RGBA", (W, H), (*PAPER, 255))
    d = ImageDraw.Draw(img)
    cx = W // 2
    name = font("Heavy", 150)
    tw = d.textlength("见闻", font=name)
    d.text((cx - tw / 2, 700), "见闻", font=name, fill=(*INK, 255))
    eng = font("Medium", 34)
    tw = d.textlength("JIANWEN", font=eng)
    d.text((cx - tw / 2, 890), "JIANWEN", font=eng, fill=(*BLUE, 255))
    d.rectangle((cx - 40, 960, cx + 40, 965), fill=(*GOLD, 255))
    slogan = font("Regular", 46)
    for i, l in enumerate(("以政策照见时代", "以思考丰盈灵魂")):
        tw = d.textlength(l, font=slogan)
        d.text((cx - tw / 2, 1010 + i * 72), l, font=slogan, fill=(*INK, 255))
    img.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plan = []
    lines = [l.split("|", 1) for l in (ROOT / "promo/narration/lines.txt").read_text().splitlines() if "|" in l]
    durations = json.loads((ROOT / "output/promo-video/narration/durations.json").read_text())
    for key, text in lines:
        if key == "outro":
            continue
        p = OUT / f"sub_{key}.png"
        subtitle(text, p)
        start = VOICE_AT[key] / 1000
        plan.append(dict(file=str(p), start=start, end=round(start + durations[key] + 0.25, 2)))
    for i, (a, b, label, text) in enumerate(TITLES):
        p = OUT / f"title_{i}.png"
        title_card(label, text, p)
        plan.append(dict(file=str(p), start=a, end=b))
    outro(OUT / "outro.png")
    (OUT / "captions.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    print(f"{len(plan)} overlays -> {OUT}")


if __name__ == "__main__":
    main()
