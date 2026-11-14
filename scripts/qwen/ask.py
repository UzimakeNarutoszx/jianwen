#!/usr/bin/env python3
"""Ask the local Qwen model for analysis only; never edits files."""
import json
import os
import pathlib
import sys
import urllib.request

HOST = os.environ.get("QWEN_HOST", "127.0.0.1")
PORT = os.environ.get("QWEN_PORT", "8081")
MODEL = os.environ.get("QWEN_MODEL_ID", "model.Q4_K_M.gguf")
CREDS = pathlib.Path(os.environ.get("DSH_CREDENTIALS", pathlib.Path.home() / ".dsh/.credentials.yaml"))


def key() -> str:
    for line in CREDS.read_text().splitlines():
        if "LOCAL_QWEN_KEY" in line and ":" in line:
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("LOCAL_QWEN_KEY missing")


def main() -> int:
    prompt = " ".join(sys.argv[1:]).strip()
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    if not prompt:
        print("usage: ask.py <prompt>  (or pipe via stdin)", file=sys.stderr)
        return 2

    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是资深全栈工程师，用中文回答，结论优先，代码用 markdown。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 2000,
    }
    request = urllib.request.Request(
        f"http://{HOST}:{PORT}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key()}"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        data = json.load(response)
    print(data["choices"][0]["message"]["content"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
