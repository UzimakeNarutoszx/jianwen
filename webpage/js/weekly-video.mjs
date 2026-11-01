import { selectEpisodes, mediaUrl, timestamp } from './weekly-video-model.mjs?v=20261101-media2'

const feature = document.querySelector('#episode')
const archive = document.querySelector('#archive-list')
const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character])
const dateLabel = value => new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric' }).format(new Date(value))
const safeUrl = value => escape(mediaUrl(value))
let catalog

function render() {
  const requested = new URLSearchParams(location.search).get('episode')
  const { pinned, selected, archive: previous, label, unknownId } = selectEpisodes(catalog, requested)
  const episode = selected || catalog.upcoming
  document.querySelector('#archive-count').textContent = previous.length ? `${previous.length} 期` : ''
  if (!episode) {
    feature.innerHTML = '<p class="weekly-notice" role="status">首期正在筹备，发布后将在这里展示。</p>'
  } else {
    const chapters = selected?.chapters || []
    feature.innerHTML = `${unknownId ? '<p class="weekly-notice" role="status">没有找到这期节目，已展示最近可用的节目。</p>' : ''}
      <div class="weekly-heading"><span class="weekly-badge">${selected ? label : '首期制作中'}</span><p>第 ${escape(episode.number)} 期 · ${escape(episode.weekStart)} — ${escape(episode.weekEnd)}</p></div>
      <div class="weekly-layout">
        <div class="weekly-media">
          <img src="${safeUrl(episode.poster)}" alt="${escape(episode.title)}的节目封面">
          ${selected ? `<video controls playsinline preload="none" poster="${safeUrl(episode.poster)}" aria-label="第 ${escape(episode.number)} 期：${escape(episode.title)}"><source src="${safeUrl(episode.video)}" type="video/mp4">${mediaUrl(episode.captions) ? `<track kind="captions" src="${safeUrl(episode.captions)}" srclang="zh" label="中文字幕">` : ''}</video>` : ''}
          <div class="weekly-media-fallback" ${selected ? 'hidden' : ''} role="status"><strong>${selected ? '视频暂时无法播放' : '这一周，正在成片。'}</strong><p>${selected ? '请稍后刷新重试，也可以先查看下方文章与来源。' : '重点文章 · 见闻更新 · 大事总结'}</p></div>
        </div>
        <div class="weekly-copy"><h2 tabindex="-1">${escape(episode.title)}</h2><p>${escape(episode.description)}</p>
          <p class="weekly-meta">采编截至 ${escape(dateLabel(episode.cutoff))}${selected ? ` · ${escape(timestamp(episode.durationSeconds))} · 中文旁白` : ' · 完成后公开发布'}</p>
          ${selected ? `<div class="weekly-chapters" aria-label="按章节播放">${chapters.map(chapter => `<button type="button" data-seek="${Number(chapter.seconds)}"><span>${escape(chapter.title)}</span><time>${timestamp(chapter.seconds)}</time></button>`).join('')}</div>` : '<ul class="weekly-outline"><li>本周重点文章<span>养老收费怎么看，中国制造往哪走</span></li><li>本周见闻更新<span>只记录已经公开的变化</span></li><li>大事总结<span>进出口与秋粮收获的本周观察</span></li></ul>'}
          ${selected && pinned && selected.id !== pinned.id ? `<a class="button button-secondary" href="?episode=${encodeURIComponent(pinned.id)}#episode">返回${pinned.weekStart === selected.weekStart ? '最新节目' : '置顶节目'}</a>` : ''}
        </div>
      </div>
      ${selected ? `<details class="weekly-references"><summary>延伸阅读与事实来源</summary><ul>${(episode.articles || []).concat(episode.sources || []).map(source => `<li><a href="${safeUrl(source.url)}">${escape(source.title)}</a>${source.date ? ` · ${escape(source.date)}` : ''}</li>`).join('')}</ul></details>` : ''}`
    const video = feature.querySelector('video')
    if (video) {
      let pendingSeek = null
      video.addEventListener('loadedmetadata', () => {
        if (pendingSeek !== null) { video.currentTime = Math.min(pendingSeek, video.duration); pendingSeek = null }
      })
      const playbackFailed = () => {
        video.hidden = true
        feature.querySelector('.weekly-media-fallback').hidden = false
        feature.querySelectorAll('[data-seek]').forEach(button => { button.disabled = true })
      }
      video.addEventListener('error', playbackFailed)
      video.querySelector('source').addEventListener('error', playbackFailed)
      feature.querySelectorAll('[data-seek]').forEach(button => button.addEventListener('click', () => {
        const seconds = Number(button.dataset.seek)
        if (!video.readyState) { pendingSeek = seconds; video.load() } else video.currentTime = Math.min(seconds, video.duration)
        video.play().catch(() => { /* Native controls remain available if playback needs another gesture. */ })
      }))
    }
  }
  feature.setAttribute('aria-busy', 'false')
  archive.innerHTML = previous.length ? previous.map(item => `<article class="weekly-archive-item"><a href="?episode=${encodeURIComponent(item.id)}#episode" tabindex="-1" aria-hidden="true"><img src="${safeUrl(item.poster)}" alt="" loading="lazy"></a><a href="?episode=${encodeURIComponent(item.id)}#episode" ${selected?.id === item.id ? 'aria-current="true"' : ''}><p>第 ${escape(item.number)} 期 · ${escape(item.weekStart)} — ${escape(item.weekEnd)}</p><h3>${escape(item.title)}</h3><p>${escape(timestamp(item.durationSeconds))} · ${escape(dateLabel(item.publishedAt))}发布</p></a><span aria-hidden="true">观看</span></article>`).join('') : '<p class="weekly-notice">还没有往期节目。每一期发布后，都会留在这里。</p>'
}

document.querySelector('main').addEventListener('click', event => {
  const link = event.target.closest('a[href^="?episode="]')
  if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  history.pushState(null, '', link.href)
  feature.querySelector('video')?.pause()
  render()
  feature.querySelector('h2')?.focus({ preventScroll: true })
  feature.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
})
window.addEventListener('popstate', () => { if (catalog) { feature.querySelector('video')?.pause(); render() } })

try {
  const response = await fetch('data/weekly-videos.json', { cache: 'no-store' })
  if (!response.ok) throw new Error('catalog unavailable')
  catalog = await response.json()
  render()
} catch {
  feature.setAttribute('aria-busy', 'false')
  feature.innerHTML = '<p class="weekly-notice" role="status">节目列表暂时无法载入，请稍后刷新重试。</p>'
}
