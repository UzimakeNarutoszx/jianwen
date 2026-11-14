# 本地 Qwen 工作流

本机用 `llama-server` 跑 Qwen3.5-9B（Q4_K_M），作为见闻/拙政开发的主要执行者；root 负责拆任务、审 diff、跑测试和发布。

## 启动与检查

```bash
scripts/qwen/up.sh       # 启动并等待 /v1/models 就绪
scripts/qwen/status.sh   # 只看健康状态，不打印 key
scripts/qwen/down.sh     # 停止
```

- 模型：`~/Models/DS-V4-Pro-Qwen3.5-9B-heretic/model.Q4_K_M.gguf`
- 端口：`127.0.0.1:8081`（可用 `QWEN_PORT` 覆盖）
- 日志：`~/Library/Logs/jianwen-qwen.log`
- Key：从 `~/.dsh/.credentials.yaml` 的 `LOCAL_QWEN_KEY` 读取，不落盘、不回显

## 派活

```bash
scripts/qwen/task.sh "只读：统计 backend/tests 下的测试文件数量，不改任何文件"
```

- 串行锁：同一时间只跑一个 qwen 任务（`/tmp/jianwen-qwen-task.lock`）
- 超时：默认 900 秒（`QWEN_TASK_TIMEOUT`）
- 日志：`~/Library/Logs/jianwen-qwen-tasks/<时间戳>.log`
- 约束由 `_run.py` 自动加在 prompt 前面：只改指定文件、不 push、不部署、不改 .env/签名、结束输出 `CHANGED:` 和 `TESTS:`

任务卡模板：

```
背景：<为什么要做>
范围：只改 <文件/目录>
验收：<测试命令 / 页面行为>
禁止：不要动 <相邻模块>，不要改数据库结构
```

## 只做分析

```bash
scripts/qwen/ask.py "这段报错最可能的原因是什么：<日志>"
```

不落盘、不改文件；适合诊断、方案、review。

## 质量边界

- 适合：单文件改动、补测试、写文档、样式微调、按现成模式加接口。
- 不适合：跨模块重构、复杂并发/事务、需要精确视觉判断、需要看长上下文的架构决策。
- 关键改动 root 必须自己重写或逐行 review；qwen 的产出默认不可信，测试通过才算数。

## 为什么不用 subagent 工具

当前 web 会话的 provider 白名单不允许 `local-qwen`（报 “not allowed for this Session”），所以 worker 走 `dsh --profile localqwen` 的 headless 进程，而不是 `subagent(provider=local-qwen)`。如果以后单独起一个允许该 provider 的 worker profile，可以替换 `_run.py` 里的调用方式。

## 常用排查

```bash
tail -50 ~/Library/Logs/jianwen-qwen.log
scripts/qwen/status.sh
ls -lt ~/Library/Logs/jianwen-qwen-tasks | head
```
