# 见闻项目交接文档

更新时间：2026-10-11 23:00（Asia/Shanghai）。最新进度看第 11 节「工作日志」。项目根目录：`/Users/ens/Thomas的文件/编程/见闻`。

这份文档用于把项目整体交给 Claude 或其他开发者。项目包含 FastAPI 后端、Uni App/H5 前端、独立横屏网站、产品文档、测试和 Git/GitHub 配置。真实密钥不写入本文档。

## 提纲

1. 产品定位与用户链路
2. 目录和软件组成
3. 后端、数据库和 API
4. 前端与独立网站
5. DeepSeek/AI 调用
6. 本地运行和测试
7. Git 与 GitHub
8. 配置与安全
9. 当前状态和接手建议
10. 推荐阅读顺序
11. 工作日志

## 1. 产品定位与用户链路

“见闻”帮助年轻用户理解政策、新闻和公共议题。主链路是：可信公开来源 -> 每日内容生成/筛选 -> 今日页 5 件事 -> 文章详情、三句话总结、来源与依据 -> 问问/阿烬追问 -> 收藏、历史、关注主题和经典阅读进度。

产品总览优先看 `markdown/00-项目地图.md`、`markdown/AI系统总览.md`、`markdown/11-内容生成工作流.md`。页面规格在 `pages_ui/`，产品章节在 `markdown/`。

## 2. 目录和软件组成

| 目录 | 作用 | 技术 |
| --- | --- | --- |
| `backend/` | API、数据库、认证、短信、内容、AI | FastAPI、SQLAlchemy、PyMySQL、Python |
| `frontend/` | Uni App/H5 移动端 | Vue 3、Uni App、Vite |
| `webpage/` | 独立横屏官网和阅读器 | 原生 HTML/CSS/JavaScript |
| `markdown/` | 产品、AI、内容和协议文档 | Markdown |
| `pages_ui/` | 页面 UI 规格 | Markdown |
| `promo/` | 宣传片制作脚本（录屏、Blender、合成、混音、封面） | Python、zsh、Node、Blender |
| `output/` | 不进 Git 的产物；目前只有 v4 宣传片 1080p 原片 | MP4 |

`webpage` 和 `frontend` 是两套不同的前端交付形态：前者直接静态运行，后者需要 Uni App/Vite 构建。

## 3. 后端、数据库和 API

`backend/app/main.py` 创建 FastAPI，挂载静态资源，初始化数据库，并启动每日文章调度器。`backend/app/api/v1/auth.py` 负责短信、注册、登录和忘记密码；`content.py` 负责今日内容、文章、发现、经典文献、页面、问问和阿烬；`profile.py` 负责个人资料、头像、主题、收藏、历史、AI 记录和阅读进度。`models/` 是 SQLAlchemy 模型，`schemas/` 是 Pydantic 结构，`db/` 是连接和初始化。

内容服务包括 `backend/app/services/daily_articles.py`（政府公开素材、AI 生成、校验、本地兜底和每日调度）、`classic_fulltext.py`（经典全文）、`seed_content.py`（种子内容）和 `sms.py`（短信）。`backend/services/ai.py` 是 AI 客户端，`backend/services/prompts.py` 是问问和阿烬提示词。

API 前缀是 `/api/v1`。基础接口有 `/health`、`/`、`/docs`、`/redoc`。认证接口是 `/auth/send-sms`、`/auth/register`、`/auth/login`、`/auth/forgot-password`。内容接口包括 `/content/today`、`/today/personalized`、`/articles`、`/articles/{id}`、`/articles/{id}/related`、`/categories`、`/discover`、`/daily-quote`、`/classic-books`、`/classic-books/{id}/chapters/{chapter_id}`、`/pages/{key}`、`/ask/bootstrap`、`/ask`、`/ask/answer`、`/ask/stream` 和 `/ajin/chat`。个人接口包括资料、头像、主题、收藏、历史、AI 记录、阅读位置和今日清单，完整清单见 `backend/README.md`。

