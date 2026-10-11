#!/bin/zsh
# v2 音轨：《雨》30 秒段 + 本地合成音效（whoosh / 冲击 / drop 前上升音）+ 短旁白
# 音效全部用 ffmpeg lavfi 合成，无版权问题。
# 用法: promo/v2/audio.sh [曲名 起点秒]，默认 雨 128.06
set -euo pipefail
cd "${0:A:h}/../.."
TRACK=${1:-雨}; START=${2:-128.06}
V=output/promo-video/v2
S=$V/sfx; N=$V/narration; mkdir -p $S

lufs() { ffmpeg -hide_banner -nostats -i "$1" -af ebur128 -f null - 2>&1 | awk '/Summary/{s=1} s&&/I:/{print $2; exit}' }

# ---- 合成音效 ----
# whoosh：带通扫频的粉噪，0.35 秒
ffmpeg -v error -y -f lavfi -i "anoisesrc=d=0.35:c=pink:a=0.9" -af \
  "highpass=f=300,lowpass=f=6000,afade=t=in:d=0.12,afade=t=out:st=0.14:d=0.21,volume=0.8,aformat=channel_layouts=stereo,aresample=48000" $S/whoosh.wav
# impact：低频正弦下滑 + 短噪声，0.6 秒
ffmpeg -v error -y -f lavfi -i "aevalsrc='0.9*sin(2*PI*(55+90*exp(-14*t))*t)*exp(-6*t)':d=0.6:s=48000" \
  -f lavfi -i "anoisesrc=d=0.08:c=white:a=0.5" -filter_complex \
  "[1:a]highpass=f=1500,afade=t=out:d=0.08[n];[0:a][n]amix=inputs=2:normalize=0,aformat=channel_layouts=stereo" $S/impact.wav
# riser：drop 前 2 秒，音高和音量一起上升
ffmpeg -v error -y -f lavfi -i "aevalsrc='0.5*(t/2)^2*sin(2*PI*(200*t+300*t*t))':d=2:s=48000" \
  -f lavfi -i "anoisesrc=d=2:c=pink:a=0.6" -filter_complex \
  "[1:a]highpass=f=800,volume='(t/2)^3':eval=frame[n];[0:a][n]amix=inputs=2:normalize=0,aformat=channel_layouts=stereo" $S/riser.wav
# tick：每拍关键词的短促点击声
ffmpeg -v error -y -f lavfi -i "aevalsrc='0.6*sin(2*PI*2200*t)*exp(-60*t)':d=0.08:s=48000" -af aformat=channel_layouts=stereo $S/tick.wav

# ---- 音效时间表（秒），与 compose.py 的 timeline 对应 ----
typeset -a EV
EV+=(impact 0.12 impact 0.62)                                   # 开场砸字
EV+=(whoosh 1.85)                                               # 手机甩入
EV+=(tick 6.0 tick 6.5 tick 7.0 tick 7.5)                       # 4 拍关键词
EV+=(riser 6.0 impact 8.0)                                      # drop
for c in 10.0 12.5 15.0 17.0 19.5 22.0; do EV+=(whoosh $(( c - 0.12 ))); done
EV+=(impact 24.5 impact 27.5)                                   # 阿烬、片尾

inputs=(); filt=""; i=0
for name at in $EV; do
  inputs+=(-i $S/$name.wav)
  ms=$(printf "%.0f" $(( at * 1000 )))
  filt+="[${i}:a]adelay=${ms}:all=1[e$i];"
  i=$(( i + 1 ))
done
mix=""; for j in $(seq 0 $(( i - 1 ))); do mix+="[e$j]"; done
filt+="${mix}amix=inputs=$i:normalize=0,apad=whole_dur=30,atrim=0:30[o]"
ffmpeg -v error -y $inputs -filter_complex "$filt" -map "[o]" -ar 48000 $V/sfx_track.wav

# ---- 旁白轨 ----
inputs=(); filt=""; i=0
while IFS='|' read -r key at txt; do
  [[ -z $key ]] && continue
  inputs+=(-i $N/$key.aiff)
  ms=$(printf "%.0f" $(( at * 1000 )))
  filt+="[${i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay=${ms}:all=1[v$i];"
  i=$(( i + 1 ))
done < promo/v2/lines.txt
mix=""; for j in $(seq 0 $(( i - 1 ))); do mix+="[v$j]"; done
filt+="${mix}amix=inputs=$i:normalize=0,apad=whole_dur=30,atrim=0:30[o]"
ffmpeg -v error -y $inputs -filter_complex "$filt" -map "[o]" -ar 48000 $V/voice_raw.wav
ffmpeg -v error -y -i $V/voice_raw.wav -af "volume=$(( -15 - $(lufs $V/voice_raw.wav) ))dB" -ar 48000 $V/voice.wav

# ---- 配乐：去封面流，-4 dB 先留余量（原曲母带真峰值已过 0 dBTP） ----
ffmpeg -v error -y -ss $START -t 30 -i music/$TRACK.mp3 -vn -af \
  "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=-4dB,afade=t=out:st=28.3:d=1.7" $V/bed_raw.wav
ffmpeg -v error -y -i $V/bed_raw.wav -af "volume=$(( -19 - $(lufs $V/bed_raw.wav) ))dB" -ar 48000 $V/bed.wav

# ---- 混合：旁白压低配乐，音效叠加，整体 -14 LUFS 限幅 ----
ffmpeg -v error -y -i $V/bed.wav -i $V/voice.wav -i $V/sfx_track.wav -filter_complex \
  "[0:a][1:a]sidechaincompress=threshold=0.02:ratio=4:attack=20:release=350:makeup=1[d];[2:a]volume=-6dB[fx];[d][1:a][fx]amix=inputs=3:normalize=0[o]" \
  -map "[o]" -ar 48000 $V/mix_raw.wav
# 两遍 loudnorm（线性模式，真峰值上限 -2.2 dBTP，给 AAC 编码过冲留余量），先限幅掉音效瞬态
ffmpeg -v error -y -i $V/mix_raw.wav -af "alimiter=limit=0.7:level=0:attack=1:release=60" -ar 48000 $V/mix_lim.wav
read -r mi mtp mlra mth moff <<< $(ffmpeg -hide_banner -nostats -i $V/mix_lim.wav -af loudnorm=I=-14:TP=-2.2:LRA=11:print_format=json -f null - 2>&1 \
  | python3 -c "import sys,json,re; d=json.loads(re.search(r'\{.*\}', sys.stdin.read(), re.S).group()); print(d['input_i'], d['input_tp'], d['input_lra'], d['input_thresh'], d['target_offset'])")
ffmpeg -v error -y -i $V/mix_lim.wav -af "loudnorm=I=-14:TP=-2.2:LRA=11:measured_I=${mi}:measured_TP=${mtp}:measured_LRA=${mlra}:measured_thresh=${mth}:offset=${moff}:linear=true,aresample=48000" \
  -t 30 -c:a aac -b:a 192k -ar 48000 $V/audio_${TRACK}.m4a
echo "$V/audio_${TRACK}.m4a"
