#!/usr/bin/env python3
"""把阿拉伯数字改写成中文读法，减少 TTS 读错数字的概率（纯标准库，可被系统 python 直接导入）。

覆盖这些情况（都是 ASR 实测读错过的）：
- 日期：11月6日 → 十一月六日；2026-11-08 → 二零二六年十一月八日
- 年份：2027年 → 二零二七年（四位年份逐位读）
- 整数：1260 → 一千二百六十；2360 → 两千三百六十；10亿 → 十亿
- 小数：2.6万 → 二点六万；164.4万 → 一百六十四点四万；260多万 → 二百六十多万
- 百分比：15% → 百分之十五；3%–5% → 百分之三到百分之五
- 区间：10-20 → 十到二十
- 长数字串（≥7 位，手机号/编号）逐位读：13800138000 → 一三八零零一三八零零零
- 字母夹数字：5G → 五G，G7 → G七，MP3 → MP三
- 时间：11:06 → 十一点零六分

规则：数字开头的「2」后面紧跟 千/万/亿 时读「两」（两千三百六十），百位读「百」（二百六十）。
已有中文数字（二十一大、二零二七年）原样保留，因此本函数是幂等的。
"""

from __future__ import annotations

import re

DIGITS = "零一二三四五六七八九"
_SMALL_UNITS = ["", "十", "百", "千"]
_BIG_UNITS = ["", "万", "亿", "万亿"]
_FULLWIDTH = str.maketrans("０１２３４５６７８９．％", "0123456789.%")  # 只换数字和全角百分号


def _int4(n: int) -> str:
    """0 ≤ n < 10000 的中文读法。"""
    out = ""
    pending_zero = False
    for i in range(3, -1, -1):
        d = n // 10**i % 10
        if d == 0:
            if out:
                pending_zero = True
            continue
        if pending_zero:
            out += "零"
            pending_zero = False
        out += DIGITS[d] + _SMALL_UNITS[i]
    if out.startswith("一十"):  # 15 → 十五，不是一十五
        out = out[1:]
    return out


def _liang(s: str) -> str:
    """开头的「二千/二万/二亿」读「两千/两万/两亿」；二百、二十保持原样。"""
    return "两" + s[1:] if s.startswith("二") and len(s) > 1 and s[1] in "千万亿" else s


def int_to_zh(n: int) -> str:
    """整数读法，负数加「负」。"""
    if n < 0:
        return "负" + int_to_zh(-n)
    if n == 0:
        return "零"
    raw = str(n)
    if len(raw) > 4 * len(_BIG_UNITS):  # 超过万亿，退化为逐位读，避免读出天文单位
        return "".join(DIGITS[int(c)] for c in raw)
    groups = []
    rest = n
    while rest:
        groups.append(rest % 10000)
        rest //= 10000
    out = ""
    for idx in range(len(groups) - 1, -1, -1):
        g = groups[idx]
        if g == 0:
            if out and not out.endswith("零"):
                out += "零"
            continue
        if out and g < 1000 and not out.endswith("零"):
            out += "零"
        out += _int4(g) + _BIG_UNITS[idx]
    return _liang(out.rstrip("零"))


def decimal_to_zh(s: str) -> str:
    """小数读法：164.4 → 一百六十四点四，0.5 → 零点五。"""
    head, _, tail = s.partition(".")
    if not tail:
        return int_to_zh(int(head or 0))
    return int_to_zh(int(head or 0)) + "点" + "".join(DIGITS[int(c)] for c in tail)


def digits_to_zh(s: str) -> str:
    """逐位读：13800138000 → 一三八零零一三八零零零。"""
    return "".join(DIGITS[int(c)] for c in s if c.isdigit())


def number_to_zh(s: str) -> str:
    """整数或小数。"""
    return decimal_to_zh(s) if "." in s else int_to_zh(int(s))


def _date_iso(m: re.Match) -> str:
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    return f"{digits_to_zh(y)}年{int_to_zh(mo)}月{int_to_zh(d)}日"


def _date_md(m: re.Match) -> str:
    return f"{int_to_zh(int(m.group(1)))}月{int_to_zh(int(m.group(2)))}日"


def _clock(m: re.Match) -> str:
    h, mi = int(m.group(1)), int(m.group(2))
    if mi == 0:
        return f"{int_to_zh(h)}点"
    return f"{int_to_zh(h)}点{'零' + DIGITS[mi % 10] if mi < 10 else int_to_zh(mi)}分"


def _range(m: re.Match) -> str:
    return f"{number_to_zh(m.group(1))}到{number_to_zh(m.group(2))}"


def _percent(m: re.Match) -> str:
    return f"百分之{number_to_zh(m.group(1))}"


def _percent_range(m: re.Match) -> str:
    return f"百分之{number_to_zh(m.group(1))}到百分之{number_to_zh(m.group(2))}"


_PERCENT_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*[%％]?\s*[-–—~～至]\s*(\d+(?:\.\d+)?)\s*[%％]")
_DATE_ISO = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")
_YEAR_RANGE = re.compile(r"(?<!\d)(\d{4})\s*[-–—~～至]\s*(\d{4})\s*(?=年)")
_CLOCK = re.compile(r"(?<![\d:])(\d{1,2})\s*[:：]\s*(\d{2})(?![\d:])")
_DATE_MD = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]")
_YEAR = re.compile(r"(?<!\d)(\d{4})\s*(?=年)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*[%％]")
_RANGE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[-–—~～至]\s*(\d+(?:\.\d+)?)(?![\d.%])")
_LONG_DIGITS = re.compile(r"(?<![\d.])(\d{7,})(?![\d.])")
_NEAR_LATIN = re.compile(r"(?<=[A-Za-z])\d+(?:\.\d+)?|\d+(?:\.\d+)?(?=[A-Za-z])")
_THOUSANDS = re.compile(r"(?<=\d)[,，](?=\d{3}(?!\d))")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# 单独一个「2」后面直接跟万/亿（单位在数字片段外，如「2万」）也要读「两」；
# 十二万、一百零二万 这类保持「二」。
_TWO_UNIT = re.compile(r"(?<![\d一二三四五六七八九十百千零两])二(?=[千万亿])")


def normalize(text: str) -> str:
    """把 text 里的阿拉伯数字改写成中文读法。幂等：连做两次结果一样。"""
    if not text:
        return text
    s = text.translate(_FULLWIDTH)
    s = _THOUSANDS.sub("", s)
    s = _PERCENT_RANGE.sub(_percent_range, s)
    s = _YEAR_RANGE.sub(lambda m: f"{digits_to_zh(m.group(1))}到{digits_to_zh(m.group(2))}", s)
    s = _DATE_ISO.sub(_date_iso, s)
    s = _CLOCK.sub(_clock, s)
    s = _DATE_MD.sub(_date_md, s)
    s = _YEAR.sub(lambda m: digits_to_zh(m.group(1)), s)  # 四位年份逐位读
    s = _PERCENT.sub(_percent, s)
    s = _RANGE.sub(_range, s)
    s = _LONG_DIGITS.sub(lambda m: digits_to_zh(m.group(1)), s)
    s = _NEAR_LATIN.sub(lambda m: number_to_zh(m.group(0)), s)
    s = _NUMBER.sub(lambda m: number_to_zh(m.group(0)), s)
    return _TWO_UNIT.sub("两", s)
