# 见闻手机端

Vue 3 / uni-app，H5 与 App 共用页面。运行 `npm run dev:h5`，构建 `npm run build:h5`；App 沿用 HBuilderX 打包。

## 每周中心

底部导航为今日、发现、每周、问问、我的。每周默认显示公开节目，个人周报需要登录。更新日志入口位于我的 → 关于见闻。

启动项目现有后端即可访问：

- `/public/data/weekly-videos.json`：与网站共用的节目目录。
- `/public/assets/weekly-video/`：节目视频、封面和字幕，支持视频 Range 请求。
- `/public/data/changelog.json`：与网站共用的更新日志。
- `/api/v1/profile/weekly-report`、`/api/v1/profile/reading-activity`：已有账号周报与阅读活动接口。

部署后端时需要同时部署 `webpage/data/` 和 `webpage/assets/weekly-video/`。节目目录里的相对资源地址以 `/public/` 为根；无需将视频复制到 App 安装包。日志更新只修改 `webpage/data/changelog.json`。

真机打包前从 `.env.example` 创建 `.env.local`，设置 `VITE_API_BASE_URL` 为手机可访问的后端地址，正式环境使用 HTTPS。也可通过现有 `jianwen_api_base_url` 本机缓存覆盖。`127.0.0.1` 在手机上指向手机自身。

阅读统计只采集成功加载的文章和经典正文。前台停留按不超过 15 秒的片段上报，60 秒无交互、离开页面或进入后台暂停；失败记录按账号在本机保留最多 7 天，重试使用原批次 ID。旧文章浏览记录可计入篇数，但不补算历史时长。

周报图表与长图共用绘图数据，完整包含明细。H5 可下载或预览，App 可预览后保存相册。设备容量不足时明确失败，不截断长图。

## 检查

从项目根目录运行 `node --test frontend/tests/*.test.mjs`。后端目录运行 `.venv/bin/python -m unittest tests.test_public_resources tests.test_weekly_report`。App 视频播放、后台生命周期和相册授权需在 HBuilderX 真机环境验证。

浏览器验收脚本为 `frontend/tests/weekly-browser.js`，通过 Playwright CLI 的 `run-code --filename` 执行；需要先将 H5 构建目录提供在 `http://127.0.0.1:4174`，并启动 8000 端口的后端。它使用真实节目与日志资源，对个人周报接口注入测试数据，不向数据库写入测试账号。截图和长图保存在忽略提交的 `output/`。
