#!/usr/bin/env bash
# Stop the local Qwen llama-server started by up.sh.
set -euo pipefail

PIDFILE="${QWEN_PIDFILE:-$HOME/Library/Logs/jianwen-qwen.pid}"
PORT="${QWEN_PORT:-8081}"

if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$PID" 2>/dev/null || break
      sleep 0.5
    done
    kill -9 "$PID" 2>/dev/null || true
  fi
  rm -f "$PIDFILE"
  echo "qwen stopped"
else
  echo "no pid file; trying pkill on port $PORT"
  pkill -f "llama-server.*--port $PORT" 2>/dev/null || true
fi
