(async function () {
  const articleId = new URLSearchParams(location.search).get('id')
  const hero = document.querySelector('#article-hero')
  const body = document.querySelector('#article-body')
  const favoriteButton = document.querySelector('#favorite-button')
  let article = null
  let isFavorite = false

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[char]))
  }

  function safeUrl(value) {
    try {
      const url = new URL(value)
      return ['http:', 'https:'].includes(url.protocol) ? url.href : ''
    } catch {
      return ''
    }
  }

  function paragraphs(value) {
    return String(value || '').split(/\n+/).filter(Boolean).map(text => `<p>${escapeHtml(text)}</p>`).join('')
  }

  function renderSummary(items) {
    const values = Array.isArray(items) ? items.slice(0, 3) : []
    if (!values.length) return ''
    return `<section class="article-card summary-card">
      <div class="module-head"><h2>先看这三点</h2><span class="module-note">快速建立判断框架</span></div>
      <ol class="summary-list">${values.map((item, index) => `<li class="summary-item"><span class="summary-index">${String(index + 1).padStart(2, '0')}</span><span class="summary-text">${escapeHtml(item)}</span></li>`).join('')}</ol>
    </section>`
  }

  function renderInsights(value) {
    const impacts = String(value || '普通用户 / 相关从业者').split('/').map(item => item.trim()).filter(Boolean)
    const timeline = ['先读摘要', '理解背景', '核对来源', '继续追问']
    return `<div class="insight-grid">
      <section class="article-card"><div class="module-head"><h2>影响范围</h2></div><div class="impact-tags">${impacts.map(item => `<span class="impact-tag">${escapeHtml(item)}</span>`).join('')}</div></section>
      <section class="article-card"><div class="module-head"><h2>阅读路线</h2></div><ol class="article-timeline">${timeline.map((item, index) => `<li class="timeline-step"><span class="timeline-marker">${index + 1}</span><span>${item}</span></li>`).join('')}</ol></section>
    </div>`
  }

  function renderSections(sections, fallbackContent) {
    const values = Array.isArray(sections) ? sections : []
    const content = values.map(section => `<section class="article-section"><h2>${escapeHtml(section.heading || section.title || '')}</h2>${paragraphs(section.body || section.content || '')}</section>`).join('')
    return `<section class="article-card article-content">${content || `<section class="article-section">${paragraphs(fallbackContent || '暂无正文内容。')}</section>`}</section>`
  }

  function renderAsk() {
    const questions = ['这和我有什么关系？', '能不能讲得更简单？', '依据在哪里？']
    return `<section class="article-card ask-card">
      <div class="module-head"><div><h2>文章内 AI 助手</h2><span class="module-note">围绕这篇文章继续追问</span></div><strong>AI</strong></div>
      <div class="quick-questions">${questions.map(question => `<button class="question-chip" type="button" data-question="${escapeHtml(question)}">${escapeHtml(question)}</button>`).join('')}</div>
      <form class="ask-form" id="article-ask-form"><input id="article-question" autocomplete="off" placeholder="问问这件事" aria-label="围绕文章提问"><button class="button button-primary" type="submit">发送 →</button></form>
    </section>`
  }

  function renderReferences(references) {
    const values = Array.isArray(references) ? references : []
    if (!values.length) return ''
    return `<section class="article-card"><div class="module-head"><h2>来源与依据</h2><span class="module-note">具体办理以官方信息为准</span></div><ul class="reference-list">${values.map(reference => {
      if (typeof reference === 'string') return `<li class="reference-item"><div><h3>${escapeHtml(reference)}</h3></div></li>`
      const url = safeUrl(reference.url)
      return `<li class="reference-item"><div><h3>${escapeHtml(reference.title || reference.name || '参考资料')}</h3><p>${escapeHtml([reference.org, reference.date].filter(Boolean).join(' · '))}</p></div>${url ? `<a class="reference-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">查看来源 →</a>` : ''}</li>`
    }).join('')}</ul></section>`
  }

  function goAsk(question) {
    const query = new URLSearchParams({ article: articleId })
    if (question) query.set('q', question)
    location.href = `ask.html?${query.toString()}`
  }

  function bindArticleActions() {
    document.querySelectorAll('[data-question]').forEach(button => {
      button.addEventListener('click', () => goAsk(button.dataset.question || ''))
    })
    document.querySelector('#article-ask-form').addEventListener('submit', event => {
      event.preventDefault()
      goAsk(document.querySelector('#article-question').value.trim())
    })
  }

  function updateFavoriteButton() {
    favoriteButton.classList.toggle('active', isFavorite)
    favoriteButton.querySelector('.favorite-icon').textContent = isFavorite ? '★' : '☆'
    favoriteButton.querySelector('[data-label]').textContent = isFavorite ? '已收藏' : '收藏'
  }

  async function loadFavorite() {
    if (!window.getToken()) return
    favoriteButton.hidden = false
    try {
      isFavorite = Boolean(await window.jianwenApi.favorite(articleId))
      updateFavoriteButton()
    } catch {
      favoriteButton.hidden = true
    }
  }

  favoriteButton.addEventListener('click', async () => {
    if (!window.getToken()) {
      location.href = `login.html?next=${encodeURIComponent(location.pathname + location.search)}`
      return
    }
    favoriteButton.disabled = true
    try {
      if (isFavorite) await window.jianwenApi.deleteFavorite(articleId)
      else await window.jianwenApi.saveFavorite(articleId, article)
      isFavorite = !isFavorite
      updateFavoriteButton()
    } catch (error) {
      alert(error.message)
    } finally {
      favoriteButton.disabled = false
    }
  })

  if (!articleId) {
    hero.innerHTML = '<p class="eyebrow">JIANWEN / ARTICLE</p><h1>缺少文章编号</h1><p class="article-deck">请从今日列表选择一篇文章阅读。</p>'
    body.innerHTML = '<strong>无法定位文章</strong><span>返回今日页重新选择。</span>'
    return
  }

  try {
    article = await window.jianwenApi.article(articleId)
    const topic = article.topic || article.category || '见闻'
    const source = article.sources || article.source || '见闻整理'
    const readTime = article.read_time || article.readTime || '约 5 分钟'

    document.title = `${article.title} · 见闻`
    hero.innerHTML = `<div class="article-topline"><span class="article-topic">${escapeHtml(topic)}</span><span class="article-kicker">深度解读报告</span></div><h1>${escapeHtml(article.title || '未命名文章')}</h1><p class="article-deck">${escapeHtml(article.desc || '阅读背景、影响与来源依据。')}</p><div class="article-meta"><span>${escapeHtml(readTime)} · AI 辅助整理</span><span>${escapeHtml(source)}</span></div>`
    body.className = 'article-stack'
    body.innerHTML = `${renderSummary(article.summary)}${renderInsights(article.relation)}${renderSections(article.sections, article.content)}${renderAsk()}${renderReferences(article.references)}<div class="article-actions"><a class="button button-secondary" href="index.html">返回今日</a><a class="button button-primary" href="ask.html?article=${encodeURIComponent(articleId)}">继续追问</a></div>`
    bindArticleActions()

    const related = document.createElement('section')
    related.className = 'article-card'
    related.innerHTML = '<h2>沿着主题，继续阅读</h2><p role="status">正在寻找相关文章…</p>'
    body.append(related)
    window.jianwenApi.relatedArticles(articleId).then(items => {
      if (!items.length) { related.remove(); return }
      related.innerHTML = `<h2>沿着主题，继续阅读</h2><div class="related-grid">${items.map(item => `<a class="related-card" href="article.html?id=${encodeURIComponent(item.article_id)}"><span class="eyebrow">${escapeHtml(item.topic || item.category || '见闻')}</span><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.desc || '')}</p><span class="text-link">继续阅读 ↗</span></a>`).join('')}</div>`
    }).catch(() => { related.innerHTML = '<h2>继续探索</h2><p>相关推荐暂时不可用。</p><a class="text-link" href="discover.html">前往发现页 →</a>' })

    window.markArticleRead(articleId)
    if (window.getToken()) window.jianwenApi.saveHistory(articleId, article).catch(() => {})
    loadFavorite()
  } catch (error) {
    hero.innerHTML = '<p class="eyebrow">JIANWEN / ARTICLE</p><h1>文章暂时不可用</h1><p class="article-deck">后端未返回这篇文章。</p>'
    body.innerHTML = `<strong>加载失败</strong><span>${escapeHtml(error.message)}</span>`
  }
})()
