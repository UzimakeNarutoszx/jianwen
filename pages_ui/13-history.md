# pages/profile/history UI 方案

## 页面定位

历史页是阅读轨迹，应突出时间顺序和继续阅读。

## 设计方案

- 顶部做成“阅读轨迹”hero，显示最近看过数量。
- 列表改为时间轴卡片：时间、主题、标题、摘要、来源。
- 当天/昨天/更早可分组，增强可回溯感。
- 空状态使用历史/时钟图标，主按钮跳今日页。
- 与收藏页共享卡片视觉，但用时间轴作为差异点。

## iconfont 建议

- 搜索词：`history`、`clock`、`timeline`、`article`、`empty`。
- 推荐新增：`ui-history.png`、`ui-clock.png`、`ui-timeline-small.png`。

## 验收点

- 时间信息比来源更突出。
- 长标题不挤压时间。
- 空状态和未登录状态清晰。
