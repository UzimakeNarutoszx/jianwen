#!/usr/bin/env bash
# Delegate one task to the local Qwen headless agent.
# Usage: task.sh "任务描述"   (or pipe the task via stdin)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/qwen/_run.py" "$@"
