# 今日朗读 TTS 流水线

每天 06:00 后把「见闻」今日 5 篇文章合成 2 种声音的 mp3，上传到服务器，供
`GET /api/v1/content/today/audio` 和前端播放器使用。格式约定见
`../docs/today-audio-contract.md`（manifest、声音 id、路径以那份为准）。

## 文件

| 文件 | 作用 |
|---|---|
| `generate.py` | 取文章 → 数字规范化 → 切句 → 逐句合成 → ASR 自检重读 → ffmpeg 拼 mp3 → 写 `out/<date>/manifest.json` |
| `textnorm.py` | 阿拉伯数字 → 中文读法（纯标准库，可单独 `python3 -c "import textnorm"` 用） |
| `asr_check.py` | 用本地 Qwen3-ASR 回听成品，和原文比对打分；也可当命令行工具单跑 |
| `tests/` | 单元测试（`unittest`，标准库即可，不依赖 mlx） |
| `upload.sh` | rsync 到 `aliyun:/opt/jianwen/backend/uploads/tts/<date>/`，最后传 manifest；修权限、删 7 天前目录 |
| `run.sh` | generate + upload，日志写 `logs/<date>.log`；当日已上传则直接退出 |
| `com.jianwen.tts-daily.plist` | launchd 定时（每天 06:20、07:00）——**已停用**，仅作 Mac 回退 |
| `server/` | 服务器端流水线（edge-tts + ffmpeg、systemd 定时），线上实际使用 |

## 数字读错的问题与修法

`dylan`（0.6B CustomVoice）会把阿拉伯数字读成乱码，实测原文
「二十一大代表选举启动，2360名代表怎么选」被读成
「二十一大代表选举启动的二新师六零抢车方杠的C抢车队」；`jianwen` 相对稳，但「11月6日」
这类也会读飘。所以合成前先把数字改写成中文，再用 ASR 回听验收：

1. **规范化**（`textnorm.normalize`，在切句前对每句做）：2360 → 两千三百六十、
   2027年 → 二零二七年、11月6日 → 十一月六日、260多万 → 二百六十多万、2.6万 → 二点六万、
   15% → 百分之十五、3%-5% → 百分之三到百分之五、10-20 → 十到二十、5G → 五G、
   手机号/长编号逐位读。已经是中文数字的（二十一大、二零二七年）不动，函数幂等。
2. **自检**（`asr_check.check`）：转写和原文都归一化（数字转中文、去标点、统一两/二）后
   比字符相似度，**另外单独核对原文的每个数字是否都出现在转写里**——只看相似度会被短句稀释
   （「北京时间11月6日晚」读成「北京时间十七月六日晚」还有 0.90）。
   通过线：相似度 ≥ 0.85 且数字不缺。
3. **重读**：某句不过就换随机种子重合成，最多 3 次，留分数最高的一次。
4. **丢弃**：整篇平均分 < 0.85，或低于 0.7 的句子达到 `max(2, 10%)`，则该篇不发这个声音
   （manifest 里缺该声音，前端按约定禁用或回退默认声音）。阈值留 2 句余量是因为
   ASR 自己也有同音字误听（把「警示」听成「定收」），偶发一两句不该让整篇没声音。

自检明细写 `out/qa/<date>.json`（每句分数、缺失数字、用的种子、被丢弃的声音）。
**故意不放进 `out/<date>/`**：那个目录会被 `upload.sh` 整个 rsync 上服务器，
服务器目录要严格按契约。

改了合成流程或规范化规则，把 `generate.py` 里的 `VERSION` +1，旧句子缓存自动失效。

## 服务器端流水线（当前线上方案，不再需要 Mac）

2026-11-09 起，每日朗读改在阿里云服务器上生成，Mac 不必开机：

- 代码：`server/generate_server.py`（文本清洗、数字规范化与 Mac 版一致，合成换成 edge-tts），
  线上目录 `/opt/jianwen/tts/`，venv 里装 `edge-tts==7.3.1`，系统装 `ffmpeg`。
- 声音：`jianwen` → `zh-CN-XiaoxiaoNeural`（+6%），`dylan` → `zh-CN-YunxiNeural`（+6%），
  显示名分别为「见闻」「男声」。声音 id 不变，前端无需改动。
- 输出：直接写 `/opt/jianwen/backend/uploads/tts/<date>/`，属主 `jianwen:jianwen`，
  先落 mp3 最后写 manifest；只保留最近 7 个日期目录。
- 定时：systemd `jianwen-tts.timer`，每天 06:20 / 07:00 / 08:00 / 09:00（Asia/Shanghai）各跑一次，
  已成功（manifest 存在）就跳过；当天文章还没更新时按 article_id 里的日期跳过并退出，等下一班。
- 日志：`/opt/jianwen/tts/logs/<date>.log`。

```bash
# 服务器上手动跑某天（已存在 manifest 时加 --force）
/opt/jianwen/tts/run.sh 2026-11-09
/opt/jianwen/tts/run.sh 2026-11-09 --force
systemctl list-timers jianwen-tts.timer
```

