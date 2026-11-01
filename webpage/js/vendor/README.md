# Weekly report browser dependencies

Pinned upstream distributions, served locally (no runtime CDN requests):

- ECharts 5.6.0: https://www.npmjs.com/package/echarts/v/5.6.0 — Apache-2.0, see `echarts.LICENSE`.
- html-to-image 1.11.13: https://www.npmjs.com/package/html-to-image/v/1.11.13 — MIT, see `html-to-image.LICENSE`.

Downloaded from jsDelivr's npm distribution. Replacing either dependency requires rerunning the full PNG browser regression; successful DOM rendering alone does not verify chart capture.

The original personal intro and its unused tsParticles distribution are excluded
from this public edition. The two distributions above retain their upstream
license files.
