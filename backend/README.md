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
