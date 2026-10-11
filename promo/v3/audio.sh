#!/bin/zsh
# v3 音轨：《雨》30 秒段 + CC0 音效（Kenney / OpenGameArt，见 v2/assets/SOURCES.md）+ edge-tts 云健旁白
# 用法: promo/v3/audio.sh [曲名 起点秒]，默认 雨 128.06
set -euo pipefail
cd "${0:A:h}/../.."
TRACK=${1:-雨}; START=${2:-128.06}
V=output/promo-video/v3; FX=output/promo-video/v2/assets/sfx; W=$V/audio_work; mkdir -p $W

lufs() { ffmpeg -hide_banner -nostats -i "$1" -af ebur128 -f null - 2>&1 | awk '/Summary/{s=1} s&&/I:/{print $2; exit}' }

# 音效时间表：名字 时间(秒) 增益(dB)，对应 compose.py 的 timeline
typeset -a EV
EV+=(impact_hit.ogg 0.06 -4  impact_hit.ogg 0.18 -8  whoosh_1.wav 0.4 -6  pop.ogg 0.8 -8  pop.ogg 0.95 -8)
EV+=(tap.ogg 1.0 -6  tap.ogg 1.1 -6)
EV+=(impact_hit.ogg 4.0 -6  impact_hit.ogg 5.0 -6  impact_hit.ogg 6.0 -6  impact_hit.ogg 7.0 -5)
EV+=(riser.wav 6.0 -2  impact_boom.ogg 8.0 -2  camera_shutter.ogg 8.0 -10)
for c in 10.0 12.5 15.0 17.0 19.5 22.0; do EV+=(whoosh_2.wav $(( c - 0.15 )) -8  pop.ogg $(( c + 0.35 )) -12); done
EV+=(glitch_burst.wav 12.4 -10  glitch_burst.wav 16.9 -10)
EV+=(ding.ogg 22.6 -10  impact_boom.ogg 24.5 -6  swish_short.wav 27.4 -6  impact_hit.ogg 27.5 -6  ding.ogg 28.3 -8)

inputs=(); filt=""; i=0
for name at gain in $EV; do
  inputs+=(-i $FX/$name)
  ms=$(printf "%.0f" $(( at * 1000 )))
  filt+="[${i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=${gain}dB,adelay=${ms}:all=1[e$i];"
  i=$(( i + 1 ))
done
mix=""; for j in $(seq 0 $(( i - 1 ))); do mix+="[e$j]"; done
filt+="${mix}amix=inputs=$i:normalize=0,apad=whole_dur=30,atrim=0:30[o]"
ffmpeg -v error -y $inputs -filter_complex "$filt" -map "[o]" -ar 48000 $W/sfx.wav

# 旁白
inputs=(); filt=""; i=0
while IFS='|' read -r key at txt; do
  [[ -z $key ]] && continue
  inputs+=(-i $V/tts/$key.wav)
  ms=$(printf "%.0f" $(( at * 1000 )))
  filt+="[${i}:a]aformat=sample_fmts=fltp:channel_layouts=stereo,adelay=${ms}:all=1[v$i];"
  i=$(( i + 1 ))
done < promo/v3/lines.txt
mix=""; for j in $(seq 0 $(( i - 1 ))); do mix+="[v$j]"; done
filt+="${mix}amix=inputs=$i:normalize=0,apad=whole_dur=30,atrim=0:30[o]"
ffmpeg -v error -y $inputs -filter_complex "$filt" -map "[o]" -ar 48000 $W/voice_raw.wav
ffmpeg -v error -y -i $W/voice_raw.wav -af "volume=$(( -15 - $(lufs $W/voice_raw.wav) ))dB" -ar 48000 $W/voice.wav

# 配乐（原曲母带真峰值过 0 dBTP，先降 4 dB）
ffmpeg -v error -y -ss $START -t 30 -i music/$TRACK.mp3 -vn -af \
  "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=-4dB,afade=t=out:st=28.3:d=1.7" $W/bed_raw.wav
ffmpeg -v error -y -i $W/bed_raw.wav -af "volume=$(( -19 - $(lufs $W/bed_raw.wav) ))dB" -ar 48000 $W/bed.wav

ffmpeg -v error -y -i $W/bed.wav -i $W/voice.wav -i $W/sfx.wav -filter_complex \
  "[0:a][1:a]sidechaincompress=threshold=0.02:ratio=4:attack=20:release=350:makeup=1[d];[d][1:a][2:a]amix=inputs=3:normalize=0[o]" \
  -map "[o]" -ar 48000 $W/mix_raw.wav
ffmpeg -v error -y -i $W/mix_raw.wav -af "alimiter=limit=0.7:level=0:attack=1:release=60" -ar 48000 $W/mix_lim.wav
read -r mi mtp mlra mth moff <<< $(ffmpeg -hide_banner -nostats -i $W/mix_lim.wav -af loudnorm=I=-14:TP=-2.2:LRA=11:print_format=json -f null - 2>&1 \
  | python3 -c "import sys,json,re; d=json.loads(re.search(r'\{.*\}', sys.stdin.read(), re.S).group()); print(d['input_i'], d['input_tp'], d['input_lra'], d['input_thresh'], d['target_offset'])")
ffmpeg -v error -y -i $W/mix_lim.wav -af "loudnorm=I=-14:TP=-2.2:LRA=11:measured_I=${mi}:measured_TP=${mtp}:measured_LRA=${mlra}:measured_thresh=${mth}:offset=${moff}:linear=true,aresample=48000" \
  -t 30 -c:a aac -b:a 192k -ar 48000 $V/audio.m4a
echo "$V/audio.m4a"