默认数据库是本机 MySQL 的 `ENS_Project`。启动时自动创建数据库/表并执行种子内容。主要表有 `users`、`content_articles`、`content_categories`、`content_features`、`content_pages`、`daily_article_sets`、`daily_quotes`、`classic_books`、`classic_book_chapters`、`ai_prompts`、`ai_answer_rules`、`user_favorite_articles`、`user_browsing_history`、`user_ai_usage_records`、`user_follow_topics`、`user_reading_positions`。当前检查到 MySQL 正在监听 `3306`。

## 4. 前端与独立网站

### Uni App/H5：`frontend/`

页面覆盖今日、发现、问问、个人、文章、经典文献、搜索、收藏、历史、设置和登录。`frontend/utils/api.js` 默认请求 `http://当前主机:8000`，也支持本地缓存 `jianwen_api_base_url` 覆盖；token 存在 `jianwen_auth_token`。进入 `frontend` 后运行 `npm install`，再运行 `npm run dev:h5`；构建使用 `npm run build:h5`。

### 横屏官网：`webpage/`

入口为 `webpage/index.html`，见闻阅读页在 `webpage/jianwen/`，阿烬页是 `webpage/avatar.html`，更新日志是 `webpage/changelog.html`。关键脚本是 `webpage/js/api-browser.js`（API、token、问问、收藏和阅读进度）、`ajin-chat.js`、`article.js`、`reader.js`。从项目根目录运行 `python -m http.server 8765 --bind 127.0.0.1 --directory webpage`，访问 `http://127.0.0.1:8765/index.html`。网站默认请求同一主机的 `8000` 后端。视觉和验收历史见 `webpage/UPGRADE-20260919.md`。

网站发布约定：`js/site.js` 的 `SITE_VERSION`（当前 `20261011-1`）、各 html 里写死的 `?v=`、`tests/site-pages.mjs` 第 39 行要一起改；新增页面要同时改测试里的页面数（当前 11）和 `expected` 列表，否则 `site-pages.mjs` 会失败。

## 5. DeepSeek/AI 调用

AI 使用 OpenAI 兼容的 `/chat/completions`。当前本地配置是 `AI_API_BASE_URL=https://api.aicodewith.com/v1`、`AI_MODEL=deepseek-flash`。后端是 AI 代理层，浏览器不直接携带 AI key；实际供应商由 `AI_API_BASE_URL` 决定，不能仅凭模型名推断供应商。

普通问问从 `POST /api/v1/content/ask` 进入，检查登录和每日额度（默认 20 次），拼接文章/全站上下文与历史，由 `build_ask_messages()` 生成消息，调用 `backend/services/ai.py`，保存 AI 使用记录并返回回答和来源。阿烬从 `POST /api/v1/content/ajin/chat` 进入，使用 `AJIN_SYSTEM_PROMPT` 和 `build_ajin_messages()`；外部模型不可用时，`content.py` 提供本地应急回复。

流式问问从 `POST /api/v1/content/ask/stream` 进入，设置 `stream: true`，解析 SSE `data:` 行并输出文本；前端处理停止、Markdown 安全渲染、复制和重试。

每日文章服务在 Asia/Shanghai 每天 06:00 刷新：从政府公开 JSON 列表抓取素材，要求 AI 生成正好 5 篇文章（标题、说明、三段正文、摘要、来源、引用），再校验长度、数量、引用和风险表达；失败时回退本地种子文章。

AI 配置变量：`AI_API_BASE_URL`、`AI_API_KEY`、`AI_MODEL`、`AI_TIMEOUT_SECONDS`、`AI_USE_ENV_PROXY`、`AI_THINKING_DISABLED`、`AI_TEMPERATURE`、`AI_TOP_P`。真实 `AI_API_KEY` 只放 `backend/.env` 或进程环境。

## 6. 本地运行和测试

