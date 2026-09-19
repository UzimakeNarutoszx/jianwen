# 见闻项目同步 GitHub

目标仓库：https://github.com/UzimakeNarutoszx/jianwen.git

本地已初始化为 `main`，网站统一修改已提交。远程仓库首次检查为空，没有覆盖任何远程历史。

## Git 登录与后续同步

首次使用或凭据失效时，在 PowerShell 运行：

```powershell
git credential-manager github login --username UzimakeNarutoszx --browser
```

在浏览器中确认使用对该仓库有写入权限的账号完成授权。不要把密码或令牌发到聊天中。仅登录 GitHub 网页不等于授权 Git Credential Manager。

## 同步内容

- `webpage` 横屏官网、`backend` 服务、`frontend` 移动端源码、`markdown` 与 `pages_ui` 文档。
- `.gitignore` 已排除 `.env`、依赖、构建产物、日志、用户上传、数据库、验证输出及旧备份。
- 提交前已检查文件列表，未发现本地 `.env` 凭据原值出现在待提交源码中。

后续手动同步可在项目目录运行：

```powershell
git status --short
git add .
git commit -m "Update Jianwen"
git push -u origin main
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

最后两条命令的提交号应一致。已有远程提交时先检查并合并，不使用强制推送。

GitHub 保存源代码不会自动运行 FastAPI 或数据库；运行配置和数据库需要单独维护。

## 后端凭据

数据库密码和阿里云 AccessKey 不再具有源码中的默认值，须通过运行环境提供 `MYSQL_PASSWORD`、`ALIYUN_DYPNS_ACCESS_KEY_ID` 和 `ALIYUN_DYPNS_ACCESS_KEY_SECRET`。本机原有值保留在 Git 忽略的 `backend/.env` 中；配置类不会自动加载该文件，启动环境需显式注入这些变量。生产环境还需设置独立的 `SECRET_KEY`。

首次推送曾被 GitHub 密钥保护拦截，已从未发布的提交中删除硬编码凭据。建议在阿里云控制台轮换曾写入源码的 AccessKey，不要绕过密钥保护。
