#!/usr/bin/env python3
"""asr_check 比对口径测试：只依赖标准库（mlx 只在真正转写时才导入）。

  cd tts-daily && python3 -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asr_check as a  # noqa: E402


class NormalizeForCompareTest(unittest.TestCase):
    def test_drops_punctuation_and_spaces(self):
        self.assertEqual(a.normalize_for_compare("代表名额，共 2360 名。"),
                         "代表名额共二千三百六十名")

    def test_two_and_er_unified(self):
        # TTS 读「两」、ASR 写「二」（或反过来）不该算错
        self.assertEqual(a.normalize_for_compare("两千三百六十"),
                         a.normalize_for_compare("二千三百六十"))

    def test_fullwidth_and_ling(self):
        self.assertEqual(a.normalize_for_compare("二〇二七年"), "二零二七年")


class SimilarityTest(unittest.TestCase):
    def test_identical_after_normalization(self):
        self.assertAlmostEqual(
            a.similarity("代表名额共2360名", "代表名额共两千三百六十名"), 1.0, places=3)

    def test_garbled_is_low(self):
        # 2026-11-08 真实的 dylan 乱码
        score = a.similarity("二十一大代表选举启动，2360名代表怎么选",
                            "二十一大代表选举启动的二新师六零抢车方杠的C抢车队")
        self.assertLess(score, 0.7)

    def test_empty_is_zero(self):
        self.assertEqual(a.similarity("", "随便什么"), 0.0)
        self.assertEqual(a.similarity("随便什么", ""), 0.0)


class NumberTokenTest(unittest.TestCase):
    def test_extracts_number_tokens(self):
        self.assertEqual(a.number_tokens("代表2360名，38个单位"), ["二千三百六十", "三十八"])
        self.assertEqual(a.number_tokens("党的二十一大"), ["二十一"])

    def test_missing_numbers(self):
        # 短句里数字读错，相似度还高达 0.9，只能靠数字单独核对抓出来
        self.assertEqual(a.missing_numbers("北京时间11月6日晚", "北京时间十七月六日晚"), ["十一"])
        self.assertEqual(a.missing_numbers("5G工厂建了1260个", "五G工厂建了一千六百六十个"),
                         ["一千二百六十"])
        self.assertEqual(a.missing_numbers("5G工厂建了1260个", "五G工厂建了一千二百六十个"), [])

    def test_check_combines_score_and_numbers(self):
        score, missing, ok = a.check("北京时间11月6日晚", "北京时间十七月六日晚")
        self.assertFalse(ok)  # 相似度 0.9 ≥ 0.85，但数字缺了，仍判不通过
        self.assertGreaterEqual(score, 0.85)
        self.assertTrue(missing)

        score, missing, ok = a.check("北京时间11月6日晚", "北京时间十一月六日晚")
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_check_threshold(self):
        self.assertFalse(a.check("完全不一样的一句话", "另外一句毫不相干", threshold=0.85)[2])
        self.assertTrue(a.check("完全一样的一句话", "完全一样的一句话", threshold=0.85)[2])


if __name__ == "__main__":
    unittest.main()
