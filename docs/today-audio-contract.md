# 今日朗读 共享约定（只读，各分片不得修改）

## 存储
- 服务器根：`/opt/jianwen/backend/uploads/tts/`（= 后端 `settings.UPLOAD_DIR/tts`，已由 `/uploads` StaticFiles 暴露，nginx 已代理 `/uploads/`）。
- 布局：`tts/<YYYY-MM-DD>/manifest.json`，`tts/<YYYY-MM-DD>/<article_id>/<voice>.mp3`
- 音频：MP3，单声道，24 kHz，64 kbps。
- 保留最近 7 个日期目录，更早的由上传脚本删除。
- 文件属主 `jianwen:jianwen`，目录 755，文件 644。

## 声音 id（顺序即前端显示顺序，第一个为默认；vivian / uncle_fu 已于 2026-11-08 停用）
| id | label | 生成方式 |
|---|---|---|
| `jianwen` | 见闻（默认） | edge-tts `zh-CN-XiaoxiaoNeural`（语速 +6%），服务器端生成 |
| `dylan` | 男声 | edge-tts `zh-CN-YunxiNeural`（语速 +6%），服务器端生成 |

## manifest.json
```json
{
  "date": "2026-11-08",
  "generated_at": "2026-11-08T06:31:02+08:00",
  "voices": [{"id": "jianwen", "label": "见闻"}, {"id": "dylan", "label": "男声·京味"}],
  "articles": [
    {
      "article_id": "xxx",
      "title": "标题",
      "position": 0,
      "audio": {
        "jianwen": {"url": "/uploads/tts/2026-11-08/xxx/jianwen.mp3", "duration": 182.4}
      }
    }
  ]
}
```
- `url` 是站内相对路径。客户端用各自的 `buildFileUrl` 或 API base 拼接成绝对地址。
- `duration` 单位为秒，保留 1 位小数。
- 某个声音生成失败时，可以在 `audio` 里缺失该声音。前端遇到缺失要禁用该选项，或回退到默认声音。

## 后端接口
`GET /api/v1/content/today/audio`，无需登录。
- 用 `get_content_date()` 读取 `UPLOAD_DIR/tts/<date>/manifest.json`。
- 文件存在且合法时，返回 manifest 全部字段，并附加 `"ready": true`。`articles` 只保留 `article_id` 属于当日 `_today_articles(db)` 的条目，按当日顺序排列。
- 文件不存在或解析失败时返回 `{"date": "<date>", "ready": false, "voices": [...上表 4 个...], "articles": []}`，状态码 200。
- 不允许路径穿越：date 只取自服务端。

## 朗读文本
数据取自 `GET /api/v1/content/today`（列表字段 `article_id`）和 `GET /api/v1/content/articles/{article_id}`（`title`, `summary: list[str]`, `sections: [{heading, body}]`）。
文本拼接顺序是：`title`，再接 `summary` 各条，再对每个 section 依次接 `heading` 和 `body`。去掉 markdown 符号和 URL。

## 前端交互
- 只在「今日」页。只能切换当日的文章（manifest.articles，最多 5 篇），到头禁用对应方向。
- 用户选择的声音保存在本地（key：`jianwen_tts_voice`）。
- `ready:false` 时显示「今日朗读生成中」，播放器禁用，不报错。
- 听完即读完：同一篇真实播放（不含拖动跳过）累计 ≥ 90% 时，按已读处理（本地已读 + 登录用户写阅读历史），与打开文章详情等价。
