# pages/today/today UI 方案

## 当前状态

今日页已经完成第一版“高级资讯仪表盘”改造：强视觉 hero、重点简报 swiper、金句卡、进度卡、briefing 文章流。后续主要是 iconfont 精修和一致性收口。

## 设计方案

- 保留现有 hero、统计胶囊、金句卡、进度圆环、文章编号结构。
- 把当前复用的 tab/功能图标替换为更贴合语义的 iconfont 图标。
- 顶部品牌 mark 可使用“见闻 AI/书本/今日简报”风格图标。
- 进度卡使用 `checklist` 或 `radar` 图标。
- 文章卡进入箭头统一用 iconfont 细箭头。

## iconfont 建议

- 必要程度：中等。现有本地图标可用，但语义不够精准。
- 搜索词：`今日`、`日历`、`简报`、`清单`、`进度`、`文章`、`箭头右`、`金句`。
- 推荐新增：
  - `ui-today-brief.png`
  - `ui-calendar.png`
  - `ui-checklist.png`
  - `ui-quote.png`
  - `ui-arrow-right.png`

## 验收点

- 不改变当前接口和数据结构。
- 替换图标后视觉更统一，但不增加页面拥挤度。
- 今日页继续作为全站视觉基准。