后端：进入 `backend`，创建/激活虚拟环境，执行 `pip install -r requirements.txt`，再运行 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`。开发热重载可增加 `--reload`。项目已有 `.venv`、`.venv313`、`.venv314`，不要提交虚拟环境。

后端测试：进入 `backend` 执行 `.venv314/bin/python -m pytest -q`（pytest 8.4.2 只装在 `.venv314`，未写进 requirements）。网站测试包括 `node webpage/tests/site-pages.mjs`、`node webpage/tests/api-smoke.mjs`、`node webpage/tests/reading-api.mjs`、`node webpage/tests/ask.test.cjs` 和 `node webpage/tests/reader.test.cjs`。依赖服务的测试要先启动 `8000` 和 `8765`。历史验收见 `webpage/UPGRADE-20260919.md`。

## 7. Git 与 GitHub

远程仓库是 `https://github.com/UzimakeNarutoszx/jianwen.git`。本地分支为 `main`，GitHub CLI 已登录 `UzimakeNarutoszx`，协议为 HTTPS。

当前状态（2026-10-11 23:00）：本地 `main` 与 `origin/main` 一致，都是 `1f30229`，工作区干净。

接手时先检查 `git status --short --branch` 和 `git log --oneline origin/main..HEAD`，确认后执行 `git push -u origin main`，再用 `git ls-remote origin refs/heads/main` 验证远程提交号。常规备份流程是 `git add -A`、`git commit -m "Describe the change"`、`git push origin main`。

不要强制推送，也不要把 `backend/.env`、token、数据库、用户上传、虚拟环境、`__pycache__` 或密钥加入 Git。过去 GitHub push protection 曾拦截阿里云密钥；相关密钥应在阿里云控制台轮换。

## 8. 配置与安全

本机需要配置但不能公开的变量：`AI_API_KEY`、`MYSQL_PASSWORD`、`SECRET_KEY`、`ALIYUN_DYPNS_ACCESS_KEY_ID`、`ALIYUN_DYPNS_ACCESS_KEY_SECRET`。`backend/.env` 由 `backend/config.py` 加载，进程环境变量优先。短信使用阿里云 DYPNS；开发时可设置 `SMS_PROVIDER=local` 和 `SMS_DEV_CODE`。生产环境必须设置独立的 `SECRET_KEY`，不能使用开发默认值。

用户用手机号注册/登录。头像限制为图片且最大 2MB。GitHub 只保存源代码，不会自动运行 FastAPI、MySQL 或每日调度器。

## 9. 当前状态和接手建议

- Git 已同步，没有未推送的提交。
- 最后一次检查时这些服务在跑：后端 `8000`（`.venv314`，`--reload`）、网站 `8765`、H5 开发服务器 `5173`、MySQL `3306`。关机后要重新启动，见第 6 节。
- 后端 pytest 32 项、网站 5 个测试脚本都通过。
- AI 普通问问、阿烬、流式回答和每日文章生成均已有实现。
- 真实 AI、数据库和阿里云配置在 `backend/.env`，不要复制到 Claude 对话。
- 用户自己建了一个测试账号，不要改、不要删。需要登录测试时另建 `1990000000x` 临时账号，用完连同数据一起删掉。

## 10. 推荐阅读顺序

`CLAUDE_HANDOFF.md` -> `markdown/00-项目地图.md` -> `markdown/AI系统总览.md` -> `backend/README.md` -> `backend/config.py` -> `backend/services/ai.py` -> `backend/services/prompts.py` -> `backend/app/main.py` -> `backend/app/api/v1/content.py` -> `frontend/utils/api.js` -> `webpage/js/api-browser.js` -> `webpage/UPGRADE-20260919.md`。

## 11. 工作日志

### 2026-10-11

按时间顺序，后面的条目以最新状态为准。

1. **启动和推送**：用 `.venv314` 启动后端，`/health` 正常。推送了 3 个积压提交到 GitHub。启动了 `8765` 网站和 `5173` H5（第一次在 `frontend` 跑了 `npm ci`）。
2. **排查 bug，提交 `ccda61a`**：
   - H5 五个非 tabBar 页面调用 `setTabBarStyle` 报错，在 `frontend/utils/theme.js` 加了 `fail` 回调。
   - 首页分区导航在手机上横向溢出 2px，改了 `webpage/index.html`。
   - 阅读器 `bookId` 为空时把书单当成一本书渲染，在 `frontend/utils/api.js` 拦截。
