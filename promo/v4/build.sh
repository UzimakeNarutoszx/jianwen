#!/bin/zsh
# v4 一键出片：音轨 → 4 进程并行渲染画面 → 拼接 → 合成
# 前置：output/promo-video/v4/tts/<key>.wav 已由 CosyVoice 生成（output/promo-video/tools/cosy_synth.py）
set -euo pipefail
cd "${0:A:h}/../.."
V=output/promo-video/v4
for key in $(cut -d'|' -f1 promo/v4/lines.txt); do
  [[ -s $V/tts/$key.wav ]] || { echo "缺少旁白 $V/tts/$key.wav"; exit 1; }
done
promo/v4/audio.sh
N=${PARTS:-4}
for i in $(seq 0 $(( N - 1 ))); do python3 promo/v4/compose.py --part=$i/$N > $V/part_$i.log 2>&1 & done
wait
: > $V/parts.txt
for i in $(seq 0 $(( N - 1 ))); do echo "file 'part_${i}of${N}.mp4'" >> $V/parts.txt; done
ffmpeg -v error -y -f concat -safe 0 -i $V/parts.txt -c copy $V/picture.mp4
OUT=output/promo-video/jianwen-promo-v4-30s.mp4
python3 promo/v4/cover.py >/dev/null
# 9:16 封面作为 attached_pic 写进 mp4，播放器和部分平台会用它做缩略图
ffmpeg -v error -y -i $V/picture.mp4 -i $V/audio.m4a -i $V/cover/cover-9x16.png -map 0:v -map 1:a -map 2 -c copy -c:v:1 png \
  -disposition:v:1 attached_pic -t 30 -movflags +faststart $OUT
rm -f $V/part_*of*.mp4 $V/part_*.log $V/parts.txt
echo $OUT
