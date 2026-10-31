# 见闻后端

FastAPI + SQLAlchemy + PyMySQL 同步后端。启动时会自动创建 MySQL 数据库 `ENS_Project`，并用 SQLAlchemy 创建/更新当前模型对应的数据表；内容种子数据会按主键更新。

## 启动

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端默认请求 `http://127.0.0.1:8000`。真机调试时需要把 `frontend/utils/api.js` 中的默认地址，或本地缓存 `jianwen_api_base_url`，改成电脑局域网 IP。

## API 清单

### 认证

- `POST /api/v1/auth/send-sms`：发送注册/忘记密码验证码。
- `POST /api/v1/auth/register`：手机号、昵称、密码、验证码注册，不需要邮箱。
- `POST /api/v1/auth/login`：手机号和密码登录。
- `POST /api/v1/auth/forgot-password`：手机号、验证码、新密码重置密码。

### 内容

- `GET /api/v1/content/today`：今日页 5 条文章卡片。
- `GET /api/v1/content/articles/{article_id}`：文章详情页。
- `GET /api/v1/content/articles/{article_id}/related?limit=4`：相关阅读，优先同主题、其次同分类，排除当前文章；limit 范围为 1–12。
- `GET /api/v1/content/discover`：发现页主题、专题、最近更新。
- `GET /api/v1/content/categories`：主题频道列表。
- `GET /api/v1/content/articles?category=&q=`：分类页和搜索页文章列表。
- `GET /api/v1/content/pages/{page_key}`：设置页静态内容，如用户协议、来源说明。
- `GET /api/v1/content/ask/bootstrap`：问问页欢迎语、推荐问题、追问按钮。
- `POST /api/v1/content/ask`：问问回答，需要登录，默认每日最多 20 个问题，可用 `AI_DAILY_QUESTION_LIMIT` 调整。

兼容旧路径：

- `GET /api/v1/content/ask/prompts`
- `POST /api/v1/content/ask/answer`
- `POST /api/v1/content/ask/stream`：流式问问回答，需要登录并占用每日问题额度。

### 用户资料与行为

- `GET /api/v1/profile/me`：当前登录用户资料和统计。
- `PATCH /api/v1/profile/me`：更新昵称、简介。
- `POST /api/v1/profile/me/avatar`：上传头像。
- `GET/PUT /api/v1/profile/topics`：读取/保存关注主题。
- `GET/POST/DELETE /api/v1/profile/favorites`：收藏列表、保存收藏、取消收藏。
- `GET/POST/DELETE /api/v1/profile/history`：浏览历史列表、写入历史、清空历史。
- `GET/POST/DELETE /api/v1/profile/ai-records`：问问记录列表、保存记录、清空记录。
- `GET/PUT /api/v1/profile/reading-positions/{book_id}`：登录后按书同步阅读位置；请求为 `chapter_id` 和 0–100 的整数 `scroll_progress`。无历史位置时返回 `null`。

## 数据库表

- `users`：用户手机号、昵称、密码哈希、头像、简介。
- `user_favorite_articles`：用户收藏文章。
- `user_browsing_history`：用户浏览历史。
- `user_ai_usage_records`：用户问问记录。
- `user_follow_topics`：用户关注主题。
- `user_reading_positions`：按用户、书籍保存章节和章内阅读百分比。
- `content_categories`：内容主题频道。
- `content_articles`：文章卡片和详情内容，正文结构使用 JSON 字段。
- `content_features`：发现页专题。
- `content_pages`：协议、来源说明等静态页面内容。
- `ai_prompts`：问问页欢迎语、推荐问题、追问按钮。
- `ai_answer_rules`：问问回答规则，按关键词命中，空关键词为兜底回答。

### Today checklist

- `GET /api/v1/profile/today-checklist`：当前登录用户的今日理解清单，返回今日文章列表、每篇是否已读、已读数量和是否完成。

## 个人周报

网站入口：`/jianwen/weekly.html`，导航栏与“我的”页均可进入。每周视频为独立功能。

- `POST /api/v1/profile/reading-activity`：登录后上报阅读片段，字段为 `batch_id`、`kind`（`article` / `classic`）、`content_id`、带时区的 `started_at` / `ended_at`，名著另带 `book_id` 与 0–100 的 `scroll_progress`。单批最多 16 秒，接受最近七天的离线重试；不允许指定用户 ID。
- `GET /api/v1/profile/weekly-report?week_start=YYYY-MM-DD`：只返回登录用户自己的自然周统计、每日序列、主题分布、完整阅读与问题明细；日期必须是周一，省略时为北京时间本周，响应为 `private, no-store`。
- 新增 `user_reading_batches`、`user_reading_intervals`、`user_article_reading_days`，正常启动后自动创建，无需修改现有表。片段使用 UTC 微秒时间存储，按北京时间午夜拆分；按用户锁串行写入并扣除已记录重叠时间，批次重试不重复计算。
- 文章按已有浏览／已读记录计数，并与实际停留片段合并去重；同一天同一篇只计一次，周汇总按文章去重。名著章节在所选周累计前台有效停留满 30 秒才计入周阅读明细；章节日计数单独按当天 30 秒判定。计时在页面隐藏、失焦或 60 秒无操作时暂停。图表时长包含不足 30 秒的有效停留片段。
- 旧表的无时区日期沿用现有后端／数据库本地时间约定，再转换到北京时间。部署时应保持应用和数据库时区一致；旧文章浏览历史合并到普通文章阅读计数，但不倒推有效时长；名著历史位置仍只作参考。新文章阅读另按北京时间日期持久保存，重读不会覆盖历史周。停留时间采集从新功能启用后开始。
- 清空文章浏览历史会同时删除该用户的文章阅读片段和按日阅读记录；清空问答记录后周报同步更新。未保存周报快照。名著仍沿用原有位置同步接口。
- 图表与导出依赖本地固定版本 ECharts 5.6.0、html-to-image 1.11.13，许可证随 `webpage/js/vendor/` 分发；导出不上传个人记录。

验证命令：安装 `requirements-dev.txt` 后，在 `backend` 运行 `python -m unittest tests.test_weekly_report tests.test_reading_positions tests.test_profile_routes`；项目根目录运行 `node webpage/tests/reading-activity.test.cjs`、`node webpage/tests/site-pages.mjs`。浏览器回归脚本为 `webpage/tests/weekly-browser.js`，使用合成数据验证桌面／手机、106 条问题的 PNG 导出，以及账号切换和退出后的清理。