3. **宣传片**：一共做了 4 版，最终用 v4（30 秒竖版）。
   - 配乐是用户原创的《雨》，从 128.06 秒切入，117.5 BPM。
   - 旁白用 CosyVoice3 在本地合成，音效是 Kenney 和 OpenGameArt 的 CC0 素材，图标是 Lucide（ISC 授权）。
   - 修了一个 zsh bug：滤镜标签 `[$i:a]` 被当成路径修饰符，导致每句旁白都是第一句。已全部改为 `[${i}:a]`。
   - 原曲母带真峰值本身就超过 0 dBTP（《雨》0.0、《岚》+0.6、《憩》+0.7）。混音时先降 4 dB，成片是 -14 LUFS、真峰值 -2 dBTP。
4. **网站更新日志页，提交 `4db67e7`**：
   - 新增 `webpage/changelog.html`，按网站 / App / 后端与 AI 筛选（`?type=`），按月份跳转。
   - 首页 `#video` 区块和更新日志页顶部各放一处宣传片，点播，带旁白。
   - 全站版本号改为 `20261011-1`，页面检查数改为 11，`UPGRADE-20260919.md` 补了一节。
5. **整理，提交 `1f30229`**：
   - 制作脚本 `promo/` 进 Git；App 用的宣传片和封面放进 `frontend/static/promo/`。
   - 删除 `output/promo-video/`（约 14GB 过程文件）和根目录 `music/`（8 首和 `~/Music/已完成文件/` 里的逐字节一致）。

### 宣传片文件在哪里

| 文件 | 位置 | 是否在 Git |
| --- | --- | --- |
| 网站用 720p 版 + 海报 | `webpage/assets/promo/`（README 里有再生成命令） | 是 |
| App 用 720p 版 + 海报 + 9:16 / 3:4 封面 | `frontend/static/promo/` | 是 |
| 1080p 原片 | `output/jianwen-promo-v4-30s.mp4` | 否 |
| 制作脚本 | `promo/v4/`（`build.sh` 一键出片，`compose.py` 画面，`audio.sh` 音轨，`cover.py` 封面，`lines.txt` 旁白文案和时间点） | 是 |

注意：录屏、Blender 渲染帧、字体（思源黑体 SIL OFL）、音效、CosyVoice 模型都已经删了。要重做视频，必须先补回这些素材，`promo/v4/build.sh` 不能直接重跑。

### 没做完 / 待确认

- **App 还没接入宣传片**：`frontend/static/promo/` 里的视频还没放到任何 App 页面上。
- **"电脑和手机同一份进度"这句宣传先别用**：测下来，电脑网页显示"阅读位置已同步至账号"，手机浏览器打开网页版显示的却是"已在此设备保存阅读位置"。v4 已经改成只说"电脑看网页，位置存账号"。要恢复这句宣传，得先查清手机网页版为什么没走账号同步。
- **H5 阅读器的进度只存在本机**，不像网页版那样同步到账号。这是功能差异，不是故障。
- **pytest 没写进依赖**：如果要保留，加到开发依赖里。
- **后端热重载会监视虚拟环境目录**：后端是带 `--reload` 启动的，往 `.venv314` 装包也会触发重启。可以加 `--reload-dir app --reload-dir services`，只监视代码。
- **宣传片的观感用户还没最终确认**，这些都是之前反馈过的点：配音自然度、大字是否居中、版式有没有空洞。

### 下次开工先做

1. `git status --short --branch`，确认和 `origin/main` 一致。
2. 用 `lsof -nP -iTCP:8000,8765,5173 -sTCP:LISTEN` 查服务。没在跑就按第 6 节启动，再访问 `/health`。
3. 跑测试：`backend` 下 `.venv314/bin/python -m pytest -q`；项目根目录下 `node webpage/tests/site-pages.mjs` 等 5 个脚本。
4. 从上面"没做完 / 待确认"里接着做。
