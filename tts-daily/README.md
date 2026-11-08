# 今日朗读 TTS 流水线

每天 06:00 后把「见闻」今日 5 篇文章合成 4 种声音的 mp3，上传到服务器，供
`GET /api/v1/content/today/audio` 和前端播放器使用。格式约定见
`../docs/today-audio-contract.md`（manifest、声音 id、路径以那份为准）。

## 文件

| 文件 | 作用 |
|---|---|
| `generate.py` | 取文章 → 切句 → 逐句合成 → ffmpeg 拼 mp3 → 写 `out/<date>/manifest.json` |
| `upload.sh` | rsync 到 `aliyun:/opt/jianwen/backend/uploads/tts/<date>/`，最后传 manifest；修权限、删 7 天前目录 |
| `run.sh` | generate + upload，日志写 `logs/<date>.log`；当日已上传则直接退出 |
| `com.jianwen.tts-daily.plist` | launchd 定时（每天 06:20、07:00） |

## 用法

```bash
tts-daily/run.sh                      # 生成并上传今天（Asia/Shanghai 06:00 换日）
tts-daily/generate.py                 # 只生成，不传
tts-daily/generate.py --date 2026-11-08 --limit-articles 1   # 只做第一篇
tts-daily/generate.py --voices jianwen --max-sentences 3     # 调试：单声音、前 3 句
tts-daily/generate.py --from-json /tmp/articles.json         # 离线：本地 JSON 代替 API
tts-daily/upload.sh 2026-11-08        # 只上传某天
```

- `--from-json` 接受「文章列表」或 `{"articles": [...]}`；API 的 `/api/v1/content/today`
  只有摘要（没有 `sections`），要传给 `--from-json` 得是逐篇 detail 拼起来的完整文章。
- 声音：`jianwen`（1.7B Base ICL 克隆，参考音频取自拙政 promo 的 `voice_ref/ref.wav`）、
  `dylan`（0.6B CustomVoice）。每种模型只加载一次。
- 缓存：句子缓存在 `out/cache/`，键 = 文本 + 声音 + 流程版本；文本没变直接复用，
  改流程就把 `generate.py` 里的 `VERSION` +1。整篇缓存命中时几乎不耗时。
- Python 用 `~/.local/share/qwen3-tts/venv/bin/python`（mlx-audio），脚本不在该 venv 里会自动切过去。

## 安装 launchd

```bash
cp tts-daily/com.jianwen.tts-daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jianwen.tts-daily.plist
launchctl list | grep jianwen            # 看是否注册
launchctl start com.jianwen.tts-daily    # 立刻跑一次试
launchctl unload ~/Library/LaunchAgents/com.jianwen.tts-daily.plist   # 卸载
```

launchd 在机器休眠时不会补跑，所以排了 06:20 和 07:00 两班；`run.sh` 靠
`logs/<date>.uploaded` 标记去重，跑两次不会重复生成或重复上传。
想重跑某天：删掉 `logs/<date>.uploaded` 再执行 `run.sh <date>`。

## 排错

1. `logs/<date>.log` 是主日志（generate 和 upload 都写这里），
   `logs/launchd.out.log` / `launchd.err.log` 只有 launchd 自身的信息。
2. 只有某个声音缺 mp3：看日志里那行 `失败：...`；单个声音失败不会中断其他声音，
   manifest 会缺这个声音，前端按约定禁用或回退默认声音。重跑会补上（其他声音走缓存）。
3. `AttributeError: 'NoneType' ... read` 之类多半是 mlx/soundfile 导入顺序问题，
   用 venv 的解释器直接跑 `generate.py` 复现（脚本首行会自己切 venv）。
4. 上传失败：先手动 `ssh aliyun ls /opt/jianwen/backend/uploads/tts/` 确认连通；
   `upload.sh` 会先校验 manifest 的 `date` 与目标日期一致，不一致直接中止。
5. 前端一直显示「今日朗读生成中」= 服务器上 `tts/<date>/manifest.json` 不存在或解析失败，
   或 `articles[].article_id` 与当日 `_today_articles(db)` 不匹配（manifest 只保留匹配项）。
6. 磁盘：`out/` 会累积每天 mp3（约 5 篇 × 4 声音 × 2MB ≈ 40MB/天），
   不需要留的日期直接删 `out/<date>`；`out/cache/` 是句子缓存，别随手删。
