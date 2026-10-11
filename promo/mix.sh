#!/bin/zsh
# 用法: promo/mix.sh <配乐起点秒> <输出名>
# 分三步混音，每步落盘，便于单独测电平：
#   1. voice.wav 逐句旁白按分镜时间点铺好，固定增益到约 -16 LUFS
#   2. bed.wav   截取 60 秒配乐，固定增益，首尾淡入淡出
#   3. 配乐按旁白 sidechain 压低，叠加旁白，整体拉到约 -14 LUFS 并限幅
set -euo pipefail
cd "${0:A:h}/.."
START=$1; NAME=$2
N=output/promo-video/narration
W=output/promo-video/work/$NAME
OUT=output/promo-video/preview
MUSIC=output/promo-video/source/清_伴奏.mp3
mkdir -p $W $OUT

# 每句旁白的起始时间（毫秒），对应分镜
typeset -A AT=(hook 500 today 4500 article 14500 ask 24500 discover 34500 web 43000 ajin 50500 outro 56000)
KEYS=(hook today article ask discover web ajin outro)

lufs() { ffmpeg -hide_banner -nostats -i "$1" -af ebur128 -f null - 2>&1 | awk '/Summary/{s=1} s&&/I:/{print $2; exit}' }

# 1. 旁白轨
inputs=(); filt=""; i=0
for k in $KEYS; do
  inputs+=(-i $N/$k.aiff)
  filt+="[${i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay=${AT[$k]}:all=1[v$i];"
  i=$((i+1))
done
mixin=""; for j in {0..7}; do mixin+="[v$j]"; done
filt+="${mixin}amix=inputs=8:normalize=0:duration=longest,apad=whole_dur=60,atrim=0:60[o]"
ffmpeg -v error -y $inputs -filter_complex "$filt" -map "[o]" -ar 48000 $W/voice_raw.wav
vgain=$(( -16 - $(lufs $W/voice_raw.wav) ))
ffmpeg -v error -y -i $W/voice_raw.wav -af "volume=${vgain}dB" -ar 48000 $W/voice.wav

# 2. 配乐轨：空档处约 -22 LUFS
ffmpeg -v error -y -ss $START -t 60 -i $MUSIC -af "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo" $W/bed_raw.wav
bgain=$(( -22 - $(lufs $W/bed_raw.wav) ))
ffmpeg -v error -y -i $W/bed_raw.wav -af "volume=${bgain}dB,afade=t=in:d=0.8,afade=t=out:st=57:d=3" -ar 48000 $W/bed.wav

# 3. 压低配乐 + 叠加旁白
ffmpeg -v error -y -i $W/bed.wav -i $W/voice.wav -filter_complex \
  "[0:a][1:a]sidechaincompress=threshold=0.015:ratio=4:attack=30:release=500:makeup=1[d];[d][1:a]amix=inputs=2:normalize=0[o]" \
  -map "[o]" -ar 48000 $W/mix_raw.wav
mgain=$(( -14 - $(lufs $W/mix_raw.wav) ))
ffmpeg -v error -y -i $W/mix_raw.wav -af "volume=${mgain}dB,alimiter=limit=0.84:level=0,aresample=48000" -t 60 -c:a aac -b:a 192k -ar 48000 $OUT/$NAME.m4a
echo "$OUT/$NAME.m4a  voice ${vgain}dB  bed ${bgain}dB  master ${mgain}dB"
