// Run with playwright-cli run-code; all fixture data exists only in this browser.
async (page) => {
  await page.unrouteAll({behavior:'wait'})
  const check = (value, message) => { if (!value) throw new Error(message) }
  const address = 'http://127.0.0.1:8765/weekly-video.html?v=20261011-1'
  await page.setViewportSize({width:390,height:844})
  await page.route('**/data/weekly-videos.json', route => route.fulfill({json:{episodes:[],upcoming:{id:'qa-pending',number:1,title:'制作中测试',description:'仅用于测试',weekStart:'2026-10-12',weekEnd:'2026-10-18',cutoff:'2026-10-17T18:30:00+08:00',poster:'assets/weekly-video/2026-W42/cover.jpg'}}}))
  await page.goto(address)
  await page.getByText('首期制作中',{exact:true}).waitFor()
  const anonymous = await page.locator('#episode').innerText()
  check(await page.locator('#episode video').count() === 0, 'Unpublished episode must not have a fake player')
  await page.evaluate(() => {
    localStorage.setItem('jianwen_auth_token','weekly-video-browser-test')
    localStorage.removeItem('jianwen_login_expires_at')
  })
  await page.reload()
  await page.getByText('首期制作中',{exact:true}).waitFor()
  check(await page.locator('#episode').innerText() === anonymous, 'Episode content must be account-independent')
  check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile layout overflows')
  await page.evaluate(() => localStorage.removeItem('jianwen_auth_token'))

  const base = {number:1,status:'published',title:'浏览器验收节目',description:'仅存在于测试路由中，不写入公开清单。',weekEnd:'2026-10-18',cutoff:'2026-10-17T18:30:00+08:00',poster:'assets/weekly-video/2026-W42/cover.jpg',video:'assets/weekly-video/qa.mp4',durationSeconds:203,articles:[],sources:[],chapters:[{title:'片头导读',seconds:0},{title:'本周重点文章',seconds:1.1}]}
  const fixtures = {episodes:[
    {...base,id:'qa-old',weekStart:'2026-10-05',publishedAt:'2026-10-10T12:00:00+08:00'},
    {...base,id:'qa-current',number:2,weekStart:'2026-10-12',publishedAt:'2026-10-17T12:00:00+08:00'}
  ]}
  await page.unroute('**/data/weekly-videos.json')
  await page.route('**/data/weekly-videos.json', route => route.fulfill({json:fixtures}))
  const studio = await (await page.request.get('http://localhost:3016/')).text()
  const prefix = studio.match(/static-[a-f0-9]+/)?.[0]
  check(prefix, 'Studio public asset prefix missing')
  const media = await page.request.get(`http://localhost:3016/${prefix}/identity/identity.mp4`)
  check(media.ok(), 'Blender video not served')
  const body = await media.body()
  await page.route('**/assets/weekly-video/qa.mp4', route => route.fulfill({status:200,contentType:'video/mp4',body}))
  await page.goto(address)
  await page.getByText('本周视频',{exact:true}).waitFor()
  check(await page.locator('#archive-list article').count() === 1,'Pinned episode duplicated or archive missing')
  await page.getByRole('button',{name:'本周重点文章'}).click()
  await page.waitForFunction(() => {const v=document.querySelector('video'); return v.readyState > 0 && v.currentTime >= 1})
  await page.locator('video').evaluate(video => video.pause())
  await page.locator('#archive-list h3').click()
  await page.getByText('往期节目',{exact:true}).waitFor()
  check(new URL(page.url()).searchParams.get('episode') === 'qa-old','Archive deep link missing')
  await page.goBack()
  await page.getByText('本周视频',{exact:true}).waitFor()
  await page.goto(`${address}&episode=qa-old`)
  await page.getByText('往期节目',{exact:true}).waitFor()
  await page.goto(`${address}&episode=does-not-exist`)
  await page.getByText('没有找到这期节目，已展示最近可用的节目。',{exact:true}).waitFor()

  await page.unroute('**/assets/weekly-video/qa.mp4')
  await page.route('**/assets/weekly-video/qa.mp4', route => route.abort())
  await page.goto(address)
  await page.getByRole('button',{name:'本周重点文章'}).click()
  await page.getByText('视频暂时无法播放',{exact:true}).waitFor()
  check(await page.locator('video').isHidden(),'Broken player still obscures poster')
  check(await page.getByRole('button',{name:'本周重点文章'}).isDisabled(),'Broken chapter controls still enabled')

  await page.unroute('**/data/weekly-videos.json')
  await page.goto(address)
  await page.locator('#episode[aria-busy="false"]').waitFor()
  await page.screenshot({path:'output/playwright/weekly-video-mobile-final.png',fullPage:true})
  await page.setViewportSize({width:1440,height:1000})
  await page.reload()
  await page.locator('#episode[aria-busy="false"]').waitFor()
  check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),'Desktop layout overflows')
  await page.screenshot({path:'output/playwright/weekly-video-desktop-final.png',fullPage:true})
  return {passed:true,checks:['anonymous/login parity','mobile/desktop overflow','unpublished state','pin/archive','chapter playback','deep link','history','unknown episode','media failure','Blender asset']}
}
