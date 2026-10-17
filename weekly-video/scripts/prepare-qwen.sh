#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
QWEN_RUNTIME_PYTHON=${QWEN_RUNTIME_PYTHON:-"$HOME/.local/share/qwen3-tts/venv/bin/python"}
if [ ! -x "$QWEN_RUNTIME_PYTHON" ]; then
  echo 'Qwen runtime missing. See README.md for the isolated MLX installation.' >&2
  exit 1
fi
exec "$QWEN_RUNTIME_PYTHON" scripts/prepare.py --engine qwen3 "$@"
