#!/usr/bin/env python3
"""用本地 Qwen3-ASR 回听合成结果，和原文比对，给每句打相似度分（供 generate.py 自检与重读）。

比对口径：两边都先做「数字转中文 + 去标点空格 + 统一两/二」的归一化，再用字符序列相似度
（difflib，1 - 编辑距离/长度）打分。0.85 以上认为读对了，0.7 以下认为这句不能发。

模型只在本机有缓存时加载（mlx-community/Qwen3-ASR-0.6B-8bit），导入本模块不需要 mlx，
纯函数（normalize_for_compare / similarity）可被系统 python 直接测。

用法:
  python3 tts-daily/asr_check.py out/2026-11-08/<article>/dylan.mp3 --text-file /tmp/sents.txt
  python3 tts-daily/asr_check.py out/2026-11-08/<article>/jianwen.mp3   # 只转写并打印
"""
from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import textnorm  # noqa: E402

ASR_MODEL = "mlx-community/Qwen3-ASR-0.6B-8bit"
ASR_SR = 16000
# 中文标点与空白：比对时全部丢掉
_NOISE = re.compile(r"[\s，。！？；：、,.!?;:\"'“”‘’（）()《》<>【】\[\]—–\-…·~～%％]")
_NUM_LIANG = re.compile(r"两(?=[百千万亿])")
_NUM_LING = re.compile(r"[〇○]")
# 归一化后文本里的「数字」片段（中文读法），用来单独核对数字有没有被读错
_NUM_TOKEN = re.compile(r"[零一二三四五六七八九十][零一二三四五六七八九十百千万亿点]*")


def normalize_for_compare(text: str) -> str:
    """比对口径归一化：数字转中文、去标点空格、统一「两/二」「〇/零」。"""
    s = textnorm.normalize(text or "")
    s = _NUM_LING.sub("零", s)
    s = _NUM_LIANG.sub("二", s)
    return _NOISE.sub("", s)


def number_tokens(text: str) -> list[str]:
    """抽出比对口径下的数字片段（含原文就是中文的数字，如「二十一大」）。"""
    return [t for t in _NUM_TOKEN.findall(normalize_for_compare(text)) if t]


def missing_numbers(ref: str, hyp: str) -> list[str]:
    """ref 里有、转写里没出现的数字（数字被读错时最容易在这里露出来）。"""
    h = normalize_for_compare(hyp)
    return [t for t in number_tokens(ref) if t not in h]


def similarity(ref: str, hyp: str) -> float:
    """字符级相似度 0–1（两边先按比对口径归一化）。任一为空时返回 0。"""
    a, b = normalize_for_compare(ref), normalize_for_compare(hyp)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def check(ref: str, hyp: str, threshold: float = 0.85) -> tuple[float, list[str], bool]:
    """综合判定：(相似度, 缺失的数字, 是否通过)。

    通过条件是「相似度 ≥ threshold」且「原文的数字都在转写里出现」——
    单看相似度会被短句稀释（「北京时间11月6日晚」读成「北京十七月六日晚」还有 0.78），
    所以数字单独卡一道。
    """
    score = similarity(ref, hyp)
    missing = missing_numbers(ref, hyp)
    return score, missing, score >= threshold and not missing


def _ffmpeg_to_wav(src: Path, dst: Path, seconds: float | None = None) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src)]
    if seconds:
        cmd += ["-t", f"{seconds:.2f}"]
    cmd += ["-ar", str(ASR_SR), "-ac", "1", "-c:a", "pcm_s16le", str(dst)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def find_cached_model(name: str = ASR_MODEL) -> str:
    """优先用本地 HF 缓存（离线可用），找不到就返回仓库名让 mlx 自己解析。"""
    repo = "models--" + name.replace("/", "--")
    root = Path.home() / ".cache/huggingface/hub" / repo / "snapshots"
    snaps = sorted(p for p in root.glob("*") if (p / "model.safetensors").is_file()) if root.is_dir() else []
    return str(snaps[-1]) if snaps else name


class AsrChecker:
    """懒加载 ASR 模型；不可用时 available=False，调用方按「跳过自检」处理。"""

    def __init__(self, model: str = ASR_MODEL):
        self.model_id = model
        self._model = None
        self.available = True
        self.reason = ""

    def load(self):
        if self._model is not None or not self.available:
            return self._model
        try:
            from mlx_audio.stt.utils import load_model
            self._model = load_model(find_cached_model(self.model_id))
        except Exception as exc:  # 没装 mlx / 没缓存 → 自检降级，不阻断合成
            self.available = False
            self.reason = f"{type(exc).__name__}: {exc}"
        return self._model

    def transcribe(self, audio: Path) -> str:
        """转写一段音频（wav/mp3 均可，内部重采样到 16k 单声道）。"""
        if self.load() is None:
            raise RuntimeError(f"ASR 不可用：{self.reason}")
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "asr.wav"
            _ffmpeg_to_wav(Path(audio), wav)
            out = self._model.generate(str(wav), language="Chinese")
        return (getattr(out, "text", "") or "").strip()

    def score(self, text: str, audio: Path) -> tuple[float, list[str], str]:
        """返回 (相似度, 缺失的数字, 转写文本)。转写失败抛异常，由调用方决定是否重试。"""
        hyp = self.transcribe(audio)
        score, missing, _ = check(text, hyp)
        return score, missing, hyp


def main():
    ap = argparse.ArgumentParser(description="用 Qwen3-ASR 回听 mp3/wav，和原文比对打分")
    ap.add_argument("audio", type=Path, help="音频文件（mp3 或 wav）")
    ap.add_argument("--text-file", type=Path, help="原文文件，一行一句；给出则逐句打分")
    ap.add_argument("--model", default=ASR_MODEL)
    args = ap.parse_args()
    if not args.audio.is_file():
        raise SystemExit(f"找不到 {args.audio}")
    asr = AsrChecker(args.model)
    hyp = asr.transcribe(args.audio)
    print(hyp)
    if not args.text_file:
        return
    refs = [x.strip() for x in args.text_file.read_text(encoding="utf-8").splitlines() if x.strip()]
    print(f"--- 整篇相似度 {similarity(''.join(refs), hyp):.3f}")
    for line in refs:
        s, missing, ok = check(line, hyp)
        print(f"{s:5.3f} {'OK ' if ok else 'NG '}  {line}" + (f"  缺数字={missing}" if missing else ""))


if __name__ == "__main__":
    main()
