# pages/profile/ask-records UI 方案

## 页面定位

问问记录页是 AI 对话档案，应突出问题、答案摘要和来源。

## 设计方案

- 顶部改为“AI 档案库”hero，显示记录数量。
- 记录卡分三层：时间、问题、回答摘要、来源入口。
- 问题使用深色强调，回答使用浅色正文区。
- 可加入“继续问”按钮，跳转问问页并带入上下文。
- 空状态使用 AI chat 图标，主按钮“去问问”。

## iconfont 建议

- 搜索词：`chat history`、`AI`、`question`、`source`、`continue`。
- 推荐新增：`ui-ai-record.png`、`ui-question.png`、`ui-continue-chat.png`。

## 验收点

- 问题和回答层级明确。
- 长回答自动截断或卡片高度可控。
- 来源入口不抢主信息。
