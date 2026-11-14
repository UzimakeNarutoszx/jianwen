#!/usr/bin/env bash
# Report local Qwen health without printing the API key.
set -euo pipefail

PORT="${QWEN_PORT:-8081}"
HOST="${QWEN_HOST:-127.0.0.1}"
CREDS="${DSH_CREDENTIALS:-$HOME/.dsh/.credentials.yaml}"

KEY="$(python3 - "$CREDS" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
for line in path.read_text().splitlines():
    if 'LOCAL_QWEN_KEY' in line and ':' in line:
        print(line.split(':', 1)[1].strip().strip('"').strip("'"))
        break
PY
)"

if [ -z "$KEY" ]; then
  echo "LOCAL_QWEN_KEY missing" >&2
  exit 2
fi

python3 - "$HOST" "$PORT" "$KEY" <<'PY'
import json, sys, urllib.request
host, port, key = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    req = urllib.request.Request(
        f"http://{host}:{port}/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.load(response)
except Exception as exc:  # noqa: BLE001
    print(f"down: {exc}")
    raise SystemExit(1)

items = data.get("data") or data.get("models") or []
ids = [item.get("id") or item.get("model") or item.get("name") for item in items]
print("up:", ", ".join(str(i) for i in ids if i) or "(no model id)")
PY
