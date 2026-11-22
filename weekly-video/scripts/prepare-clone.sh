#!/bin/sh
# 每周视频旁白：日更在用的「见闻」声音（1.7B Base ICL 克隆），按整句合成。
# 用法：npm run prepare:clone -- 2026-W47 [--tempo 0.9]
# 换参考音：QWEN_REF_AUDIO=/path/ref.wav QWEN_REF_TEXT=/path/ref.txt npm run prepare:clone -- 2026-W47
set -eu
cd "$(dirname "$0")/.."
REF_AUDIO=${QWEN_REF_AUDIO:-"$HOME/Thomas的文件/编程/其他/拙政园的造景手法/output/promo-video/voice_ref/ref.wav"}
REF_TEXT=${QWEN_REF_TEXT:-"$(dirname "$REF_AUDIO")/ref.txt"}
if [ ! -f "$REF_AUDIO" ] || [ ! -f "$REF_TEXT" ]; then
  echo "参考音缺失：$REF_AUDIO / $REF_TEXT（可用 QWEN_REF_AUDIO、QWEN_REF_TEXT 指定）" >&2
  exit 1
fi
exec bash scripts/prepare-qwen.sh \
  --model mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit \
  --unit sentence \
  --ref-audio "$REF_AUDIO" \
  --ref-text "$REF_TEXT" \
  "$@"
