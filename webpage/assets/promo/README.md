# 宣传片网页版

- `jianwen-promo-v4-720.mp4`：v4 宣传片（30 秒竖版，有旁白）的网页版，720×1280，H.264 Main + AAC 96k，faststart。
- `jianwen-promo-poster.webp`：海报，来自 v4 的 9:16 封面。

成片源文件在 `output/promo-video/`，不进 Git，由 `promo/v4/build.sh` 生成。再生成网页版：

```sh
ffmpeg -i output/promo-video/jianwen-promo-v4-30s.mp4 -map 0:v:0 -map 0:a:0 -vf scale=720:1280:flags=lanczos \
  -c:v libx264 -profile:v main -preset slow -b:v 1200k -maxrate 1600k -bufsize 3200k -pix_fmt yuv420p \
  -c:a aac -b:a 96k -ar 48000 -movflags +faststart webpage/assets/promo/jianwen-promo-v4-720.mp4
python3 -c "from PIL import Image; Image.open('output/promo-video/v4/cover/cover-9x16.png').convert('RGB').resize((720,1280), Image.LANCZOS).save('webpage/assets/promo/jianwen-promo-poster.webp', 'WEBP', quality=82)"
```

页面用法见 `js/promo.js`：带控件、用户点播，不自动播放；滚出视口或切到后台时暂停；减少动态效果时不预加载。
