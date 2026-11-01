# 见闻云服务器部署

2026-11-01 部署到阿里云北京 Ubuntu 22.04，公网 IP：8.147.110.194。

- 网页验收：http://8.147.110.194/jianwen/
- 健康检查：http://8.147.110.194/health
- 项目目录：`/opt/jianwen`
- 后端：`jianwen.service`，专用 `jianwen` 用户、单 worker，监听 `127.0.0.1:8000`。
- MySQL：仅本机访问，数据库 `ENS_Project`，应用账号 `jianwen`。
- Nginx：`/etc/nginx/sites-available/jianwen`，代理 API、静态图片及公开视频；网页与 API 同源。
- 密钥：服务器 `/opt/jianwen/backend/.env`，权限 `640 root:jianwen`，不在代码包内。
- `SEED_CONTENT_ON_STARTUP=false`：保留迁移内容，跳过种子数据重写。
- 应用时区：`Asia/Shanghai`，与原数据库历史时间约定一致。

## 检查和维护

```bash
systemctl status jianwen --no-pager
journalctl -u jianwen -n 100 --no-pager
systemctl restart jianwen
nginx -t
curl -fsS http://127.0.0.1:8000/health
```

Nginx 日志：`/var/log/nginx/jianwen-access.log`、`/var/log/nginx/jianwen-error.log`。

## 数据与备份

已导入 31 张表，验收时账号 2、文章 63、收藏 1、浏览历史 13、问问记录 44。正常后台任务可能继续更新文章等内容。

每日北京时间 03:30 由 `jianwen-backup.timer` 执行数据库备份，保存到 `/var/backups/jianwen`。备份仅在同一台服务器上，没有自动删除策略；需要定期检查磁盘、下载备份，后续增加异地备份。原始上传文件在 `/root`。用户上传目录为 `/opt/jianwen/backend/uploads`，数据库定时备份不包含上传文件。

```bash
systemctl list-timers jianwen-backup.timer
systemctl start jianwen-backup.service
ls -lh /var/backups/jianwen
```

## 验收边界

公网 TCP 80 已由用户放行。3306、8000 不应对公网开放。

当前仅 HTTP 验收，尚未配置域名、备案和 HTTPS；账号登录等敏感操作应在 HTTPS 配好后验证。

短信配置已从本机迁移，未实际发送测试短信。AI 已切换到 DeepSeek 官方 `https://api.deepseek.com/v1`，模型 `deepseek-chat`，模型列表及最小聊天请求均返回 HTTP 200；聊天回复为“连接正常”。密钥仅存于服务器配置，不写入源码。每次使用 dotenv 更新配置后，需重新确认文件属组为 `root:jianwen`、权限为 `640`，防止临时文件替换导致属组改变。

节目目录登记了 3 期周视频，另有 1 个宣传视频，均已上传。周视频 Range 请求、封面和字幕检查通过，宣传视频公网 Range 检查通过。

图片改为使用后端 `/static/images/*.jpg` 的压缩封面（约 100–210KB），不再请求网页目录 5–7MB 的原始 PNG。Nginx 为 `.mjs` 显式配置 `application/javascript`，确保周视频列表模块正常执行；浏览器已验证列表、元数据及实际播放。

回滚前备份包括 `/var/backups/jianwen/source-before-service.tar.gz`、`env-before-service` 和启动前 SQL 压缩备份。还原数据库会覆盖运行后的新数据，必须先另行备份和确认。
