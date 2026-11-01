# 公开展示素材

- `media/today.png`、`media/login.png`、`media/home.png`：本仓库独立网页真实渲染；全新临时浏览器上下文、合成数据、拦截外部请求，没有读取真实账号或生产服务。
- `media/interface-tour.mp4`：上述三张截图按首页、今日、登录顺序合成的 13 秒无声导览，不是操作录像，不包含音频流。没有执行音量归一化。
- 所有编辑配图均替换为新生成的中性几何图形；保留的品牌和功能图标经过接触表检查，无真人照片。未复制原项目任何宣传片、每周节目、私人介绍截图或演示文稿。

## 复现截图

安装 `playwright` Python 包，准备 Chromium（脚本默认使用 macOS Chrome，可按本机路径调整），在独立终端运行：

```bash
python3 -m http.server 18765 --bind 127.0.0.1 --directory webpage
python3 docs/capture-preview.py
```

`capture-preview.py` 中的数据明确标注为合成示例，不模拟用户登录，也不联系生产 API。
