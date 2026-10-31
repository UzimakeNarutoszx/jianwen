# Weekly report browser dependencies

Pinned upstream distributions, served locally (no runtime CDN requests):

- ECharts 5.6.0: https://www.npmjs.com/package/echarts/v/5.6.0 — Apache-2.0, see `echarts.LICENSE`.
- html-to-image 1.11.13: https://www.npmjs.com/package/html-to-image/v/1.11.13 — MIT, see `html-to-image.LICENSE`.

Downloaded from jsDelivr's npm distribution. Replacing either dependency requires rerunning the full PNG browser regression; successful DOM rendering alone does not verify chart capture.

# Intro page dependencies

- tsParticles slim bundle 3.9.1: https://cdn.jsdelivr.net/npm/@tsparticles/slim@3.9.1 (`tsparticles.slim.bundle.min.js`, saved here as `tsparticles.slim.bundle-3.9.1.min.js`) — MIT. Used only by `intro.html`; upstream license header is kept in the file.

Both script bundles are loaded from this directory instead of a CDN, so the site keeps working offline and without a third-party runtime request.
