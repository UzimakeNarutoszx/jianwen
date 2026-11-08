#!/usr/bin/env python3
"""textnorm 单元测试：只依赖标准库，用系统 python3 直接跑。

  cd tts-daily && python3 -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import textnorm as t  # noqa: E402


class IntegerTest(unittest.TestCase):
    def test_plain_ints(self):
        cases = {
            0: "零", 1: "一", 5: "五", 10: "十", 11: "十一", 15: "十五",
            20: "二十", 41: "四十一", 99: "九十九", 100: "一百", 105: "一百零五",
            110: "一百一十", 1260: "一千二百六十", 2360: "两千三百六十",
            10000: "一万", 10001: "一万零一", 21000: "两万一千", 10**8: "一亿",
        }
        for n, want in cases.items():
            self.assertEqual(t.int_to_zh(n), want, f"{n} 应读 {want}")

    def test_leading_two_reads_liang(self):
        # 「2」开头 + 千/万/亿 读「两」，但二百、二十保持「二」
        self.assertEqual(t.normalize("2360名"), "两千三百六十名")
        self.assertEqual(t.normalize("260多万名"), "二百六十多万名")
        self.assertEqual(t.normalize("2万"), "两万")
        self.assertEqual(t.normalize("2亿"), "两亿")
        self.assertEqual(t.normalize("200人"), "二百人")
        self.assertEqual(t.normalize("20人"), "二十人")

    def test_decimal(self):
        self.assertEqual(t.normalize("2.6万"), "二点六万")
        self.assertEqual(t.normalize("164.4万"), "一百六十四点四万")
        self.assertEqual(t.normalize("0.5%"), "百分之零点五")

    def test_thousands_separator(self):
        self.assertEqual(t.normalize("1,260个"), "一千二百六十个")


class DateTest(unittest.TestCase):
    def test_month_day(self):
        # ASR 实测把「11月6日」读成「十七月六日」，这条是回归用例
        self.assertEqual(t.normalize("北京时间11月6日晚"), "北京时间十一月六日晚")
        self.assertEqual(t.normalize("11月6日"), "十一月六日")
        self.assertEqual(t.normalize("6月底"), "六月底")

    def test_year_reads_digit_by_digit(self):
        self.assertEqual(t.normalize("2027年"), "二零二七年")
        self.assertEqual(t.normalize("党的二十一大定于2027年下半年在北京召开"),
                         "党的二十一大定于二零二七年下半年在北京召开")

    def test_iso_date(self):
        self.assertEqual(t.normalize("2026-11-08"), "二零二六年十一月八日")
        self.assertEqual(t.normalize("2024-2026年"), "二零二四到二零二六年")
        self.assertEqual(t.normalize("2027年下半年"), "二零二七年下半年")  # 不是日期

    def test_clock(self):
        self.assertEqual(t.normalize("11:06"), "十一点零六分")
        self.assertEqual(t.normalize("9:00"), "九点")


class PercentAndRangeTest(unittest.TestCase):
    def test_percent(self):
        self.assertEqual(t.normalize("多于15%"), "多于百分之十五")
        self.assertEqual(t.normalize("3%"), "百分之三")

    def test_percent_range(self):
        for raw in ("3%-5%", "3%–5%", "3-5%"):
            self.assertEqual(t.normalize(raw), "百分之三到百分之五", raw)

    def test_range(self):
        self.assertEqual(t.normalize("10-20"), "十到二十")
        self.assertEqual(t.normalize("10 至 20"), "十到二十")


class LongDigitTest(unittest.TestCase):
    def test_phone_reads_digit_by_digit(self):
        self.assertEqual(t.normalize("13800138000"), "一三八零零一三八零零零")

    def test_latin_adjacent(self):
        self.assertEqual(t.normalize("5G工厂"), "五G工厂")
        self.assertEqual(t.normalize("6G"), "六G")
        self.assertEqual(t.normalize("5G-A"), "五G-A")
        self.assertEqual(t.normalize("4K 视频"), "四K 视频")


class IdempotentTest(unittest.TestCase):
    def test_keeps_existing_chinese_numbers(self):
        # 原文已经是中文数字的不要动（幂等，避免二次处理读坏）
        for raw in ("二十一大", "二零二七年", "十五五规划", "十四五", "两会", "一带一路"):
            self.assertEqual(t.normalize(raw), raw)

    def test_second_pass_is_noop(self):
        samples = [
            "二十一大代表选举启动，2360名代表怎么选",
            "北京时间11月6日晚，5G工厂建了1260个，260多万名用户，15% 到 3%-5%",
            "2026-11-08 13800138000 2.6万 164.4万 10-20 11:06",
        ]
        for s in samples:
            once = t.normalize(s)
            self.assertEqual(t.normalize(once), once, s)

    def test_no_digits_left(self):
        s = "二十一大代表选举启动，2360名代表怎么选，38个选举单位，2027年下半年，15%"
        self.assertIsNone(t._NUMBER.search(t.normalize(s)))

    def test_punctuation_untouched(self):
        # 只改数字，中文标点原样保留（全角冒号曾被误换成半角过一次）
        for raw in ("真正的问题是：名额和结构要求已明确",
                    "一是责任主体：推荐提名靠基层党组织发动",
                    "他说：“2360名。”"):
            self.assertEqual(t.normalize(raw).replace("两千三百六十", "2360"), raw)

    def test_fullwidth_digits(self):
        self.assertEqual(t.normalize("１１月６日"), "十一月六日")
        self.assertEqual(t.normalize("２３６０名"), "两千三百六十名")


class RealArticleTest(unittest.TestCase):
    """真文章里的数字逐个核过（2026-11-08 第一篇）。"""

    def test_first_article_first_sentences(self):
        cases = {
            "二十一大代表选举启动，2360名代表怎么选": "二十一大代表选举启动，两千三百六十名代表怎么选",
            "代表名额共2360名，由全国38个选举单位选举产生": "代表名额共两千三百六十名，由全国三十八个选举单位选举产生",
            "差额比例多于15%": "差额比例多于百分之十五",
        }
        for src, want in cases.items():
            self.assertEqual(t.normalize(src), want)

    def test_empty_and_none(self):
        self.assertEqual(t.normalize(""), "")
        self.assertEqual(t.normalize(None), None)


if __name__ == "__main__":
    unittest.main()
