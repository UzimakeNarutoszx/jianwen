# 见闻项目交接文档

更新时间：2026-10-11（Asia/Shanghai）。项目根目录：`/Users/ens/Thomas的文件/编程/见闻`。

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
| `output/` | 截图、快照和测试输出 | PNG 等 |

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

入口为 `webpage/index.html`，见闻阅读页在 `webpage/jianwen/`，阿烬/产品介绍页是 `webpage/avatar*.html`。关键脚本是 `webpage/js/api-browser.js`（API、token、问问、收藏和阅读进度）、`ajin-chat.js`、`article.js`、`reader.js`。从项目根目录运行 `python -m http.server 8765 --bind 127.0.0.1 --directory webpage`，访问 `http://127.0.0.1:8765/index.html`。网站默认请求同一主机的 `8000` 后端。视觉和验收历史见 `webpage/UPGRADE-20260919.md`。

## 5. DeepSeek/AI 调用

AI 使用 OpenAI 兼容的 `/chat/completions`。当前本地配置是 `AI_API_BASE_URL=https://api.aicodewith.com/v1`、`AI_MODEL=deepseek-flash`。后端是 AI 代理层，浏览器不直接携带 AI key；实际供应商由 `AI_API_BASE_URL` 决定，不能仅凭模型名推断供应商。

普通问问从 `POST /api/v1/content/ask` 进入，检查登录和每日额度（默认 20 次），拼接文章/全站上下文与历史，由 `build_ask_messages()` 生成消息，调用 `backend/services/ai.py`，保存 AI 使用记录并返回回答和来源。阿烬从 `POST /api/v1/content/ajin/chat` 进入，使用 `AJIN_SYSTEM_PROMPT` 和 `build_ajin_messages()`；外部模型不可用时，`content.py` 提供本地应急回复。

流式问问从 `POST /api/v1/content/ask/stream` 进入，设置 `stream: true`，解析 SSE `data:` 行并输出文本；前端处理停止、Markdown 安全渲染、复制和重试。

每日文章服务在 Asia/Shanghai 每天 06:00 刷新：从政府公开 JSON 列表抓取素材，要求 AI 生成正好 5 篇文章（标题、说明、三段正文、摘要、来源、引用），再校验长度、数量、引用和风险表达；失败时回退本地种子文章。

AI 配置变量：`AI_API_BASE_URL`、`AI_API_KEY`、`AI_MODEL`、`AI_TIMEOUT_SECONDS`、`AI_USE_ENV_PROXY`、`AI_THINKING_DISABLED`、`AI_TEMPERATURE`、`AI_TOP_P`。真实 `AI_API_KEY` 只放 `backend/.env` 或进程环境。

## 6. 本地运行和测试

后端：进入 `backend`，创建/激活虚拟环境，执行 `pip install -r requirements.txt`，再运行 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`。开发热重载可增加 `--reload`。项目已有 `.venv`、`.venv313`、`.venv314`，不要提交虚拟环境。

后端测试：进入 `backend` 执行 `pytest -q`。网站测试包括 `node webpage/tests/site-pages.mjs`、`node webpage/tests/api-smoke.mjs`、`node webpage/tests/reading-api.mjs`、`node webpage/tests/ask.test.cjs` 和 `node webpage/tests/reader.test.cjs`。依赖服务的测试要先启动 `8000` 和 `8765`。历史验收见 `webpage/UPGRADE-20260919.md`。

## 7. Git 与 GitHub

远程仓库是 `https://github.com/UzimakeNarutoszx/jianwen.git`。本地分支为 `main`，GitHub CLI 已登录 `UzimakeNarutoszx`，协议为 HTTPS。

本次盘点结果：本地 HEAD 是 `9f15b4c beta版`，远程 `origin/main` 是 `94d8d78 Update project backup`，本地 `main` 比远程领先 2 个提交：`0bd8b53 fix discover page responsive layout` 和 `9f15b4c beta版`。

接手时先检查 `git status --short --branch` 和 `git log --oneline origin/main..HEAD`，确认后执行 `git push -u origin main`，再用 `git ls-remote origin refs/heads/main` 验证远程提交号。常规备份流程是 `git add -A`、`git commit -m "Describe the change"`、`git push origin main`。

不要强制推送，也不要把 `backend/.env`、token、数据库、用户上传、虚拟环境、`__pycache__` 或密钥加入 Git。过去 GitHub push protection 曾拦截阿里云密钥；相关密钥应在阿里云控制台轮换。

## 8. 配置与安全

本机需要配置但不能公开的变量：`AI_API_KEY`、`MYSQL_PASSWORD`、`SECRET_KEY`、`ALIYUN_DYPNS_ACCESS_KEY_ID`、`ALIYUN_DYPNS_ACCESS_KEY_SECRET`。`backend/.env` 由 `backend/config.py` 加载，进程环境变量优先。短信使用阿里云 DYPNS；开发时可设置 `SMS_PROVIDER=local` 和 `SMS_DEV_CODE`。生产环境必须设置独立的 `SECRET_KEY`，不能使用开发默认值。

用户用手机号注册/登录。头像限制为图片且最大 2MB。GitHub 只保存源代码，不会自动运行 FastAPI、MySQL 或每日调度器。

## 9. 当前状态和接手建议

- 本地 Git 与 GitHub 已关联，本地比远程多两个提交。
- MySQL 正在监听 `3306`。
- 当前没有检测到 `uvicorn`、`http.server` 或 Uni App 开发服务器进程。
- AI 普通问问、阿烬、流式回答和每日文章生成均已有实现。
- 真实 AI、数据库和阿里云配置在 `backend/.env`，不要复制到 Claude 对话。

Claude 第一轮建议：阅读本文、`markdown/00-项目地图.md`、`markdown/AI系统总览.md` 和 `backend/README.md`；检查并决定是否推送两个 beta 提交；安全配置环境变量；启动后端验证 `/health`、数据库和 AI；启动 `8765` 网站并运行测试；明确主交付是 `webpage` 还是 `frontend`。

## 10. 推荐阅读顺序

`CLAUDE_HANDOFF.md` -> `markdown/00-项目地图.md` -> `markdown/AI系统总览.md` -> `backend/README.md` -> `backend/config.py` -> `backend/services/ai.py` -> `backend/services/prompts.py` -> `backend/app/main.py` -> `backend/app/api/v1/content.py` -> `frontend/utils/api.js` -> `webpage/js/api-browser.js` -> `webpage/UPGRADE-20260919.md`。
