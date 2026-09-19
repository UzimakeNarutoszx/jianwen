# pages/article/detail UI 方案

## 页面定位

文章详情是核心阅读和理解页面，应做成“深度解读报告页”。

## 设计方案

- 顶部导航改为透明 glass nav，返回和收藏都使用 iconfont。
- 文章标题区加入大图或主题渐变底，突出主题、标题、来源和阅读时间。
- “先看这三点”从 data SVG 升级为原生卡片结构，便于统一样式和暗色适配。
- 影响范围和时间线做成左右/上下组合的信息仪表盘。
- 正文卡减少装饰，提升阅读舒适度，段落间距更稳定。
- 继续问问卡固定为“文章内 AI 助手”，按钮图标化。
- 来源与依据使用等级徽章、机构、日期、可信说明。

## iconfont 建议

- 搜索词：`back`、`star`、`timeline`、`impact`、`ask ai`、`source`、`official`。
- 推荐新增：`ui-back.png`、`ui-star.png`、`ui-timeline.png`、`ui-impact.png`、`ui-official.png`。

## 验收点

- 收藏状态清晰。
- 正文大字号阅读不拥挤。
- 来源和 AI 追问入口不会抢正文主次。
