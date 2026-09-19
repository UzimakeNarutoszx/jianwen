# Local motion assets

The studio film is no longer displayed anywhere on the site. Its source assets remain available for future editing.

Only `data-motion-film="ambient"` is initialized by `js/motion.js`. This silent decorative background plays once for at most 4.5 seconds, with no playback buttons. Offscreen and hidden-tab playback pauses. Reduced-motion and Save Data preferences avoid downloading the video; the poster remains visible. Media failures also retain the poster.

`data-motion-reveal` enables a brief entrance animation without hiding content when JavaScript is unavailable.

Rebuild assets: `python webpage/assets/motion/generate_motion.py` (Pillow, numpy, imageio-ffmpeg).
Verify behavior: `node webpage/assets/motion/verify-motion.cjs`.
