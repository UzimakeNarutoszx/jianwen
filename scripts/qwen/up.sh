#!/usr/bin/env bash
# Start the local Qwen llama-server used by scripts/qwen/*.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODEL="${QWEN_MODEL:-$HOME/Models/DS-V4-Pro-Qwen3.5-9B-heretic/model.Q4_K_M.gguf}"
PORT="${QWEN_PORT:-8081}"
HOST="${QWEN_HOST:-127.0.0.1}"
LOG="${QWEN_LOG:-$HOME/Library/Logs/jianwen-qwen.log}"
PIDFILE="${QWEN_PIDFILE:-$HOME/Library/Logs/jianwen-qwen.pid}"
CREDS="${DSH_CREDENTIALS:-$HOME/.dsh/.credentials.yaml}"

mkdir -p "$(dirname "$LOG")"

if [ ! -f "$MODEL" ]; then
  echo "model not found: $MODEL" >&2
  exit 1
fi

KEY="$(python3 - "$CREDS" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
if not path.exists():
    print('')
    raise SystemExit(0)
for line in path.read_text().splitlines():
    if 'LOCAL_QWEN_KEY' in line and ':' in line:
        print(line.split(':', 1)[1].strip().strip('"').strip("'"))
        break
PY
)"

if [ -z "$KEY" ]; then
  echo "LOCAL_QWEN_KEY not found in $CREDS" >&2
  exit 1
fi

health() {
  curl -fsS -m 3 \
    -H "Authorization: Bearer $KEY" \
    "http://$HOST:$PORT/v1/models" >/dev/null 2>&1
}

if health; then
  echo "qwen already healthy on http://$HOST:$PORT"
  exit 0
fi

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "qwen process $(cat "$PIDFILE") exists but not healthy; see $LOG" >&2
  exit 1
fi

echo "starting llama-server..."
nohup /opt/homebrew/bin/llama-server \
  -m "$MODEL" \
  --host "$HOST" --port "$PORT" \
  -c "${QWEN_CTX:-16384}" \
  --parallel 1 \
  -ngl "${QWEN_GPU_LAYERS:-99}" \
  --api-key "$KEY" \
  --no-webui \
  >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"

for _ in $(seq 1 120); do
  if health; then
    python3 - "$HOST" "$PORT" "$KEY" <<'PY'
import json, sys, urllib.request
host, port, key = sys.argv[1], sys.argv[2], sys.argv[3]
req = urllib.request.Request(
    f"http://{host}:{port}/v1/models",
    headers={"Authorization": f"Bearer {key}"},
)
with urllib.request.urlopen(req, timeout=5) as response:
    data = json.load(response)
items = data.get("data") or data.get("models") or []
ids = [item.get("id") or item.get("model") or item.get("name") for item in items]
print("qwen ready:", ", ".join(str(i) for i in ids if i) or "(no model id)")
PY
    exit 0
  fi
  sleep 1
done

echo "qwen did not become healthy in 120s; tail of $LOG:" >&2
tail -20 "$LOG" >&2 || true
exit 1
