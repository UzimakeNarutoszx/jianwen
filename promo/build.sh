#!/bin/zsh
# 合成宣传片成片：Blender 镜头序列 + 片尾卡 + 字幕叠加 + 混音
# 用法: promo/build.sh [配乐起点秒，默认 150]
# 前置: promo/render_all.sh 已渲染完，python3 promo/captions.py 已生成字幕
set -euo pipefail
cd "${0:A:h}/.."
START=${1:-150}
V=output/promo-video
R=$V/render
W=$V/work/build
mkdir -p $W

# 1. 混音（同时得到 preview/A_from<START>s.m4a）
NAME=final_from${START}s
promo/mix.sh $START $NAME
AUDIO=$V/preview/$NAME.m4a

# 2. 每个镜头的 PNG 序列编码成中间片段，按分镜顺序拼接
#    镜头之间 0.3 秒交叉淡化，所以 xfade offset = 累计时长 - 0.3 × 已有转场数
SHOTS=(hook today article ask discover web ajin)
typeset -A SECS=(hook 4 today 10 article 10 ask 10 discover 9 web 7.5 ajin 6)
# 每段比分镜多 0.3 秒（定格最后一帧），抵消交叉淡化的重叠，镜头起点仍落在分镜时间上
for s in $SHOTS; do
  SECS[$s]=$(( SECS[$s] + 0.3 ))
  ffmpeg -v error -y -framerate 30 -i $R/$s/f_%04d.png -vf "tpad=stop_mode=clone:stop_duration=1,trim=duration=${SECS[$s]},format=yuv420p" \
    -c:v libx264 -crf 12 -preset fast $W/$s.mp4
done
# 片尾卡：补足到 60 秒
SECS[outro]=$(( 60 - 56.5 + 0.1 ))
ffmpeg -v error -y -loop 1 -framerate 30 -t ${SECS[outro]} -i $V/captions/outro.png -vf "format=yuv420p,fade=t=in:d=0.4" -c:v libx264 -crf 12 $W/outro.mp4
SHOTS+=(outro)

inputs=(); filt=""; prev="[0:v]"; acc=0; i=0; XF=0.3
for s in $SHOTS; do inputs+=(-i $W/$s.mp4); done
for s in $SHOTS; do
  if (( i > 0 )); then
    off=$(( acc - XF * i ))
    filt+="${prev}[${i}:v]xfade=transition=fade:duration=${XF}:offset=${off}[x${i}];"
    prev="[x${i}]"
  fi
  acc=$(( acc + SECS[$s] ))
  i=$(( i + 1 ))
done
filt="${filt%;}"
ffmpeg -v error -y $inputs -filter_complex "$filt" -map "$prev" -c:v libx264 -crf 12 -preset fast -pix_fmt yuv420p $W/picture.mp4

# 3. 字幕和标题卡按 captions.json 的时间叠加
python3 - $W <<'EOF'
import json, sys
items = json.load(open('output/promo-video/captions/captions.json'))
inputs, chain, prev = [], [], '[0:v]'
for i, it in enumerate(items, 1):
    inputs += ['-loop', '1', '-t', '60', '-framerate', '30', '-i', it['file']]
    a, b = it['start'], it['end']
    # 每条字幕 0.2 秒淡入淡出
    chain.append(f"[{i}:v]format=rgba,fade=t=in:st={a}:d=0.2:alpha=1,fade=t=out:st={b - 0.2}:d=0.2:alpha=1[c{i}]")
    chain.append(f"{prev}[c{i}]overlay=0:0:enable='between(t,{a},{b})'[o{i}]")
    prev = f'[o{i}]'
open(sys.argv[1] + '/overlay.args', 'w').write('\n'.join(inputs))
open(sys.argv[1] + '/overlay.filter', 'w').write(';'.join(chain))
open(sys.argv[1] + '/overlay.map', 'w').write(prev)
EOF
ov_inputs=("${(@f)$(cat $W/overlay.args)}")
ffmpeg -v error -y -i $W/picture.mp4 $ov_inputs -/filter_complex $W/overlay.filter -map "$(cat $W/overlay.map)" -t 60 -c:v libx264 -crf 14 -preset slow -pix_fmt yuv420p $W/captioned.mp4

# 4. 合入音频，输出成片
OUT=$V/jianwen-promo-1080x1920.mp4
ffmpeg -v error -y -i $W/captioned.mp4 -i $AUDIO -map 0:v -map 1:a -c:v libx264 -profile:v high -crf 16 -preset slow -r 30 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -t 60 -movflags +faststart $OUT
echo $OUT
