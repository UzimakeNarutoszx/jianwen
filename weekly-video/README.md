# 见闻每周视频

独立的 Remotion + Blender 制作工程。节目向所有访客公开，网站只读取 `webpage/data/weekly-videos.json`，不依赖登录、个人偏好或另一个周报。此工程不启动定时任务、不写数据库，也不修改宣传片工程。

## 首期

`2026-W42`，采编截至北京时间 2026-10-17 18:30，覆盖 10 月 12—18 日这一周。首期约 4 分 54 秒，1920×1080、30fps；两篇站内文章、公开更新回看、进出口与秋粮两条大事。事实与编辑判断分开表达。

首期已导出正式 MP4，并发布到当前本地网站的公开节目清单，页面可手动点播；封面、章节和字幕一并提供。没有虚构往期，Studio 预览继续保留。当前发布地址为 `http://127.0.0.1:8765/weekly-video.html?episode=2026-W42`；尚未执行远程服务器部署。

## 预览与导出

```sh
cd weekly-video
npm ci
npm run dev
# http://localhost:3016/WeeklyVideo
npm run lint
npm test
npm run cover
npm run render
```

视频输出到 `output/weekly-video/<期号>/episode.mp4`。封面及逐句计时的 VTT/SRT 保存在 `public/episodes/<期号>/`。视频导出不是启动预览的必要步骤。

检查完整视频后，本地发布：

```sh
python3 scripts/publish.py 2026-W42 --video ../output/weekly-video/2026-W42/episode.mp4
```

发布工具检查 H.264/AAC、分辨率、帧率、时长、封面和字幕，复制媒体后才原子更新公开清单。拒绝覆盖同一期历史节目。网站支持 `weekly-video.html?episode=2026-W42`，公开节目按发布时间倒序，当前自然周优先置顶。无本周新片时显示“最近一期”。

## 下一期

1. 复制 `episodes/2026-W42/episode.json` 到新期号目录，修改期号、日期、文章、来源、旁白和画面文案。保持五个章节名称：片头导读、本周重点文章、本周见闻更新、大事总结、片尾来源。
2. 保存核验来源与站内文章快照。新闻按发布日期核对，开发中的功能不算公开更新。
3. `npm run prepare -- 2026-W43`，生成音轨、逐句字幕和带时间的脚本快照。时长必须为 180–300 秒。
4. `node scripts/select-episode.mjs 2026-W43`，切换 Studio 模板。既有期的内容、字幕和媒体均保留。
5. 导出封面、检查 Studio、导出视频，再执行发布命令。若需要先展示制作中的预告，仅修改公开清单的 `upcoming`，不把草稿加入 `episodes`。

每期模板统一读取所选快照；修改新期文案不会重写旧期脚本。需要重渲染某一期时先选择对应期号。已发布媒体不自动重建。

## 旁白

旧交接文档记载的是通义开源 CosyVoice3，但模型与脚本已删除，并未配置千问云端 API。本工程已另行安装 **Qwen3-TTS 0.6B CustomVoice 4bit / MLX-Audio 0.5.9**，默认使用 Vivian 中文音色，完全在本机生成，不需要 API key 或云端付费额度。音轨可用 `--tempo` 调整节奏，FFmpeg 保持音高。

独立 Python 3.12 环境位于 `~/.local/share/qwen3-tts/venv`，约 1.6 GB 模型权重位于 Hugging Face 本地缓存。安装来源为 [MLX-Audio](https://github.com/Blaizzy/mlx-audio) 与 [Qwen3-TTS 的 MLX 模型](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-4bit)，模型标注 Apache-2.0 授权。重新安装：

```sh
uv venv --python 3.12 ~/.local/share/qwen3-tts/venv
uv pip install --python ~/.local/share/qwen3-tts/venv/bin/python -r qwen-requirements.txt
npm run prepare -- 2026-W42 --tempo 1.25
```

可通过 `QWEN_RUNTIME_PYTHON` 指定别处的 Python 环境。模型只加载一次，逐段生成，已完成片段按文本与音色缓存，调整节奏无需重新推理。时长不在 3–5 分钟时保留现有预览。字幕时间来自每个实际语音片段的时长，非按全文平均分配。

用户已在本任务中明确确认《憩》《柱》《雨》《岚》《终》均为自己的原创，可以用于配乐，清单保存在 `music-library.json`。首期使用《雨》，文件标签作者为昔日烬，交接记录（2026-10-11）也记载其原创归属。原文件保留，单独快照在本期 `music/` 中。Caravan 记为用户推荐的可用候选，实际使用前核对具体版本的词曲、编曲和录音授权，不将免费收听等同于公共领域。来源与 SHA-256 记录在本期 `provenance.json`，片尾显示配乐署名。

```bash
# 首次指定原曲；以后从本期快照重新混音
python3 scripts/mix-music.py 2026-W42 --source '/Users/ens/Music/已完成文件/雨.mp3'
python3 scripts/mix-music.py 2026-W42
```

混音将音乐设为 -30 LUFS 底乐，旁白出现时自动压低；循环接点交叉淡化 3 秒，片头淡入 3 秒、片尾淡出 5 秒。成品目标 -16 LUFS、峰值上限 -1.5 dBTP。原始 `narration.m4a` 保留，Studio 和导出使用同一个带内容哈希的混音文件，避免旁白重复叠加。**每次重新生成旁白后，先重新运行混音，再预览或导出**；生成旁白会清除时间线中的旧混音引用，自动回退到纯旁白，避免使用过期声音。

原先的 macOS Tingting 版本已备份到 `output/weekly-video/2026-W42/macos-backup/`，仍可通过 `npm run prepare:macos -- 2026-W42` 生成系统语音备选。

如已有自己的 CosyVoice 命令，可显式传入：

```sh
python3 scripts/prepare.py 2026-W43 --tts-command '/path/to/python /path/to/synth.py --text {text} --output {output}'
```

该命令逐句调用，不经过 shell；输出需为 FFmpeg 可读取的音频。也可用 `--voice`、`--rate` 调整本机语音。更换旁白后重新生成时间轴，避免旧字幕与新语音错位。

## Blender 资产

已用本机 Blender 5.2.2 LTS 实际渲染。`blender/identity.py` 原创建模三层编辑纸页与金色圆环，分别对应阅读、更新、事件与串联的一周；作为片头、章节转场及片尾画面。

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b -t 4 --python blender/identity.py
ffmpeg -y -framerate 30 -i public/identity/frame-%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart public/identity/identity.mp4
ffmpeg -y -i public/identity/frame-0072.png -frames:v 1 -update 1 public/identity/hold.jpg
```

保留 `.blend`、脚本、视频和静帧。中间 PNG、依赖、音频工作缓存与最终导出目录不进入 Git。三维源素材为 960×540，编排画布与视频导出为 1920×1080。

## 验证

从仓库根目录运行 `node webpage/tests/site-pages.mjs` 和 `node --test webpage/tests/weekly-video.test.mjs`。覆盖导航、北京时间跨周、置顶、草稿过滤、往期链接和字幕连续性。浏览器另检查桌面/手机、登录前后内容一致、章节跳转、前进后退和媒体失败。
