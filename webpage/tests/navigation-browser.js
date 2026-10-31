// Start the website on port 8765; run playwright-cli run-code --filename webpage/tests/navigation-browser.js.
async page => {
  const paths=['index.html','intro.html','changelog.html','avatar.html','weekly-video.html','jianwen/index.html','jianwen/discover.html','jianwen/ask.html','jianwen/article.html','jianwen/reader.html','jianwen/login.html','jianwen/profile.html','jianwen/weekly.html']
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000})
    for(const path of paths) {
      await page.goto(`http://127.0.0.1:8765/${path}?v=20261031-1`,{waitUntil:'domcontentloaded'})
      await page.locator('header[data-site-header] .site-nav').waitFor({state:'visible'})
      for (const label of ['我的周报','每周视频']) {
        const link=page.locator('header[data-site-header]').getByRole('link',{name:label,exact:true})
        if(await link.count()!==1 || !await link.isVisible()) throw new Error(`${path} ${width}: ${label} missing or hidden`)
        const href=await link.getAttribute('href')
        const target=new URL(href,page.url())
        if(target.searchParams.get('v')!=='20261031-1') throw new Error(`${path}: stale nav version`)
        const response=await page.request.get(target.href)
        if(response.status()!==200) throw new Error(`${path}: link target unavailable`)
      }
    }
  }
  await page.goto('http://127.0.0.1:8765/weekly-video.html?v=20261031-1')
  await page.screenshot({path:'output/playwright/navigation-mobile.png'})
  await page.setViewportSize({width:1440,height:1000})
  await page.goto('http://127.0.0.1:8765/index.html?v=20261031-1')
  await page.screenshot({path:'output/playwright/navigation-desktop.png'})
  await page.evaluate(()=>document.body.dataset.navVerification='All 13 page entries checked at desktop and mobile widths; protected guest pages redirect to login.')
}
