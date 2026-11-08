#!/usr/bin/env python3
"""generate.py 里不依赖 mlx 的部分：数字规范化后的切句、整篇自检判定、侧车回收。

  cd tts-daily && python3 -m unittest discover -s tests -v
  （把 mlx 的导入挡在 ensure_runtime 之后，这里直接 import generate 不会加载模型。）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generate as g  # noqa: E402

ARTICLE = {
    "article_id": "ai-daily-20261108-1",
    "title": "二十一大代表选举启动，2360名代表怎么选",
    "summary": ["代表名额共2360名，由全国38个选举单位选举产生。"],
    "sections": [{"heading": "先看名额与时间表",
                  "body": "中央印发通知，部署党的二十一大代表选举。差额比例多于15%。"}],
}


class BuildSentencesTest(unittest.TestCase):
    def test_numbers_normalized_before_synthesis(self):
        sents = [t for t, _ in g.build_sentences(ARTICLE)]
        # 标题里的 2360 必须变成中文读法，这是 dylan 读成乱码的根因
        self.assertEqual(sents[0], "二十一大代表选举启动，两千三百六十名代表怎么选")
        joined = "".join(sents)
        self.assertNotRegex(joined, r"\d")  # 送进模型的文本里不该再有阿拉伯数字
        self.assertIn("三十八个选举单位", joined)
        self.assertIn("百分之十五", joined)

    def test_sentence_order_follows_contract(self):
        # title → summary → (heading, body)
        sents = [t for t, _ in g.build_sentences(ARTICLE)]
        self.assertEqual(sents[0], "二十一大代表选举启动，两千三百六十名代表怎么选")
        self.assertEqual(sents[1], "代表名额共两千三百六十名，由全国三十八个选举单位选举产生")
        self.assertEqual(sents[2], "先看名额与时间表")

    def test_gaps(self):
        sents = g.build_sentences(ARTICLE)
        self.assertEqual(sents[-1][1], None)  # 最后一句不接静音
        self.assertTrue(all(gap in (g.SENT_GAP, g.SECTION_GAP) for _, gap in sents[:-1]))

    def test_max_sentences(self):
        self.assertEqual(len(g.build_sentences(ARTICLE, 2)), 2)

    def test_long_sentence_split_after_normalization(self):
        art = {"title": "", "summary": [], "sections": [{"heading": "", "body": "数字" * 60 + "。",
                                                          }]}
        for text, _ in g.build_sentences(art):
            self.assertLessEqual(len(text), g.MAX_CHARS)


class VoiceOkTest(unittest.TestCase):
    def qa(self, scores):
        return [{"text": "x", "score": s, "missing": [], "seed": 0} for s in scores]

    def test_all_pass(self):
        self.assertTrue(g.voice_ok(self.qa([1.0, 0.95, 0.9])))

    def test_one_low_sentence_tolerated(self):
        # ASR 自己会把「警示」听成「定收」这类同音字；偶发一两句不丢整篇
        self.assertTrue(g.voice_ok(self.qa([1.0, 1.0, 0.95, 1.0, 0.95, 1.0, 0.6, 1.0, 1.0, 1.0])))

    def test_two_low_sentences_drops_voice(self):
        self.assertFalse(g.voice_ok(self.qa([1.0, 0.5, 0.4])))

    def test_many_low_sentences_drops_voice(self):
        # 数字被成片读错就是这种分数分布
        self.assertFalse(g.voice_ok(self.qa([0.6, 0.5, 0.45, 0.7, 0.55])))

    def test_average_below_pass_drops_voice(self):
        self.assertFalse(g.voice_ok(self.qa([0.8, 0.8, 0.8])))

    def test_no_scores_means_asr_unavailable(self):
        self.assertTrue(g.voice_ok(self.qa([None, None])))

    def test_empty(self):
        self.assertTrue(g.voice_ok([]))


class ReadQaTest(unittest.TestCase):
    def test_missing_sidecar_yields_none_score(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            rows = g.read_qa([("某句话", None)], "dylan", Path(td))
        self.assertEqual(rows[0]["score"], None)
        self.assertEqual(rows[0]["text"], "某句话")


class TextPiecesTest(unittest.TestCase):
    def test_strip_markdown(self):
        self.assertEqual(g.strip_markdown("**粗体** [链接](http://x) `code`"),
                         "粗体 链接 code")
        self.assertEqual(g.strip_markdown("https://example.com/a 正文"), "正文")

    def test_split_sentences(self):
        # 句号会被去掉，！？ 保留给模型当语气提示（原有行为）
        self.assertEqual(g.split_sentences("第一句。第二句！第三句？"),
                         ["第一句", "第二句！", "第三句？"])


if __name__ == "__main__":
    unittest.main()
