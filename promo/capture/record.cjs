// 宣传片录屏：每个镜头单独一个浏览器上下文录制，输出 webm + 内容就绪时间点
// 用法: node promo/capture/record.cjs [镜头名...]
// 依赖本机已启动 8000 后端、8765 网站、5173 H5；PLAYWRIGHT_PATH 指向 playwright 包
const fs = require('fs')
const path = require('path')
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright')

const ROOT = path.resolve(__dirname, '../..')
const OUT = path.join(ROOT, 'output/promo-video/capture')
const H5 = 'http://localhost:5173/#/'
const WEB = 'http://127.0.0.1:8765/'
const PHONE = process.env.PROMO_PHONE
const PASSWORD = process.env.PROMO_PASSWORD
const ARTICLE = 'ai-daily-20261011-3'
const MOBILE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, size: { width: 780, height: 1688 } }
const DESKTOP = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, size: { width: 1440, height: 900 } }

const sleep = ms => new Promise(r => setTimeout(r, ms))

// 平滑滚动：总距离 px，在 ms 内匀速完成
async function glide(page, px, ms, selector) {
  const steps = Math.round(ms / 16)
  for (let i = 0; i < steps; i++) {
    await page.evaluate(([dy, sel]) => {
      const el = sel && document.querySelector(sel)
      ;(el || window).scrollBy(0, dy)
    }, [px / steps, selector])
    await sleep(16)
  }
}

async function loginState(browser, kind) {
  const file = path.join(OUT, `.state-${kind}.json`)
  const ctx = await browser.newContext(kind === 'h5' ? MOBILE : DESKTOP)
  const page = await ctx.newPage()
  if (kind === 'h5') {
    await page.goto(H5 + 'pages/auth/login', { waitUntil: 'networkidle' })
    await sleep(800)
    const inputs = page.locator('input')
    await inputs.nth(0).fill(PHONE)
    await inputs.nth(1).fill(PASSWORD)
    await page.locator('uni-button:has-text("登录")').last().click()
  } else {
    await page.goto(WEB + 'jianwen/login.html', { waitUntil: 'networkidle' })
    await page.fill('#phone', PHONE)
    await page.fill('#password', PASSWORD)
    await page.click('#submit-button')
  }
  await sleep(2500)
  const ok = await page.evaluate(() => !!localStorage.getItem('jianwen_auth_token'))
  if (!ok) throw new Error(`${kind} 登录失败`)
  await ctx.storageState({ path: file })
  await ctx.close()
  return file
}
// 每个镜头：先 goto 并等内容就绪，再调用 mark() 记下剪辑起点，之后的动作就是成片画面
const SHOTS = {
  async today(page, mark) {
    await page.goto(H5 + 'pages/today/today', { waitUntil: 'networkidle' })
    await sleep(1500); mark()
    await sleep(1500)
    await glide(page, 1100, 6000)
    await sleep(1500)
  },
  async article(page, mark) {
    await page.goto(H5 + `pages/article/detail?id=${ARTICLE}`, { waitUntil: 'networkidle' })
    await sleep(1500); mark()
    await sleep(1200)
    await glide(page, 260, 1500)
    await sleep(2500)
    // 跳到"来源与依据"
    await glide(page, 2350, 3500)
    await sleep(2000)
  },
  async ask(page, mark) {
    await page.goto(H5 + 'pages/ask/ask', { waitUntil: 'networkidle' })
    await sleep(1500); mark()
    await sleep(800)
    const input = page.locator('.composer-input input').first()
    await input.click()
    await input.pressSequentially('青年就业支持计划和我有什么关系？', { delay: 90 })
    await sleep(400)
    await page.locator('.send-button').first().click()
    // 等流式回答出来并多停留一会儿
    await sleep(9000)
  },
  async discover(page, mark) {
    await page.goto(H5 + 'pages/discover/discover', { waitUntil: 'networkidle' })
    await sleep(1500); mark()
    await sleep(800)
    await glide(page, 700, 2500)
    await sleep(800)
    // 带 chapterId 直接进正文，再左滑翻两页
    await page.goto(H5 + 'pages/classics/reader?bookId=party-constitution&chapterId=1', { waitUntil: 'networkidle' })
    await sleep(1800)
    for (let i = 0; i < 2; i++) {
      await page.mouse.move(330, 450)
      await page.mouse.down()
      await page.mouse.move(40, 455, { steps: 18 })
      await page.mouse.up()
      await sleep(1800)
    }
  },
  // 手机浏览器打开横屏网站（响应式布局），用于"手机也能看网页版"
  async 'web-mobile'(page, mark) {
    await page.goto(WEB + 'jianwen/index.html', { waitUntil: 'networkidle' })
    await sleep(1500); mark()
    await sleep(1000)
    await glide(page, 900, 3500)
    await sleep(600)
    await page.goto(WEB + 'jianwen/reader.html?book=party-constitution', { waitUntil: 'networkidle' })
    await sleep(1200)
    await glide(page, 700, 3000)
    await sleep(1000)
  },
  async web(page, mark) {
    await page.goto(WEB + 'index.html', { waitUntil: 'networkidle' })
    await sleep(1500); mark()
    await sleep(1500)
    await page.goto(WEB + 'jianwen/reader.html?book=party-constitution', { waitUntil: 'networkidle' })
    await sleep(1000)
    await glide(page, 600, 2500)
    await sleep(1500)
  }
}

