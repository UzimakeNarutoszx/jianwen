(function () {
  'use strict'
  const $ = id => document.getElementById(id)
  const root = $('weekly-report'), status = $('weekly-status'), download = $('download-report')
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
  const colors = ['#28645e', '#c09a54', '#597d9b', '#96647c', '#729255', '#aa704e']
  let report = null, charts = [], generation = 0, selected = '', blobUrl = '', exporting = false
  let identity = window.getToken()
  const minutes = seconds => (seconds / 60).toFixed(1)
  const shift = (date, days) => new Date(Date.parse(`${date}T00:00:00Z`) + days * 86400000).toISOString().slice(0, 10)
  const list = (items, render, empty) => items.length ? `<ul class="weekly-list">${items.map(item => `<li>${render(item)}</li>`).join('')}</ul>` : `<p class="weekly-empty">${esc(empty)}</p>`
  function dispose() { charts.forEach(chart => chart.dispose()); charts = [] }
  function revoke() { if (blobUrl) URL.revokeObjectURL(blobUrl); blobUrl = ''; $('export-preview').replaceChildren() }
  function clear() {
    generation++; report = null; dispose(); root.replaceChildren(); revoke(); download.disabled = true
    document.querySelectorAll('.weekly-export').forEach(node => node.remove())
  }
  function login() { location.replace(`login.html?return=${encodeURIComponent(location.pathname + location.search)}`) }
  function guard() {
    if (window.getToken() !== identity || !window.getToken()) {
      clear(); identity = window.getToken(); status.textContent = '账号已变更，正在重新加载…'
      if (!identity) login(); else load(selected)
      return false
    }
    return true
  }
  const articleLink = item => `article.html?id=${encodeURIComponent(item.content_id)}`
  const classicLink = item => `reader.html?book=${encodeURIComponent(item.book_id)}&chapter=${encodeURIComponent(item.content_id)}`
  function render(data) {
    const s = data.summary
    const questionList = channel => list(data.questions.filter(q => q.channel === channel), q => `<strong>${esc(q.question)}</strong><small>${esc(q.created_at.slice(0, 16).replace('T', ' '))}</small>`, '这一周还没有提问记录。')
    root.innerHTML = `<article class="weekly-paper">
      <header class="weekly-cover"><h2>${esc(data.user.nickname)}的见闻周报</h2><p>${data.week_start} — ${data.week_end}</p><span class="weekly-badge">${data.is_current ? '本周 · 持续更新中' : '个人历史周报'}</span><p>这一周，你有 ${s.active_days} 天留下阅读或提问记录。</p></header>
      <dl class="weekly-stats"><div><dt>文章阅读</dt><dd>${s.articles}<small>篇</small></dd></div><div><dt>名著阅读</dt><dd>${s.chapters}<small>章 / ${s.books} 本</small></dd></div><div><dt>AI 问问</dt><dd>${s.ask}<small>次</small></dd></div><div><dt>阿烬提问</dt><dd>${s.ajin}<small>次</small></dd></div><div><dt>有效停留</dt><dd>${minutes(s.reading_seconds)}<small>分钟</small></dd></div></dl>
      <section class="weekly-charts" aria-label="本周个人使用图表">
        ${[['daily','每天的阅读与追问','每天同一文章、章节各计一次；提问按次数统计。'],['topics','阅读主题占比','按本周读过的不同文章统计，包含已有浏览记录。'],['trend','阅读时间的积累','仅累计实际采集到的前台停留，不补算历史时长。'],['radar','我的主题阅读分布','沿用网站主题顺序，数值为文章篇数，不代表能力评分。']].map(([key,title,caption]) => `<figure class="weekly-figure"><h3>${title}</h3><div class="weekly-chart" data-chart="${key}" role="img" aria-label="${title}，数据见下方明细"></div><figcaption>${caption}</figcaption></figure>`).join('')}
      </section>
      <details class="weekly-data"><summary>查看图表数据</summary><div class="weekly-table-wrap"><table class="weekly-table"><caption>本周每日使用记录</caption><thead><tr><th scope="col">日期</th><th scope="col">文章</th><th scope="col">章节</th><th scope="col">问问</th><th scope="col">阿烬</th><th scope="col">停留分钟</th></tr></thead><tbody>${data.days.map(d => `<tr><th scope="row">${d.date}</th><td>${d.articles}</td><td>${d.chapters}</td><td>${d.ask}</td><td>${d.ajin}</td><td>${minutes(d.reading_seconds)}</td></tr>`).join('')}</tbody></table></div><p>${data.topics.map(t => `${esc(t.name)} ${t.count} 篇`).join(' · ')}</p></details>
      <section class="weekly-data"><h3>这一周，看过的文章 · ${s.articles} 篇</h3>${list(data.articles, i => `<a href="${articleLink(i)}"><strong>${esc(i.title)}</strong></a><small>${esc(i.topic)} · ${esc(i.dates.join('、'))} · ${i.seconds > 0 ? `已记录停留 ${minutes(i.seconds)} 分钟` : '未采集阅读时长'}</small>`, '这一周还没有文章阅读记录。')}</section>
      <section class="weekly-data"><h3>这一周，问过的问题</h3><h4>AI 问问 · ${s.ask} 次</h4>${questionList('ask')}<h4>阿烬 · ${s.ajin} 次</h4>${questionList('ajin')}</section>
      <section class="weekly-data"><h3>这一周，读过的名著 · ${s.books} 本</h3>${list(data.classics, i => `<a href="${classicLink(i)}"><strong>${esc(i.book_title)} · ${esc(i.title)}</strong></a><small>${esc(i.dates.join('、'))} · 章内最近进度 ${i.scroll_progress}% · 有效停留 ${minutes(i.seconds)} 分钟</small>`, '还没有累计停留满 30 秒的名著章节。')}</section>
      ${data.legacy.length ? `<section class="weekly-data"><h3>名著历史位置</h3><p>仅保留最近阅读位置，无法确认有效停留，不计入上方名著阅读统计。</p>${list(data.legacy, i => `<strong>${esc(i.book_title ? `${i.book_title} · ` : '')}${esc(i.title)}</strong><small>${esc(i.date.slice(0, 16).replace('T',' '))}${i.kind === 'classic' ? ` · 章内进度 ${i.scroll_progress}%` : ''}</small>`, '')}</section>` : ''}
      <footer class="weekly-notes">仅记录当前登录账号的个人活动。北京时间周一至周日。<br>文章按已有浏览／已读记录计数，同一天同一篇只计一次，本周按文章去重；名著章节仍需累计有效停留满 30 秒。每日数量之和可能与周去重数量不同。隐藏、失焦或连续 60 秒无操作时暂停计时，重叠时间只计一次。<br>${data.tracking_since ? `当前账号最早留存的有效停留记录：${data.tracking_since}。` : '当前账号尚无有效停留记录。'}历史文章计入篇数，不补算未采集的阅读时长。周报随记录清除而更新。</footer>
    </article>`
  }
  function options(data) {
    const base = { animation: false, color: colors, textStyle: { fontFamily: 'sans-serif', color: '#152c31' }, tooltip: { trigger: 'axis', renderMode: 'richText' }, aria: { enabled: true } }
    const names = ['文章', '名著章节', 'AI 问问', '阿烬'], fields = ['articles','chapters','ask','ajin']
    const nonzero = data.topics.filter(t => t.count)
    const axes = data.topics.slice()
    // Radar requires at least three axes; real empty placeholders never carry values.
    while (axes.length < 3) axes.push({ name: '暂无主题', count: 0 })
    return {
      daily: { ...base, legend: { data: names, bottom: 0 }, grid: { left: 38, right: 12, top: 24, bottom: 62 }, xAxis: { type: 'category', data: data.days.map(d => d.date.slice(5)) }, yAxis: { type: 'value', minInterval: 1 }, series: fields.map((f,i) => ({ type:'bar', name:names[i], data:data.days.map(d => d[f]), barMaxWidth: 18 })) },
      topics: { ...base, tooltip: { trigger:'item', renderMode:'richText' }, title: nonzero.length ? undefined : { text:'本周暂无文章阅读', left:'center', top:'center', textStyle:{ color:'#657779', fontSize:14, fontWeight:400 } }, legend: { bottom:0, type:'scroll' }, series:[{ type:'pie', radius:['0%','62%'], center:['50%','43%'], label:{ show:false }, data:nonzero.map(t => ({ name:t.name, value:t.count })) }] },
      trend: { ...base, grid:{ left:45, right:18, top:32, bottom:32 }, xAxis:{ type:'category', boundaryGap:false, data:data.days.map(d => d.date.slice(5)) }, yAxis:{ type:'value', name:'分钟' }, series:[{ type:'line', name:'累计有效停留（分钟）', data:data.days.map(d => Number(minutes(d.cumulative_seconds))), smooth:false, lineStyle:{ width:3 }, symbolSize:7 }] },
      radar: { ...base, tooltip:{ trigger:'item', renderMode:'richText' }, radar:{ center:['50%','50%'], radius:'60%', splitNumber:3, axisName:{ color:'#152c31', fontSize:11, formatter:name => name.length > 5 ? `${name.slice(0,5)}\n${name.slice(5)}` : name }, indicator:axes.map(t => ({ name:t.name, max:Math.max(1,...axes.map(a => a.count)) })) }, series:[{ type:'radar', data:[{ name:'阅读文章（篇）', value:axes.map(t => t.count) }], areaStyle:{ opacity:0.12 } }] }
    }
  }
  function draw(container, data) {
    if (!window.echarts) throw new Error('图表组件加载失败，请刷新重试。')
    const config = options(data)
    return [...container.querySelectorAll('[data-chart]')].map(node => {
      const chart = echarts.init(node, null, { renderer:'canvas' })
      chart.setOption(config[node.dataset.chart]); return chart
    })
  }
  async function load(week = '') {
    clear()
    const request = generation, expected = identity
    selected = week
    status.textContent = '正在整理你的周报…'; root.setAttribute('aria-busy','true')
    try {
      const data = await window.jianwenApi.weeklyReport(week)
      if (request !== generation || expected !== window.getToken()) return
      report = data; selected = data.week_start; render(data); charts = draw(root, data)
      $('week-date').value = selected; $('week-date').max = data.current_week_start
      $('next-week').disabled = selected >= data.current_week_start
      $('previous-week').disabled = selected <= '2000-01-03'
      download.disabled = false
      status.textContent = data.summary.active_days ? '你的个人记录已更新，可下载完整长图。' : '这一周还没有使用记录，开始阅读或提问后会在这里显示。'
      history.replaceState(null, '', `${location.pathname}?week_start=${selected}&v=20261017-4`)
    } catch (error) {
      if (request !== generation || expected !== window.getToken()) return
      status.textContent = `周报加载失败：${error.message}`
      const retry = document.createElement('button'); retry.className='button button-secondary'; retry.textContent='重新加载'; retry.onclick=() => load(week); root.replaceChildren(retry)
    } finally { if (request === generation) root.setAttribute('aria-busy','false') }
  }
  async function exportReport() {
    if (!guard() || !report || exporting) return
    exporting = true; download.disabled = true; revoke()
    const expected = identity, version = generation, data = report
    let stage, exportCharts = []
    status.textContent = '正在生成完整长图，请稍候…'
    try {
      if (!window.htmlToImage) throw new Error('图片组件加载失败，请刷新重试。')
      await document.fonts.ready
      stage = document.createElement('div'); stage.className='weekly-export'; stage.setAttribute('aria-hidden','true'); stage.inert = true
      stage.append(root.firstElementChild.cloneNode(true)); document.body.append(stage)
      stage.querySelectorAll('details').forEach(node => { node.open = true })
      // Cloned ECharts IDs would otherwise resolve to (and dispose) the live charts.
      stage.querySelectorAll('[data-chart]').forEach(node => { node.replaceChildren(); node.removeAttribute('_echarts_instance_') })
      exportCharts = draw(stage, data)
      for (const chart of exportCharts) {
        const node = chart.getDom(), img = new Image()
        img.src = chart.getDataURL({ type:'png', pixelRatio:2, backgroundColor:'#fffef9' })
        await img.decode(); chart.dispose(); node.replaceChildren(img)
      }
      const height = stage.scrollHeight, width = 960
      const ratio = Math.min(2, 30000 / height, Math.sqrt(16000000 / (width * height)))
      if (ratio < 0.5) throw new Error('本周明细超出当前设备的单张长图容量，请使用内存更充足的设备重试。')
      const blob = await htmlToImage.toBlob(stage, { width, height, pixelRatio:ratio, backgroundColor:'#fffef9', skipAutoScale:true, style:{ position:'static', left:'auto', top:'auto' } })
      if (!blob || !blob.size) throw new Error('图片生成失败，请重试。')
      if (expected !== window.getToken() || version !== generation) return
      blobUrl = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href=blobUrl; link.download=`见闻周报_${data.week_start}_${data.week_end}.png`; link.textContent='再次下载完整长图'; link.className='button button-secondary'
      $('export-preview').append(link); link.click()
      const details = document.createElement('details'); details.className='weekly-preview'
      const summary = document.createElement('summary'); summary.textContent='预览长图（手机可展开后长按保存）'
      const img = new Image(); img.src=blobUrl; img.alt=`${data.user.nickname}的个人周报长图`; details.append(summary,img); $('export-preview').append(details)
      status.textContent = '完整长图已生成。若未自动下载，可点击再次下载，或展开预览保存。'
    } catch (error) { if (version === generation) status.textContent=`长图生成失败：${error.message} 可点击下载按钮重试。` }
    finally { exportCharts.forEach(c => { if (!c.isDisposed()) c.dispose() }); stage?.remove(); exporting=false; if (version === generation && report) download.disabled=false }
  }
  $('previous-week').onclick=() => { if (selected) load(shift(selected,-7)) }
  $('next-week').onclick=() => { if (report && selected < report.current_week_start) load(shift(selected,7)) }
  $('current-week').onclick=() => load()
  $('week-date').onchange=event => {
    const value = event.target.value
    if (!value) return
    const weekday = new Date(`${value}T00:00:00Z`).getUTCDay()
    load(shift(value,-((weekday+6)%7)))
  }
  download.onclick=exportReport
  window.addEventListener('resize', () => charts.forEach(c => c.resize()))
  window.addEventListener('storage', guard)
  window.addEventListener('jianwen-session-change', guard)
  window.addEventListener('pagehide', clear)
  window.addEventListener('pageshow', event => { if (event.persisted && guard()) load(selected) })
  document.addEventListener('visibilitychange', () => { if (!document.hidden) guard() })
  if (!identity) login(); else load(new URLSearchParams(location.search).get('week_start') || '')
})()
