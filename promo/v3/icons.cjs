// 把 output/promo-video/v2/assets/icons/*.svg 用 Chrome 渲染成 512px 白色透明 PNG
const fs = require('fs'), path = require('path')
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright')
const DIR = path.resolve(__dirname, '../../output/promo-video/v2/assets/icons')
;(async () => {
  const out = path.join(DIR, 'png'); fs.mkdirSync(out, { recursive: true })
  const b = await chromium.launch({ channel: 'chrome' })
  const pg = await b.newPage({ viewport: { width: 512, height: 512 } })
  for (const f of fs.readdirSync(DIR).filter(f => f.endsWith('.svg'))) {
    const svg = fs.readFileSync(path.join(DIR, f), 'utf8').replace(/currentColor/g, '#ffffff')
      .replace(/width="24"/, 'width="512"').replace(/height="24"/, 'height="512"')
    await pg.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`)
    await pg.locator('svg').screenshot({ path: path.join(out, f.replace('.svg', '.png')), omitBackground: true })
  }
  await b.close()
  console.log('rendered', fs.readdirSync(out).length, 'icons')
})()
