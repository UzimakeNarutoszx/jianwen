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

### 议题追踪与审核发布

- `GET /api/v1/content/issues?limit=20`：已发布可见议题数组，limit 1–50。
- `GET /api/v1/content/issues/{issue_key}`：按事件日期排序的时间线；携带登录 token 时包含关注与已读发布版本。
- `GET /api/v1/profile/issues`：已关注的可见议题数组。
- `GET /api/v1/profile/issues/updates`：未读更新数组，每项为 `{issue, new_events, events}`；`new_events` 统计新增或修订事件。
- `POST/DELETE /api/v1/profile/issues/{issue_key}/follow`：关注/取消关注；重复调用幂等。
- `POST /api/v1/profile/issues/{issue_key}/seen`：请求 `{published_version}`，只能标记实际加载的版本，服务端原子取最大值，不吞掉并发新发布。

文章详情新增可空 `issue` 和默认空数组 `policy_checks`。问问普通与流式请求均支持可选 `article_id`、`issue_key`、`policy_key`；指定不存在或未发布的上下文返回 404。议题上下文只含已发布节点。周报新增 `issues` 数组，按北京时间的**发布周**统计，并附当周发布事件快照；历史事件回填也会计入实际发布周。

每日文章提交后只写持久候选任务，单独后台线程每 30 秒领取任务并调用 AI，失败延迟 5 分钟重试，最多 3 次；15 分钟租约允许进程重启恢复。AI 只能产生待审候选，不会公开议题。种子兜底文章不排入任务。启动会运行候选 worker；不要为无副作用验证启动真实服务。

在 `backend/` 目录使用下列 CLI；所有写入生产数据库的命令应由操作者明确执行。`backfill --dry-run` 仅读取，不调用 AI、不写数据库。

```bash
.venv314/bin/python scripts/issue_threads.py backfill --since 2026-10-01 --dry-run
.venv314/bin/python scripts/issue_threads.py backfill --since 2026-10-01
.venv314/bin/python scripts/issue_threads.py work-once
.venv314/bin/python scripts/issue_threads.py export --output /tmp/issue-review.json
.venv314/bin/python scripts/issue_threads.py validate --file /tmp/issue-review.json
.venv314/bin/python scripts/issue_threads.py publish --file /tmp/issue-review.json --reviewer 人工审核人
.venv314/bin/python scripts/issue_threads.py reject 123 --reviewer 人工审核人
.venv314/bin/python scripts/issue_threads.py hide ISSUE_KEY --reviewer 人工审核人
.venv314/bin/python scripts/issue_threads.py merge FROM_KEY INTO_KEY --reviewer 人工审核人
.venv314/bin/python scripts/issue_threads.py detach ISSUE_KEY ARTICLE_ID --reviewer 人工审核人
.venv314/bin/python scripts/issue_threads.py revise ISSUE_KEY --file /tmp/issue-correction.json --reviewer 人工审核人
```

导出的资料是 `{candidate_id, base_version, payload}` 数组。人工核对原文与官方来源后，编辑标题、现状、阶段和摘要；不得替换来源文章或归并目标，低置信度候选需补证后才能通过校验。导出不覆盖已有文件。发布整份文件为一个事务，任何过期基线或无效候选均回滚；同一文件内多个节点加入同一议题受统一基线校验。修订资料格式为 `{published_version, title?, status_line?, stage?, events?: [{article_id, delta_summary}]}`；只允许修订现有事件。发布、修订、隐藏、归并、脱离均记录发布版本、审核人和快照；单篇文章只能有一个主议题，归并会迁移关注关系。归并旧键会解析到当前目标议题；隐藏旧键及不存在的键返回 404。事件的 `historical` 在写入时按 `event_date` 是否早于北京时间发布日持久判定，归并和修订不会重新推断。

新增表由 `create_all` 首次创建；它不会自动迁移既有表字段。测试使用内存 SQLite 和 mock AI，无需访问真实 AI 或业务数据库。

### 匿名政策自查

- `GET /api/v1/content/policy-checks`：当前已发布或暂停的规则目录，可按 `article_id` / `issue_key` 筛选。
- `GET /api/v1/content/policy-checks/{policy_key}`：公开规则、依据与核验有效期。过期或暂停时保留依据，不返回题目。
- `POST /api/v1/content/policy-checks/{policy_key}/evaluate`：无需登录，请求 `{version, answers: {question_id: option_value}}`。确定性返回“可能符合 / 暂不符合 / 信息不足”；任何明确不满足优先，缺项和“不确定”都视为信息不足。

自查不调用 AI，不保存答案、不关联账号；公开问问上下文只包含规则条款，不包含答案。版本变化返回 409，过期或暂停返回 410，未知问题/选项返回 422。核验有效期和适用日期按北京时间解释，截止日当天有效。目录、详情和评估响应禁用缓存。

新增 `content_policy_checks` 保存不可改写的规则版本；`current_key` 唯一指向当前公开版本。规则必须有政府 HTTPS 原文、逐题依据、审核记录、适用起始日期和有效核验时间才能显式发布。采编资料与 CLI 用法见 [editorial/README.md](editorial/README.md)。当前杭州补贴文件为**未发布草稿**，不能作为现行资格认定依据。

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
