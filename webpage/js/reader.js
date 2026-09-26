(function () {
  'use strict'
  const $ = id => document.getElementById(id)
  const api = window.jianwenApi
  const params = new URLSearchParams(location.search)
  const bookId = params.get('book') || params.get('id') || ''
  const positionKey = `jianwen_web_reader_${encodeURIComponent(bookId)}`
  let book = null
  let activeIndex = -1
  let requestVersion = 0
  let ready = false
  let restoring = false
  let scrollTimer
  let syncTimer
  let syncPending = null
  let syncRunning = false
  let lastSynced = ''
  const cache = new Map()

  function readStorage(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback } catch { return fallback }
  }
  function writeStorage(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true } catch { return false }
  }
  function safeUrl(value) {
    try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : '' } catch { return '' }
  }
  function hint(message, retry) {
    const text = document.createElement('p')
    text.className = 'reader-hint'
    text.setAttribute('role', 'status')
    text.textContent = message
    $('reader-content').replaceChildren(text)
    if (retry) {
      const button = document.createElement('button')
      button.type = 'button'
      button.textContent = '重新加载'
      button.addEventListener('click', retry)
      $('reader-content').append(button)
    }
  }
  let fontSize = Math.min(28, Math.max(16, Number(readStorage('jianwen_web_reader_font', 20)) || 20))
  function applyFont() {
    document.documentElement.style.setProperty('--reader-font-size', `${fontSize}px`)
    $('font-value').textContent = `${fontSize} px`
    $('font-smaller').disabled = fontSize <= 16
    $('font-larger').disabled = fontSize >= 28
    writeStorage('jianwen_web_reader_font', fontSize)
  }
  function progress() {
    const content = $('reader-content')
    const top = content.getBoundingClientRect().top + window.scrollY
    const distance = Math.max(1, content.offsetHeight - window.innerHeight + 150)
    return Math.min(1, Math.max(0, (window.scrollY - top + 100) / distance))
  }
  function canSync() { return typeof api.saveReadingProgress === 'function' && typeof window.getToken === 'function' && !!window.getToken() }
  async function flushSync() {
    if (syncRunning || !syncPending || !canSync()) return
    const value = syncPending
    syncPending = null
    syncRunning = true
    const key = JSON.stringify(value)
    try {
      await api.saveReadingProgress(bookId, value)
      lastSynced = key
      if (!syncPending) $('save-state').textContent = '阅读位置已同步至账号'
    } catch {
      $('save-state').textContent = '已保存到此设备，账号同步暂不可用'
    } finally {
      syncRunning = false
      if (syncPending) flushSync()
    }
  }
  function savePosition() {
    if (!ready || restoring || !book || activeIndex < 0) return
    const fraction = progress()
    const value = { bookId, chapterId: book.chapters[activeIndex].id, chapterTitle: book.chapters[activeIndex].title, fraction, updatedAt: Date.now() }
    const saved = writeStorage(positionKey, value)
    $('save-state').textContent = saved ? '已在此设备保存阅读位置' : '浏览器未允许保存阅读位置'
    $('chapter-progress').textContent = `本章 ${Math.round(fraction * 100)}%`
    if (canSync()) {
      const payload = { chapter_id: value.chapterId, scroll_progress: Math.round(fraction * 1000) / 1000 }
      if (JSON.stringify(payload) !== lastSynced) {
        syncPending = payload
        clearTimeout(syncTimer)
        syncTimer = setTimeout(flushSync, 1200)
      }
    }
  }
  function renderToc() {
    const query = $('chapter-search').value.trim().toLocaleLowerCase()
    const fragment = document.createDocumentFragment()
    book.chapters.forEach((chapter, index) => {
      if (query && !chapter.title.toLocaleLowerCase().includes(query)) return
      const button = document.createElement('button')
      button.type = 'button'
      button.textContent = chapter.title
      if (index === activeIndex) button.setAttribute('aria-current', 'true')
      button.addEventListener('click', () => openChapter(index))
      fragment.append(button)
    })
    if (!fragment.childNodes.length) {
      const empty = document.createElement('p')
      empty.className = 'reader-hint'
      empty.textContent = query ? '没有匹配的章节。' : '本书暂未提供章节。'
      fragment.append(empty)
    }
    $('chapter-list').replaceChildren(fragment)
  }
  async function openChapter(index, savedPosition) {
    if (!book || index < 0 || index >= book.chapters.length) return
    savePosition()
    ready = false
    const version = ++requestVersion
    activeIndex = index
    const chapter = book.chapters[index]
    $('chapter-title').textContent = chapter.title
    $('chapter-number').textContent = `第 ${index + 1} / ${book.chapters.length} 章`
    $('chapter-progress').textContent = ''
    $('previous-chapter').disabled = index === 0
    $('next-chapter').disabled = index === book.chapters.length - 1
    $('reader-content').setAttribute('aria-busy', 'true')
    renderToc()
    hint('正在加载本章原文…')
    const url = new URL(location.href)
    url.searchParams.set('book', bookId)
    url.searchParams.set('chapter', chapter.id)
    history.replaceState(null, '', url)
    try {
      const detail = cache.get(chapter.id) || await api.classicChapter(bookId, chapter.id)
      if (version !== requestVersion) return
      cache.set(chapter.id, detail)
      if (!detail.content || !detail.content.trim()) {
        hint(detail.summary ? `本章暂无完整正文。\n${detail.summary}` : '本章暂无完整正文，可查看原始出处或选择其他章节。')
        const sourceUrl = safeUrl(detail.external_url || book.external_url)
        if (sourceUrl) {
          const source = document.createElement('a')
          source.href = sourceUrl
          source.target = '_blank'
          source.rel = 'noopener noreferrer'
          source.className = 'text-link'
          source.textContent = '查看原始出处 ↗'
          $('reader-content').append(source)
        }
      } else {
        const fragment = document.createDocumentFragment()
        detail.content.trim().split(/\r?\n+/).forEach(line => {
          const paragraph = document.createElement('p')
          paragraph.textContent = line.trim()
          fragment.append(paragraph)
        })
        $('reader-content').replaceChildren(fragment)
      }
      ready = true
      restoring = true
      requestAnimationFrame(() => {
        if (version !== requestVersion) return
        const fraction = Math.min(1, Math.max(0, Number(savedPosition?.fraction) || 0))
        const content = $('reader-content')
        const target = savedPosition ? content.getBoundingClientRect().top + window.scrollY - 100 + fraction * Math.max(1, content.offsetHeight - window.innerHeight + 150) : $('chapter-title').getBoundingClientRect().top + window.scrollY - 110
        window.scrollTo({ top: Math.max(0, target), behavior: 'instant' })
        if (!savedPosition) $('chapter-title').focus({ preventScroll: true })
        requestAnimationFrame(() => {
          if (version !== requestVersion) return
          restoring = false
          savePosition()
        })
      })
    } catch (error) {
      if (version !== requestVersion) return
      restoring = false
      hint(`本章加载失败：${error.message || '请稍后重试'}`, () => openChapter(index, savedPosition))
    } finally {
      if (version === requestVersion) $('reader-content').setAttribute('aria-busy', 'false')
    }
  }
  async function loadBook() {
    if (!bookId) {
      $('book-meta').textContent = '请从原典书架选择一本书。'
      $('chapter-title').textContent = '还没有选择书籍'
      $('chapter-list').textContent = ''
      $('reader-content').setAttribute('aria-busy', 'false')
      hint('点击上方“返回原典书架”即可开始阅读。')
      return
    }
    try {
      book = await api.classicBook(bookId)
      book.chapters = Array.isArray(book.chapters) ? book.chapters : []
      document.title = `${book.title} · 见闻阅读室`
      $('book-title').textContent = book.title
      $('book-meta').textContent = [book.author, book.source_org, book.description].filter(Boolean).join(' · ')
      const source = safeUrl(book.external_url)
      if (source) { $('book-source').href = source; $('book-source').hidden = false }
      $('chapter-count').textContent = `${book.chapters.length} 章`
      renderToc()
      let saved = readStorage(positionKey, null)
      const initialVersion = requestVersion
      if (canSync() && typeof api.readingProgress === 'function') {
        let timeout
        try {
          const remote = await Promise.race([api.readingProgress(bookId), new Promise(resolve => { timeout = setTimeout(() => resolve(null), 2500) })])
          const remoteTime = remote?.updated_at ? Date.parse(/Z$|[+-]\d{2}:\d{2}$/.test(remote.updated_at) ? remote.updated_at : `${remote.updated_at}Z`) : 0
          if (remote && (!saved || remoteTime > (Number(saved.updatedAt) || 0))) saved = { chapterId: remote.chapter_id, fraction: remote.scroll_progress, updatedAt: remoteTime }
        } catch { /* Reading remains available when account sync is unavailable. */ }
        finally { clearTimeout(timeout) }
      }
      if (requestVersion !== initialVersion) return
      const requestedId = params.get('chapter') || saved?.chapterId
      const found = book.chapters.findIndex(chapter => String(chapter.id) === String(requestedId))
      const index = found >= 0 ? found : 0
      if (book.chapters.length) await openChapter(index, saved && String(saved.chapterId) === String(book.chapters[index].id) ? saved : null)
      else {
        $('chapter-title').textContent = '章节正在整理'
        hint('本书尚未提供在线章节，您可以先查看上方的原始出处。')
        $('reader-content').setAttribute('aria-busy', 'false')
      }
    } catch (error) {
      $('book-meta').textContent = '书籍暂时无法打开'
      $('chapter-title').textContent = '加载遇到问题'
      $('chapter-list').textContent = '目录暂时无法加载'
      $('reader-content').setAttribute('aria-busy', 'false')
      hint(error.message || '请检查网络后重试。', loadBook)
    }
  }
  $('previous-chapter').addEventListener('click', () => openChapter(activeIndex - 1))
  $('next-chapter').addEventListener('click', () => openChapter(activeIndex + 1))
  $('chapter-search').addEventListener('input', () => { if (book) renderToc() })
  $('font-smaller').addEventListener('click', () => { fontSize = Math.max(16, fontSize - 2); applyFont() })
  $('font-larger').addEventListener('click', () => { fontSize = Math.min(28, fontSize + 2); applyFont() })
  $('toc-toggle').addEventListener('click', () => {
    if (document.body.classList.contains('is-focused')) {
      document.body.classList.remove('is-focused')
      $('focus-toggle').setAttribute('aria-pressed', 'false')
      $('focus-toggle').textContent = '专注阅读'
      document.body.classList.remove('toc-hidden')
    } else document.body.classList.toggle('toc-hidden')
    const visible = !document.body.classList.contains('toc-hidden')
    $('toc-toggle').setAttribute('aria-expanded', String(visible))
    $('toc-toggle').textContent = visible ? '收起目录' : '展开目录'
  })
  $('focus-toggle').addEventListener('click', () => {
    const enabled = document.body.classList.toggle('is-focused')
    $('focus-toggle').setAttribute('aria-pressed', String(enabled))
    $('focus-toggle').textContent = enabled ? '退出专注' : '专注阅读'
    const visible = !enabled && !document.body.classList.contains('toc-hidden')
    $('toc-toggle').setAttribute('aria-expanded', String(visible))
    $('toc-toggle').textContent = visible ? '收起目录' : '展开目录'
  })
  window.addEventListener('scroll', () => { clearTimeout(scrollTimer); scrollTimer = setTimeout(savePosition, 180) }, { passive: true })
  window.addEventListener('pagehide', () => { savePosition(); flushSync() })
  document.addEventListener('visibilitychange', () => { if (document.hidden) { savePosition(); flushSync() } })
  applyFont()
  loadBook()
})()
