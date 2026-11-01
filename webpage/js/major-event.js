// 大事报道：首页置顶卡片。数据来自 /api/v1/content/breaking-news，默认配图为共产党图。
;(function () {
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
  // 只放行官方来源的 https 链接，其他一律不渲染链接。
  const HOSTS = ['gov.cn', 'news.cn', 'xinhuanet.com', 'people.com.cn', 'people.cn']
  function safeUrl(value) {
    try {
      const url = new URL(String(value || ''))
      const ok = url.protocol === 'https:' && HOSTS.some(h => url.hostname === h || url.hostname.endsWith('.' + h))
      return ok ? url.href : ''
    } catch { return '' }
  }
  // 与文章列表共用后端压缩封面。
  function imageUrl(value) {
    const name = String(value || '/static/images/共产党.jpg').split('/').pop()
    return window.jianwenApi.baseUrl() + '/static/images/' + encodeURIComponent(name)
  }
  function dateRange(item) {
    if (item.start_date && item.end_date && item.start_date !== item.end_date) return `${item.start_date} 至 ${item.end_date}`
    return item.start_date || item.end_date || ''
  }
  function render(root, item) {
    const href = safeUrl(item.source_url)
    const closed = item.status === '已闭幕'
    const tag = href ? 'a' : 'div'
    const attrs = href ? ` href="${esc(href)}" target="_blank" rel="noopener noreferrer"` : ''
    const badge = `<span class="major-event-badge${closed ? ' is-closed' : ''}">${closed ? '已闭幕' : '进行中'}</span>`
    const head = `<p class="major-event-eyebrow">大事报道 ${badge}</p>`
    const meta = `<p class="major-event-meta">${esc(dateRange(item))} · ${esc(item.source_name)}</p>`
    const img = `<img class="major-event-image" src="${esc(imageUrl(item.image))}" alt="" loading="eager">`
    const body = `<div class="major-event-body">${head}<h2>${esc(item.event_name || item.title)}</h2><p class="major-event-summary">${esc(item.summary)}</p>${meta}</div>`
    root.innerHTML = `<${tag} class="major-event-card"${attrs}>${img}${body}</${tag}>`
    root.hidden = false
  }
  async function load() {
    const root = document.getElementById('major-event')
    if (!root || !window.jianwenApi || !window.jianwenApi.majorEvents) return
    try {
      const items = await window.jianwenApi.majorEvents()
      if (Array.isArray(items) && items.length) render(root, items[0])
    } catch (error) {
      // 拉取失败就不显示，不影响首页其他内容。
      root.hidden = true
    }
  }
  load()
})()
