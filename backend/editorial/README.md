# 议题与政策采编

本目录不对外提供静态访问，保存来源核验、规则草稿和人工审核资料。公开接口只读取已发布数据库快照。

## 政策自查

`policies/hangzhou-graduate-first.json` 为杭州应届毕业生生活补贴首笔申领规则草稿。依据为政府域名公开的 2024-05-13 申请指南；已核对 PDF 表格的国籍、毕业学校、参保期限和申请材料。官方亲清在线仍列出此项政策为长期项目，但这并不足以证明每项细则在 2026 年均未调整，因此草稿未填写核验有效期和审核人，不能直接发布。

编辑需对照现行办事系统完成复核，在新版本中填写 `verified_at`、`review_expires_at`、`effective_from`、`reviewer`、`review_note`，再明确发布。仅将时间改成今天不构成核验。日期按北京时间解释，复核期限当天仍可自查，次日暂停。

在 backend 目录执行：

```sh
.venv314/bin/python scripts/policy_checks.py validate editorial/policies/hangzhou-graduate-first.json
.venv314/bin/python scripts/policy_checks.py import editorial/policies/hangzhou-graduate-first.json --dry-run
```

正常 `import` 只保存草稿；`--publish` 才发布。已有版本不允许原地改写，规则或核验日期变化须增加版本。`pause <policy_key>` 暂停公开评估，仍保留依据页。导入工具不创建数据库、不启动每日生成、不调用 AI。

## 议题追踪

每日自动归并仅创建候选。使用 `scripts/issue_threads.py` 的 export、validate、publish 流程审核；回填先执行 `backfill --since YYYY-MM-DD --dry-run`。真实回填只入队，不发布。审核时必须核对关联文章的官方原文，不能将模型置信度当作事实证据。

公开变更使用发布版本计数；新闻发生日期与发布到见闻的日期分别保留。修订、历史补录和归并须明确说明原因。用户答案、账号资料和密钥不得写入本目录。
