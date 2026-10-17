async (page) => {
  page.setDefaultTimeout(12000)
  const origin = 'http://127.0.0.1:4174'
  const assert = (value, message) => { if (!value) throw new Error(message) }
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(origin + '/#/pages/weekly/weekly')
  await page.reload()
  await page.getByText('从养老收费，到中国制造的新变化', { exact: true }).waitFor()
  assert(await page.locator('uni-tabbar .uni-tabbar__label').allTextContents().then(x => x.join('/') === '今日/发现/每周/问问/我的'), 'five navigation tabs')
  assert(await page.locator('video').count() === 1, 'native H5 video')
  await page.screenshot({ path: 'output/frontend-weekly-mobile.png' })
  await page.locator('uni-button.chapter-row').filter({hasText:'本周重点文章'}).click()
  await page.waitForFunction(() => document.querySelector('video')?.currentTime >= 22)
  await page.getByRole('tab', { name: '我的周报' }).click()
  await page.getByText('登录查看周报', { exact: true }).waitFor()
  assert(await page.locator('video').count() === 0, 'video removed when report selected')
  await page.goto(origin + '/#/pages/settings/changelog')
  const changelog = await (await page.request.get('http://127.0.0.1:8000/public/data/changelog.json')).json()
  const updateCount = changelog.entries.flatMap(entry => entry.groups.flatMap(group => group.items)).length
  await page.getByText(`全部 · ${updateCount} 条更新`, { exact: true }).waitFor()
  await page.getByText('App', { exact: true }).click()
  assert(!(await page.locator('.entry-title').allTextContents()).includes('横屏网站首版'), 'changelog app filter')
  await page.screenshot({ path: 'output/frontend-changelog-mobile.png' })
  const report = {
    user: { id: 9001, nickname: '测试读者' }, timezone: 'Asia/Shanghai', week_start: '2026-10-12', week_end: '2026-10-18', current_week_start: '2026-10-12', is_current: true, tracking_since: '2026-10-12',
    summary: { articles: 1, chapters: 1, books: 1, ask: 2, ajin: 1, reading_seconds: 150, active_days: 2 },
    days: Array.from({ length: 7 }, (_, i) => ({ date: `2026-10-${12 + i}`, articles: i === 0 ? 1 : 0, chapters: i === 1 ? 1 : 0, ask: i === 0 ? 2 : 0, ajin: i === 0 ? 1 : 0, reading_seconds: i === 0 ? 150 : 0, cumulative_seconds: 150 })),
    topics: [{ name: '科技', count: 1 }, { name: '社会', count: 0 }, {name:'其他',count:0}],
    articles: [{ content_id: 'one', title: '本周文章标题', topic: '科技', dates: ['2026-10-12'], seconds: 120 }],
    classics: [{ book_id: 'b', content_id: '1', title: '第一章', book_title: '测试名著', dates: ['2026-10-13'], scroll_progress: 40, seconds: 30 }],
    questions: [{ channel: 'ask', question: '怎样理解这项变化？', created_at: '2026-10-12T10:00:00+08:00' }, { channel: 'ajin', question: '继续追问', created_at: '2026-10-12T11:00:00+08:00' }], legacy: []
  }
  await page.route('**/api/v1/profile/weekly-report*', route => {
    const week = new URL(route.request().url()).searchParams.get('week_start') || report.week_start
    return route.fulfill({ json: { ...report, week_start: week, is_current: week === report.week_start } })
  })
  await page.evaluate(() => { localStorage.setItem('jianwen_auth_token', 'frontend-browser-test'); localStorage.setItem('jianwen_auth_user', JSON.stringify({type:'object',data:{id:9001,nickname:'测试读者'}})) })
  await page.goto(origin + '/#/pages/weekly/weekly')
  await page.reload()
  await page.getByRole('tab', { name: '我的周报' }).click()
  await page.getByText('测试读者的见闻周报', { exact: true }).waitFor()
  assert(await page.locator('.report-chart canvas').count() === 4, 'four canvas charts')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  assert(!overflow, 'no mobile horizontal overflow')
  await page.screenshot({ path: 'output/frontend-report-mobile.png', fullPage: true })
  await page.evaluate(() => document.addEventListener('click', event => {
    if (event.target instanceof HTMLAnchorElement && event.target.download) window.__weeklyExportUrl = event.target.href
  }, true))
  const downloadEvent = page.waitForEvent('download')
  await page.getByText('导出完整周报长图', {exact:true}).click()
  const download = await downloadEvent
  await download.saveAs('output/frontend-weekly-report.png')
  const hasFullImage = await page.evaluate(async () => {
    const img = new Image(); img.src = window.__weeklyExportUrl; await img.decode()
    const canvas = document.createElement('canvas'); canvas.width = img.width; canvas.height = img.height
    const ctx = canvas.getContext('2d'); ctx.drawImage(img, 0, 0)
    return img.height > 1000 && ctx.getImageData(20, img.height - 1, 1, 1).data[3] === 255
  })
  assert(hasFullImage, 'export backing canvas includes final row; no one-pixel blank export')
  await page.getByText('完整长图已生成，可预览或保存。所有明细均已包含。', { exact:true }).waitFor()
  await page.getByText('上一周', {exact:true}).click()
  await page.getByText('2026-10-05 — 2026-10-18', {exact:true}).waitFor()
  assert(await page.getByText('完整长图已生成，可预览或保存。所有明细均已包含。', {exact:true}).count() === 0, 'old export cleared')
  await page.getByText('回到本周', {exact:true}).click()
  await page.getByText('2026-10-12 — 2026-10-18', {exact:true}).waitFor()
  await page.setViewportSize({width:1280,height:900})
  await page.screenshot({path:'output/frontend-report-desktop.png'})
  await page.evaluate(() => {localStorage.removeItem('jianwen_auth_token');localStorage.removeItem('jianwen_auth_user')})
  await page.goto(origin + '/#/pages/weekly/weekly')
  await page.reload()
  await page.getByRole('tab', {name:'我的周报'}).click()
  await page.getByText('登录查看周报',{exact:true}).waitFor()
  assert(await page.locator('.weekly-paper').count() === 0, 'logout clears private report')
  assert(errors.length === 0, 'browser errors: ' + errors.join('; '))
}
