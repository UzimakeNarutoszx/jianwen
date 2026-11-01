# 公开展示素材

- README 主展示使用 `media/cloud-today.png`、`media/cloud-article.png`、`media/cloud-login.png`：来自[云端实际网页](http://8.147.110.194/jianwen/index.html?v=20261031-1)的今日、文章、登录页面截图，显示拍摄时的真实界面与内容状态。登录页面未填写账号信息；展示图未见真人照片。不应把截图中的文章内容视为已核实新闻。
- `media/jianwen-poster-public.jpg`：真实 v4 宣传片公开处理版的展示海报。
- [v4 宣传视频公开处理版](https://github.com/UzimakeNarutoszx/personal-website-oss/releases/download/public-editions-2026-11-01/jianwen-promo-v4-public.mp4)：真实成片，30 秒、1080 × 1920，包含音频；真人照片所在局部区域已遮挡。视频存放于 Release，不是截图合成的无声导览。这里不声称执行过音量归一化。
- 去敏范围仅为新闻轮播中的工厂人物照片卡片；该区域改为产品深蓝底，按原有标题、摘要和控件文字重绘，局部字体与原片略有差别。其他画面和时序保留，AAC 原音轨直接复制，原文件未修改。
- 上述云端截图、海报与宣传视频属于展示素材，不纳入源码 MIT 许可；其内容、图像、声音及第三方权利须另行确认，不因仓库开源而获得再分发授权。
- 源码中的编辑配图仍为中性几何图形；保留的品牌和功能图标经过接触表检查。此展示更新没有改变源码资源或 APK。

## 保留的本地合成演示

`media/today.png`、`media/login.png`、`media/home.png` 是早期本地合成数据截图；`media/interface-tour.mp4` 是这些截图组成的约 13 秒无声导览。它们不再作为 README 主展示，仍为 Android 公开预览包处理记录及本地复现保留。APK 内仍使用这一无声导览，并未因 README 更换展示视频而更新。

## 复现本地合成截图

安装 `playwright` Python 包，准备 Chromium（脚本默认使用 macOS Chrome，可按本机路径调整），在独立终端运行：

```bash
python3 -m http.server 18765 --bind 127.0.0.1 --directory webpage
python3 docs/capture-preview.py
```

`capture-preview.py` 中的数据明确标注为合成示例，不模拟用户登录，也不联系生产 API。该脚本不会复现 README 当前使用的云端截图，也不会生成 v4 宣传片。
