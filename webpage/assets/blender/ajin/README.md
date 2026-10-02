# 阿烬 Blender 资产工作流

这里保存阿烬硬件视觉资产的源文件、导出设置与脚本。当前环境未检测到 Blender CLI，因此本轮只建立规范，不伪造 `.blend` 或渲染文件。

## 目标

- 低面数、硬件感明确的阿烬主体模型。
- 固定三点灯光与 3/4 正面镜头。
- 透明 PNG/WebP：网页默认静态资产。
- 3–5 秒无缝 MP4：支持动效时的可选素材。

## 导出约定

- 静态图：1600×1200，RGBA，主体留 8% 安全边距。
- 移动端图：900×1200，RGBA，主体居中。
- 视频：1920×1080、24fps、H.264，默认静音，首尾姿态一致。
- 文件名：`ajin-hero.webp`、`ajin-hero-mobile.webp`、`ajin-hero-loop.mp4`。

导出后把文件放到 `webpage/assets/blender/ajin/`，页面会优先使用它们，缺失时回退到 `webpage/assets/阿烬.png`。