部署/回滚：

```bash
# 部署（本地 → 服务器）
scp tts-daily/server/generate_server.py tts-daily/server/textnorm.py root@8.147.110.194:/opt/jianwen/tts/
scp tts-daily/server/run.sh root@8.147.110.194:/opt/jianwen/tts/
# 定时器
systemctl enable --now jianwen-tts.timer     # 停用：systemctl disable --now jianwen-tts.timer

# 回退到 Mac 生成
launchctl load ~/Library/LaunchAgents/com.jianwen.tts-daily.plist.disabled-20261109
mv ~/Library/LaunchAgents/com.jianwen.tts-daily.plist.disabled-20261109 \
   ~/Library/LaunchAgents/com.jianwen.tts-daily.plist
```

注意：edge-tts 是微软 Edge 朗读服务的非官方接口，2026-10 曾因 Sec-MS-GEC 轮换失效，
本项目固定 7.3.1 并保留四班重试；若再次失效，可临时改回 Mac 版，或换 CosyVoice 等付费接口。

## 用法

```bash
tts-daily/run.sh                      # 生成并上传今天（Asia/Shanghai 06:00 换日）
tts-daily/generate.py                 # 只生成，不传
tts-daily/generate.py --date 2026-11-08 --limit-articles 1   # 只做第一篇
tts-daily/generate.py --voices jianwen --max-sentences 3     # 调试：单声音、前 3 句
tts-daily/generate.py --from-json /tmp/articles.json         # 离线：本地 JSON 代替 API
tts-daily/generate.py --no-asr        # 只做数字规范化，跳过回听自检（更快，质量不保证）
tts-daily/upload.sh 2026-11-08        # 只上传某天
```

- `--from-json` 接受「文章列表」或 `{"articles": [...]}`；API 的 `/api/v1/content/today`
  只有摘要（没有 `sections`），要传给 `--from-json` 得是逐篇 detail 拼起来的完整文章。
- 声音：`jianwen`（1.7B Base ICL 克隆，参考音频取自拙政 promo 的 `voice_ref/ref.wav`）、
  `dylan`（0.6B CustomVoice）。每种模型只加载一次。
- 缓存：句子缓存在 `out/cache/`，键 = 文本 + 声音 + 流程版本；每句旁边有
  `<digest>.qa.json` 存自检结果，整篇命中时直接回收，不重跑 ASR。
- Python 用 `~/.local/share/qwen3-tts/venv/bin/python`（mlx-audio），脚本不在该 venv 里会自动切过去。
  测试只用到标准库，系统 `python3` 就能跑。

## 单独验收某个成品

```bash
# 转写整篇，看数字读得对不对
~/.local/share/qwen3-tts/venv/bin/python tts-daily/asr_check.py \
  tts-daily/out/2026-11-08/ai-daily-20261108-1/dylan.mp3

# 有原文时逐句打分（一行一句）
~/.local/share/qwen3-tts/venv/bin/python tts-daily/asr_check.py <mp3> --text-file /tmp/sents.txt
```

## 测试

```bash
cd tts-daily && python3 -m unittest discover -s tests -v
```

覆盖：整数/小数/日期/年份/百分比/区间/长数字/字母夹数字的读法、幂等性、
「只改数字不动标点」、ASR 比对口径与「数字单独核对」、切句与自检判定逻辑。

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
   如果日志是 `自检整体不过（平均 x.xx），本篇不发布该声音`，看 `out/qa/<date>.json`
   里同名的 `dropped` 项和逐句分数；确认是 ASR 误判（同音字）而不是真读错，
   可以临时 `--no-asr` 重跑该篇，或调 `generate.py` 里的 `ASR_PASS` / `ASR_DROP`。
3. ASR 加载不了（`警告：ASR 不可用`）：模型在
   `~/.cache/huggingface/hub/models--mlx-community--Qwen3-ASR-0.6B-8bit`，
   缺失时流水线会降级为「只做数字规范化」继续跑，不会中断。
4. `AttributeError: 'NoneType' ... read` 之类多半是 mlx/soundfile 导入顺序问题，
   用 venv 的解释器直接跑 `generate.py` 复现（脚本首行会自己切 venv）。
5. 上传失败：先手动 `ssh aliyun ls /opt/jianwen/backend/uploads/tts/` 确认连通；
   `upload.sh` 会先校验 manifest 的 `date` 与目标日期一致，不一致直接中止。
6. 前端一直显示「今日朗读生成中」= 服务器上 `tts/<date>/manifest.json` 不存在或解析失败，
   或 `articles[].article_id` 与当日 `_today_articles(db)` 不匹配（manifest 只保留匹配项）。
7. 磁盘：`out/` 会累积每天 mp3（约 5 篇 × 2 声音 × 2MB ≈ 20MB/天），
   不需要留的日期直接删 `out/<date>`；`out/cache/` 是句子缓存，别随手删。
