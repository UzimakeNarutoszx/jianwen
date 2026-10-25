(() => {
  const spot = document.querySelector('#breaking-news-spot')
  if (!spot) return
  const inToday = document.body.dataset.page === 'jianwen-index'
  const root = inToday ? '../' : ''
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[char]))
  async function refresh() {
    try {
      const items = await window.jianwenApi.breakingNews()
      const item = Array.isArray(items) ? items[0] : null
      if (!item) { spot.hidden = true; spot.replaceChildren(); return }
      const href = (inToday ? '' : 'jianwen/') + 'breaking-news.html?key=' + encodeURIComponent(item.event_key)
      spot.innerHTML = '<a class="breaking-news-card" href="' + href + '"><img src="' + root + 'asset/images/共产党.png" alt=""><span class="breaking-news-copy"><span class="breaking-news-label">大事报道</span><strong>' + esc(item.title) + '</strong><span>' + esc(item.summary) + '</span></span><span class="breaking-news-arrow" aria-hidden="true">↗</span></a>'
      spot.hidden = false
    } catch { spot.hidden = true; spot.replaceChildren() }
  }
  refresh()
  addEventListener('pageshow', refresh)
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh() })
  setInterval(() => { if (!document.hidden) refresh() }, 300000)
})()

