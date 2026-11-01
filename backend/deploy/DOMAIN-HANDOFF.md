# jianwen.xin 域名接入记录

检查日期：2026-11-01。此任务仅处理域名，不修改手机端、签名或 APK 构建。

## 当前结果

- 阿里云 Safari 控制台成功新增并启用 `@ A 8.147.110.194` 与 `www A 8.147.110.194`，默认线路，TTL 600 秒。
- 服务器分别查询 dns21.hichina.com、dns22.hichina.com 和 223.5.5.5，返回上述公网 IP。域名当前未配置 AAAA 和 CAA。本机代理 DNS 返回 198.18.*，不能据此判断公网解析。
- 公网真实 Chromium 访问 `http://jianwen.xin/` 返回 403，标题为 `Non-compliance ICP Filing`。截图显示阿里云“当前备案状态不符合访问要求”。未通过工信部验证码查询独立核实备案号；用户提供的状态为尚未备案。不能把解析成功描述为网站已上线。
- 官方说明：https://beian.aliyun.com/ ：域名未在阿里云完成备案而解析到其中国内地服务器，会被监测系统识别并阻断。
- 源站专用域名站点返回 503 文本“ICP备案尚未完成，网站暂未开放”。这是源站行为，不承诺公网能显示该提示，公网仍受阿里云备案拦截。
- 未购买服务、未申请证书、未接受证书服务协议、未提交备案资料、未更改安全组或放宽 SSH 权限。

## 配置与回滚

域名独立配置：`/etc/nginx/sites-available/jianwen-domain`，启用链接：`/etc/nginx/sites-enabled/jianwen-domain`。本地源文件为同目录的 `jianwen-domain.pending.conf`。

操作前读取并备份现有配置，备份目录为 `/var/backups/jianwen/domain-20261101/`，包括 `jianwen.before` 和 `nginx.before.txt`。部署通过 `nginx -t` 后 reload。原 `/etc/nginx/sites-available/jianwen` 未改写，部署后 SHA256 与备份一致；园林 include 保留。独立站点日志为 `/var/log/nginx/jianwen-domain-access.log` 与 `/var/log/nginx/jianwen-domain-error.log`。

如需回退域名站点，可将其启用链接移出 sites-enabled 到备份目录，再 `nginx -t`、reload；不要恢复旧的见闻整文件，以免覆盖原对话后续增加的 downloads 配置。DNS 记录可在控制台暂停，需用户明确要求后执行。

## 只读回归检查

- `/opt/jianwen/backend/.env` 为 `640 root:jianwen`，`SEED_CONTENT_ON_STARTUP=false`，未改动。
- 见闻 `127.0.0.1:8000/health` 与公网 IP `/health` 正常。
- 园林 `127.0.0.1:8011/health` 与公网 IP `/garden/health` 正常。
- 公网 IP 的今日、发现和每周视频页面均返回 200。真实浏览器加载今日页有内容，内容 API 三项返回 200；静态 agents.png 有一项 ERR_ABORTED，未扩大任务修改。没有声称整个网站浏览器验收通过。
- `/downloads/jianwen-1.0.0.apk` 此次只读检查为 404，由原对话继续发布；未修改该路径或 APK。

## HTTPS 准备和后续门槛

目前没有 certbot、没有已部署证书、没有 443 监听；外部 TLS 连接超时，不能据此单独认定是安全组问题。待证书部署时由用户在 ECS 控制台核对 TCP 443 入站规则。

同目录 `jianwen-domain.tls.conf.disabled` 是未启用的 TLS 参数草稿，未被 Nginx include。预定证书路径为 `/etc/nginx/tls/jianwen.xin/fullchain.pem` 和 `privkey.pem`。证书应覆盖根域名和 www；私钥仅保存服务器，目录 700、私钥 600 root:root。需要用户选择证书服务并自行确认相关协议，不自动购买或同意条款。DNS 验证可用于合法证明域名控制权，但证书不能替代备案，备案未通过前不启用正式域名服务。

上线顺序：

1. 用户在阿里云 ICP 备案入口办理，完成实名认证、主体/网站资料、短信或人脸验证、必要的前置审批核查。见闻包含新闻和 AI 内容，应如实向备案客服说明业务，确认个人/企业主体及许可要求。核对 ECS 是否满足备案资源资格；若不满足，先反馈，不自动购买。
2. 备案通过并确认阿里云接入正常后，用户提供备案号，在网页显示合规备案信息；公开状态与后台状态均需核验。
3. 每次部署先读取最新见闻配置及 garden/downloads include，备份后再做增量。将域名待备案站点替换为正式站点，复用最新应用 locations；不能直接复制本次早期配置覆盖后续改动。
4. 核验可信证书 SAN、完整链、有效期、私钥匹配及续期方案，再启用 443；`nginx -t` 后 reload。先验收 HTTPS，再启用 HTTP 跳转；暂不设置 HSTS，避免未完成部署时锁死访问。
5. 浏览器实测今日、发现、每周视频播放/Range、API、图片、园林及届时发布的 downloads，记录失败请求、控制台和混合内容。不能只以 HTTP 200 作为验收。

## API、媒体、CORS 核查

线上 `webpage/js/api-browser.js` 在 HTTPS 或默认 HTTP 端口下默认取 `window.location.origin`，无需把 API 固定改成域名或 HTTP IP。`jianwen_api_base_url` 本地存储覆盖值可能造成混合内容；新域名的存储与旧 IP 分离，旧覆盖值不会自然迁移。正式验收需检查实际存储和网络请求。

线上 `major-event.js`、`weekly-video.mjs` 与 `data/weekly-videos.json` 未发现固定 `http://` URL；视频清单使用相对路径。本次未全量审计数据库媒体 URL，也未完成 HTTPS 下浏览器验收，不能宣称已消除所有混合内容。

当前后端 `CORS_ORIGINS=http://8.147.110.194`。正常同源域名网页无需依赖跨域授权；若实际有跨域客户端，再按业务最小范围追加真实 HTTPS origins，不改为通配符。uvicorn 已启用 proxy headers 且只信任 127.0.0.1，正式 TLS 反代应保留 `X-Forwarded-Proto $scheme`。

## 证据

- `output/domain/icp-block.png`：真实浏览器截图。
- `output/domain/domain-public-headers.txt`、`domain-public-body.html`：公网请求的备案拦截响应。
