# Original local motion films

Both MP4 files are silent H.264, 960 × 540, 24 fps, 10 seconds, with fast-start metadata. The loop uses periodic motion. Source art is the existing local 阿烬主机.png / 阿烬.png; no stock footage is used.

Load `css/motion.css` and `js/motion.js` (defer or end of body). Add:

```html
<div class="aj-film" data-motion-film="ajin"></div>
```

`ajin` and `home` use `ajin-studio.mp4`, a cream product film with baked-in editorial text. `ambient` uses `ajin-ambient.mp4`, an unlettered green background for HTML overlays. Both have corresponding `*-poster.jpg` files. Relative media URLs resolve against the script URL, so nested pages work.

The container receives a muted inline video and accessible play/pause button. Keep HTML overlays in sibling elements, or give them positioned stacking above the video. `data-motion-reveal` optionally adds a subtle one-time entrance; the content is never hidden if JS is unavailable. Add a background poster in page CSS if a no-JavaScript placeholder is required (the default stylesheet uses the studio poster).

Video downloads only when visible and permitted. Reduced-motion and Save Data preferences prevent automatic downloads and playback. Explicit play opts in. Background tabs, offscreen films and manually paused films stay paused. Failed media displays its poster. No audio track exists.

Rebuild: `python webpage/assets/motion/generate_motion.py` (Pillow, numpy, imageio-ffmpeg).
Control tests: `node webpage/assets/motion/verify-motion.cjs`.
