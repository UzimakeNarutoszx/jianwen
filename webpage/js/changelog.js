// 更新日志筛选：?type=web|app|ai。不开 JS 时显示全部条目
;(() => {
  const types = { web: '网站', app: 'App', ai: '后端与 AI' }
  const type = new URLSearchParams(location.search).get('type')
  const active = type in types ? type : 'all'
  document.querySelectorAll('.changelog-filters a').forEach(a => {
    if (a.dataset.filter === active) a.setAttribute('aria-current', 'page')
    else a.removeAttribute('aria-current')
  })
  let shown = 0
  document.querySelectorAll('.changelog-month').forEach(month => {
    let monthShown = 0
    month.querySelectorAll('article').forEach(article => {
      let articleShown = 0
      article.querySelectorAll('li[data-type]').forEach(li => {
        const match = active === 'all' || li.dataset.type.split(' ').includes(active)
        li.hidden = !match
        articleShown += match
      })
      // 小标题下没有可见条目时一并隐藏
      article.querySelectorAll('h4').forEach(h => {
        const list = h.nextElementSibling
        h.hidden = !list || ![...list.children].some(li => !li.hidden)
        if (list) list.hidden = h.hidden
      })
      article.hidden = articleShown === 0
      shown += articleShown
      monthShown += articleShown
    })
    month.hidden = monthShown === 0
    const link = document.querySelector(`.changelog-months a[href="#${month.id}"]`)
    if (link) link.hidden = month.hidden
  })
  const count = document.querySelector('[data-changelog-count]')
  if (count) count.textContent = active === 'all' ? `共 ${shown} 条更新` : `${types[active]}：${shown} 条更新`
})()
