#!/bin/bash
# 今日朗读每日流水线：生成 → 上传。日志写 logs/<date>.log。
# 当日已上传成功（logs/<date>.uploaded 存在）就直接退出，重复触发不会重跑。
# 用法: tts-daily/run.sh [YYYY-MM-DD]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 跟 generate.py 一致：Asia/Shanghai 06:00 前算前一天（两班 06:20 / 07:00 都落在当天内容上）
if [[ -n "${1:-}" ]]; then
  DATE="$1"
else
  DATE="$(TZ=Asia/Shanghai date +%F)"
  [[ "$(TZ=Asia/Shanghai date +%H)" -lt 6 ]] && DATE="$(TZ=Asia/Shanghai date -v-1d +%F)"
fi
LOGDIR="$HERE/logs"
LOG="$LOGDIR/$DATE.log"
MARK="$LOGDIR/$DATE.uploaded"
PY="$HOME/.local/share/qwen3-tts/venv/bin/python"

mkdir -p "$LOGDIR"
log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG"; }

if [[ -f "$MARK" ]]; then
  log "$DATE 已上传成功（${MARK}），跳过"
  exit 0
fi

log "===== 开始 $DATE ====="
[[ -x "$PY" ]] || { log "找不到 ${PY}，无法运行 generate.py"; exit 1; }

if ! "$PY" "$HERE/generate.py" --date "$DATE" >>"$LOG" 2>&1; then
  log "generate.py 失败，看 $LOG"
  exit 1
fi
log "生成完成：$HERE/out/$DATE"

if ! "$HERE/upload.sh" "$DATE" >>"$LOG" 2>&1; then
  log "upload.sh 失败，看 ${LOG}（可手动重跑本脚本）"
  exit 1
fi

date '+%F %T' > "$MARK"
log "===== 完成 $DATE ====="
