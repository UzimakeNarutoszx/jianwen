// Browser regression with synthetic data only. Start webpage on port 8765, open its login page,
// then run playwright-cli run-code --filename webpage/tests/weekly-browser.js.
async page => {
  const topics = ['就业','住房','医保社保','消费补贴','公共生活','社会民生','科技产业','AI技术','政策解读','绿色发展','其他'].map((name,i) => ({name,count:i%3}))
  function fixture(user) {
    const days = Array.from({length:7},(_,i)=>({date:`2026-10-${String(12+i).padStart(2,'0')}`,articles:i%3,chapters:i%2,ask:15,ajin:0,reading_seconds:60*(i+1),cumulative_seconds:30*(i+1)*(i+2)}))
    return {user:{id:user,nickname:user===1?'测试读者甲':'测试读者乙'},timezone:'Asia/Shanghai',week_start:'2026-10-12',week_end:'2026-10-18',current_week_start:'2026-10-12',is_current:true,tracking_since:'2026-10-12',
      summary:{articles:2,chapters:1,books:1,ask:105,ajin:1,reading_seconds:1680,active_days:7},days,topics,
      articles:[{content_id:'a',title:'城市公共空间如何影响日常生活？',topic:'公共生活',dates:['2026-10-12'],seconds:120},{content_id:'b',title:'从技术进步到产业变化：理解 AI 的新应用',topic:'AI技术',dates:['2026-10-13'],seconds:90}],
      classics:[{kind:'classic',content_id:'1',book_id:'book',book_title:'论语',title:'学而第一',dates:['2026-10-14'],seconds:90,scroll_progress:64}],
      questions:user===1?Array.from({length:106},(_,i)=>({id:i,channel:i===105?'ajin':'ask',question:i===105?'长图末尾问题校验标记甲':`只有甲的提问 ${i+1}：怎样理解阅读材料中的观点？\n请结合日常生活给出具体例子。`,created_at:'2026-10-16T10:30:00+08:00'})):[{id:500,channel:'ask',question:'只有乙的提问',created_at:'2026-10-16T10:30:00+08:00'}],
      legacy:[{kind:'classic',book_title:'测试名著',scroll_progress:25,title:'历史阅读位置测试',content_id:'old',date:'2026-10-12T10:00:00+08:00'}]}
  }
  await page.route('**/api/v1/profile/weekly-report*', async route => {
    const user = route.request().headers().authorization==='Bearer browser-user-b'?2:1
    await route.fulfill({status:200,contentType:'application/json',headers:{'Cache-Control':'private, no-store'},body:JSON.stringify(fixture(user))})
  })
  await page.evaluate(()=>{
    localStorage.setItem('jianwen_auth_token','browser-user-a')
    localStorage.setItem('jianwen_auth_user',JSON.stringify({id:1,nickname:'测试读者甲'}))
    localStorage.setItem('jianwen_login_expires_at',String(Date.now()+86400000))
  })
  await page.setViewportSize({width:1440,height:1050})
  await page.goto('http://127.0.0.1:8765/jianwen/weekly.html?v=20261025-3')
  await page.getByRole('button',{name:'下载完整长图'}).waitFor({state:'visible'})
  await page.waitForFunction(()=>!document.querySelector('#download-report').disabled)
  if(await page.locator('[data-chart] canvas').count()!==4) throw new Error('Missing charts')
  if(await page.locator('#weekly-report').getByText('长图末尾问题校验标记甲',{exact:true}).count()!==1) throw new Error('Full details missing')
  await page.screenshot({path:'output/playwright/weekly-desktop.png'})
  const downloaded = page.waitForEvent('download')
  await page.getByRole('button',{name:'下载完整长图'}).click()
  const file = await downloaded
  await file.saveAs('output/playwright/weekly-full.png')
  await page.getByRole('status').filter({hasText:'完整长图已生成'}).waitFor()
  if(await page.locator('#weekly-report [data-chart] canvas').count()!==4) throw new Error('Export disposed visible charts')
  const dimensions = await page.locator('#export-preview img').evaluate(img=>({width:img.naturalWidth,height:img.naturalHeight}))
  console.log('PNG downloaded',file.suggestedFilename(),dimensions)
  await page.setViewportSize({width:390,height:844})
  await page.screenshot({path:'output/playwright/weekly-mobile.png'})
  const overflow = await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
  if(overflow) throw new Error('Mobile horizontal overflow')
  await page.evaluate(()=>window.setSession({access_token:'browser-user-b',user:{id:2,nickname:'测试读者乙'}}))
  await page.waitForFunction(()=>document.querySelector('#weekly-report').textContent.includes('只有乙的提问'))
  if(await page.locator('#weekly-report').getByText('长图末尾问题校验标记甲',{exact:true}).count()) throw new Error('Previous account leaked')
  if(await page.locator('#export-preview img').count()) throw new Error('Previous image leaked')
  await page.evaluate(()=>window.clearSession())
  await page.waitForURL('**/login.html*')
  console.log('Desktop/mobile layout, all four charts, 106 questions, full PNG, account switch, image clearing and logout passed.')
}
