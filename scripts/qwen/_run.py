#!/usr/bin/env python3
"""Run one headless task with the local Qwen profile, serialized and timed out."""
import fcntl
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CWD = Path(os.environ.get("QWEN_CWD", ROOT)).resolve()
LOCK = Path("/tmp/jianwen-qwen-task.lock")
LOG_DIR = Path(os.environ.get("QWEN_TASK_LOG_DIR", Path.home() / "Library/Logs/jianwen-qwen-tasks"))
TIMEOUT = int(os.environ.get("QWEN_TASK_TIMEOUT", "600"))

PREAMBLE = """你在见闻仓库里执行一个受控的开发任务。硬性约束：
- 只修改任务里明确提到的文件或目录；先读后改。
- 不执行 git push、不部署、不改 .env / 签名 / 生产配置，不删除用户文件。
- 完成后必须输出两行：CHANGED: <逗号分隔的文件> 和 TESTS: <执行的命令与结果>。
- 如果任务无法完成，输出 BLOCKED: <原因>，不要假装完成。

任务：
"""


def main() -> int:
    args = " ".join(sys.argv[1:]).strip()
    if not args and not sys.stdin.isatty():
        args = sys.stdin.read().strip()
    if not args:
        print("usage: task.sh <task>  (or pipe task via stdin)", file=sys.stderr)
        return 2

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}.log"
    prompt = PREAMBLE + args
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"cwd={CWD}\n\n{prompt}\n\n")
        log.flush()
        with LOCK.open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            started = time.time()
            process = subprocess.Popen(
                ["dsh", "--profile", "localqwen", prompt],
                cwd=CWD,
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            timed_out = False
            try:
                process.wait(timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.kill()
                process.wait(timeout=10)
            log.write(f"\n[qwen] {time.time() - started:.1f}s timed_out={timed_out}\n")

    print(log_path.read_text(encoding="utf-8", errors="ignore"))
    return 1 if timed_out else (process.returncode or 0)


if __name__ == "__main__":
    raise SystemExit(main())