;(async () => {
  if (!PHONE || !PASSWORD) throw new Error('需要 PROMO_PHONE 和 PROMO_PASSWORD 环境变量')
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await chromium.launch({ channel: 'chrome' })
  const states = { h5: await loginState(browser, 'h5'), web: await loginState(browser, 'web') }
  const names = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(SHOTS)
  const marks = fs.existsSync(path.join(OUT, 'marks.json')) ? JSON.parse(fs.readFileSync(path.join(OUT, 'marks.json'))) : {}

  for (const full of names) {
    // 镜头名后缀 -dark：录制 App 深色模式版本（uni 存储格式 {type,data}）
    const dark = full.endsWith('-dark')
    const name = dark ? full.slice(0, -5) : full
    const kind = name.startsWith('web') ? 'web' : 'h5'
    const preset = name === 'web' ? DESKTOP : MOBILE
    const tmp = path.join(OUT, `.tmp-${full}`)
    fs.rmSync(tmp, { recursive: true, force: true })
    fs.mkdirSync(tmp, { recursive: true })
    const ctx = await browser.newContext({ ...preset, storageState: states[kind] })
    if (dark) await ctx.addInitScript(() => localStorage.setItem('jianwen_dark_mode', JSON.stringify({ type: 'boolean', data: true })))
    const page = await ctx.newPage()
    const errors = []
    page.on('pageerror', e => errors.push(e.message))
    // CDP screencast：每帧 JPEG 带时间戳，跨页面跳转也不断
    const cdp = await ctx.newCDPSession(page)
    const frames = []
    cdp.on('Page.screencastFrame', async f => {
      const file = path.join(tmp, `${String(frames.length).padStart(5, '0')}.jpg`)
      fs.writeFileSync(file, Buffer.from(f.data, 'base64'))
      frames.push({ file, ts: f.metadata.timestamp })
      cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {})
    })
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 95, maxWidth: preset.size.width, maxHeight: preset.size.height, everyNthFrame: 1 })
    const t0 = Date.now() / 1000; let start = 0
    await SHOTS[name](page, () => { start = Date.now() / 1000 - t0 })
    await sleep(100)
    const end = Date.now() / 1000 - t0
    await cdp.send('Page.stopScreencast').catch(() => {})
    // 记下镜头结束时屏幕上的文字，供人工核对画面内容
    const screenText = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 600)).catch(() => '')
    await ctx.close()
    // 用 concat 清单按真实帧间隔拼接，再转成恒定 30fps
    const list = frames.map((f, i) => `file '${f.file}'\nduration ${((frames[i + 1] ? frames[i + 1].ts : t0 + end) - f.ts).toFixed(4)}`).join('\n')
    fs.writeFileSync(path.join(tmp, 'list.txt'), list + `\nfile '${frames[frames.length - 1].file}'\n`)
    const dest = path.join(OUT, `${full}.mp4`)
    const lead = frames.length ? Math.max(0, frames[0].ts - t0) : 0
    require('child_process').execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', path.join(tmp, 'list.txt'),
      '-vf', `fps=30,scale=${preset.size.width}:${preset.size.height}:flags=lanczos,format=yuv420p`, '-c:v', 'libx264', '-crf', '14', '-preset', 'slow', dest])
    start = Math.max(0, start - lead)
    fs.rmSync(tmp, { recursive: true, force: true })
    marks[full] = { start: +start.toFixed(2), end: +end.toFixed(2), errors, screenText }
    console.log(`${full}: ${dest} start=${start.toFixed(2)}s end=${end.toFixed(2)}s${errors.length ? ' errors=' + errors.join('; ') : ''}`)
  }
  fs.writeFileSync(path.join(OUT, 'marks.json'), JSON.stringify(marks, null, 2))
  for (const f of Object.values(states)) fs.rmSync(f, { force: true })
  await browser.close()
})().catch(e => { console.error(e); process.exit(1) })
