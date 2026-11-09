#!/bin/bash
# 见闻每日朗读（服务器端）：生成当天 5 篇 × 2 声音，直接写入 backend/uploads/tts/<date>。
# 用法: run.sh [YYYY-MM-DD] [generate_server.py 额外参数...]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -n "${1:-}" && "${1:-}" =~ ^20[0-9]{2}-[0-9]{2}-[0-9]{2}$ ]]; then
  DATE="$1"; shift
else
  DATE="$(TZ=Asia/Shanghai date +%F)"
fi
mkdir -p "$HERE/logs"
LOG="$HERE/logs/$DATE.log"
exec 9>"$HERE/.lock"
if ! flock -n 9; then
  echo "[$(date "+%F %T")] 已有任务在跑，跳过" >>"$LOG"
  exit 0
fi
echo "[$(date "+%F %T")] ===== 开始 $DATE =====" >>"$LOG"
"$HERE/venv/bin/python" "$HERE/generate_server.py" --date "$DATE" "$@" >>"$LOG" 2>&1
echo "[$(date "+%F %T")] ===== 结束 $DATE =====" >>"$LOG"
