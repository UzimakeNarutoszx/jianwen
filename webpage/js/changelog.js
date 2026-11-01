// The website and App render the same public changelog catalog.
;(() => {
  const types = { web: '网站', app: 'App', ai: '后端与 AI' }
  const type = new URLSearchParams(location.search).get('type')
  const active = Object.hasOwn(types, type) ? type : 'all'
  const container = document.querySelector('[data-changelog-entries]')
  const months = document.querySelector('[data-changelog-months]')
  const count = document.querySelector('[data-changelog-count]')
  const retry = document.querySelector('[data-changelog-retry]')
  document.querySelectorAll('.changelog-filters a').forEach(a => {
    if (a.dataset.filter === active) a.setAttribute('aria-current', 'page')
    else a.removeAttribute('aria-current')
  })
  function element(tag, text, className) {
    const node = document.createElement(tag)
    if (text) node.textContent = text
    if (className) node.className = className
    return node
  }
  async function load() {
    retry.hidden = true
    count.textContent = '正在加载更新日志…'
    try {
      const response = await fetch('data/changelog.json', { cache: 'no-store' })
      if (!response.ok) throw new Error('加载失败')
      const data = await response.json()
      if (!Array.isArray(data.entries)) throw new Error('内容格式错误')
      container.replaceChildren()
      months.replaceChildren()
      const sections = new Map()
      let shown = 0
      for (const entry of [...data.entries].sort((a, b) => b.date.localeCompare(a.date))) {
        const groups = entry.groups.map(group => ({ ...group, items: group.items.filter(item => active === 'all' || item.types.includes(active)) })).filter(group => group.items.length)
        if (!groups.length) continue
        const month = entry.date.slice(0, 7)
        if (!sections.has(month)) {
          const label = `${Number(month.slice(0, 4))} 年 ${Number(month.slice(5))} 月`
          const section = element('section', '', 'changelog-month')
          section.id = `month-${month}`
          section.setAttribute('aria-labelledby', `m-${month}`)
          const heading = element('h2', label)
          heading.id = `m-${month}`
          const timeline = element('div', '', 'timeline')
          section.append(heading, timeline)
          container.append(section)
          const link = element('a', label)
          link.href = `#month-${month}`
          months.append(link)
          sections.set(month, timeline)
        }
        const article = element('article')
        const time = element('time', entry.date)
        time.dateTime = entry.date
        const body = element('div')
        body.append(element('h3', entry.title))
        for (const group of groups) {
          const list = element('ul')
          for (const item of group.items) {
            const li = element('li', item.text)
            li.dataset.type = item.types.join(' ')
            list.append(li)
            shown++
          }
          body.append(element('h4', group.title), list)
        }
        article.append(time, body)
        sections.get(month).append(article)
      }
      count.textContent = active === 'all' ? `共 ${shown} 条更新` : `${types[active]}：${shown} 条更新`
      // Initial fragments must be applied after asynchronous content is rendered.
      const anchor = document.getElementById(location.hash.slice(1))
      if (anchor) anchor.scrollIntoView()
    } catch (error) {
      count.textContent = '更新日志加载失败，请重试。'
      retry.hidden = false
    }
  }
  retry.addEventListener('click', load)
  load()
})()
