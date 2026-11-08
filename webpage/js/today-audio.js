// 今日朗读：网站版播放器。纯逻辑在文件上半部分（Node 里可直接 require 做测试），
// 下半部分才碰 DOM。数据约定见 docs/today-audio-contract.md。
;(function () {
  'use strict'

  const VOICE_STORAGE_KEY = 'jianwen_tts_voice'
  const PENDING_TEXT = '今日朗读生成中'
  const DEFAULT_VOICES = [
    { id: 'jianwen', label: '见闻' },
    { id: 'dylan', label: '男声·京味' }
  ]

  function normalizeVoices(voices) {
    const list = (Array.isArray(voices) ? voices : [])
      .filter(item => item && typeof item.id === 'string' && item.id)
      .map(item => ({ id: item.id, label: String(item.label || item.id) }))
    return list.length ? list : DEFAULT_VOICES.map(item => ({ id: item.id, label: item.label }))
  }

  function normalizeAudio(audio) {
    const result = {}
    if (!audio || typeof audio !== 'object' || Array.isArray(audio)) return result
    for (const id of Object.keys(audio)) {
      const value = audio[id]
      if (!value || typeof value.url !== 'string' || !value.url) continue
      const duration = Number(value.duration)
      result[id] = { url: value.url, duration: Number.isFinite(duration) && duration > 0 ? Math.round(duration * 10) / 10 : 0 }
    }
    return result
  }

  function normalizeArticles(articles) {
    return (Array.isArray(articles) ? articles : [])
      .filter(item => item && item.article_id !== undefined && item.article_id !== null && item.article_id !== '')
      .map((item, position) => ({
        articleId: String(item.article_id),
        title: String(item.title || ''),
        position: Number.isFinite(Number(item.position)) ? Number(item.position) : position,
        audio: normalizeAudio(item.audio)
      }))
  }

  // 后端总会带 ready；直接喂原始 manifest（没有 ready 字段）时按有无文章判断。
  function normalizeManifest(raw) {
    const record = raw && typeof raw === 'object' ? raw : {}
    const articles = normalizeArticles(record.articles)
    const ready = record.ready === true ? true : record.ready === false ? false : articles.length > 0
    return {
      ready,
      date: String(record.date || ''),
      generatedAt: String(record.generated_at || ''),
      voices: normalizeVoices(record.voices),
      articles: ready ? articles : []
    }
  }

  function resolveVoice(state, index, preferred) {
    const article = state.articles[index]
    const available = article ? state.voices.filter(voice => Boolean(article.audio[voice.id])) : []
    if (!available.length) return state.voices.length ? state.voices[0].id : ''
    if (preferred && available.some(voice => voice.id === preferred)) return preferred
    return available[0].id
  }

  function createTodayAudioState(raw, savedVoice) {
    const manifest = normalizeManifest(raw)
    const state = Object.assign({}, manifest, { index: 0, voice: '', loading: false })
    state.voice = resolveVoice(state, 0, savedVoice || '')
    return state
  }

  function withLoading(state, loading) {
    return Object.assign({}, state, { loading: Boolean(loading) })
  }

  function setIndex(state, index) {
    const last = state.articles.length - 1
    if (last < 0) return state
    const value = Number(index)
    const next = Math.min(Math.max(Number.isFinite(value) ? Math.round(value) : 0, 0), last)
    if (next === state.index) return state
    return Object.assign({}, state, { index: next, voice: resolveVoice(state, next, state.voice) })
  }

  function step(state, delta) {
    return setIndex(state, state.index + (Number(delta) || 0))
  }

  function canPrev(state) {
    return state.ready === true && state.articles.length > 0 && state.index > 0
  }

  function canNext(state) {
    return state.ready === true && state.index < state.articles.length - 1
  }

  function selectVoice(state, voiceId) {
    const voice = resolveVoice(state, state.index, voiceId)
    return voice === state.voice ? state : Object.assign({}, state, { voice })
  }

  function currentTrack(state) {
    if (state.ready !== true) return null
    const article = state.articles[state.index]
    if (!article) return null
    const audio = article.audio[state.voice] || null
    return {
      articleId: article.articleId,
      title: article.title,
      index: state.index,
      total: state.articles.length,
      voice: state.voice,
      url: audio ? audio.url : '',
      duration: audio ? audio.duration : 0
    }
  }

  function hasTrack(state) {
    const track = currentTrack(state)
    return Boolean(track && track.url)
  }

  function voiceOptions(state) {
    const article = state.articles[state.index]
    return state.voices.map(voice => ({
      id: voice.id,
      label: voice.label,
      available: Boolean(article && article.audio[voice.id]),
      active: voice.id === state.voice
    }))
  }

  // 自动续播只发生在当日清单内；最后一篇播完就停在原地。
  function afterEnded(state) {
    if (!canNext(state)) return { state, play: false, finished: true }
    return { state: step(state, 1), play: true, finished: false }
  }

  function formatTime(seconds) {
    const value = Number(seconds)
    if (!Number.isFinite(value) || value <= 0) return '0:00'
    const total = Math.floor(value)
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
  }

  function progressRatio(current, duration) {
    const total = Number(duration)
    const value = Number(current)
    if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(value) || value <= 0) return 0
    return Math.min(Math.max(value / total, 0), 1)
  }

  function ratioToSeconds(ratio, duration) {
    const total = Number(duration)
    const value = Number(ratio)
    if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(value) || value <= 0) return 0
    return Math.min(Math.max(value, 0), 1) * total
  }

  function statusLabel(state) {
    if (state.loading) return '正在读取今日朗读'
    if (state.ready !== true) return PENDING_TEXT
    if (!state.articles.length) return '今日暂无可朗读的文章'
    const article = state.articles[state.index]
    return article && Object.keys(article.audio).length ? '' : '这篇暂无可播放音频'
  }


  // 「听完即读完」：只累计真实播放推进的比例（拖动跳过的不算），按比例记录，换声音不清零。
  // 累计到 LISTEN_DONE_RATIO 即视为这篇已读；每篇只触发一次。
  const LISTEN_DONE_RATIO = 0.9
  function createListenTracker() {
    return { heard: {}, last: null, done: {} }
  }
  // 每次 timeupdate 调用；delta 只在 0~2 秒内才计入，超出视为拖动或换源。返回 true 表示这次刚好听完。
  function trackListen(tracker, articleId, current, duration) {
    const total = Number(duration)
    const now = Number(current)
    if (!articleId || !Number.isFinite(total) || total <= 0 || !Number.isFinite(now)) return false
    const last = tracker.last
    if (last && last.id === articleId) {
      const delta = now - last.time
      if (delta > 0 && delta <= 2) tracker.heard[articleId] = Math.min(1, (tracker.heard[articleId] || 0) + delta / total)
    }
    tracker.last = { id: articleId, time: now }
    return markIfDone(tracker, articleId)
  }
  // 换篇、换声音、拖动后调用，下一次 timeupdate 不和旧位置做差。
  function resetListenAnchor(tracker) {
    tracker.last = null
  }
  // ended 时调用：尾部最后一次 timeupdate 到结束之间的空档补齐后再判断。
  function finishListen(tracker, articleId, duration) {
    const last = tracker.last
    if (last && last.id === articleId) return trackListen(tracker, articleId, Math.min(Number(duration), last.time + 2), duration)
    return markIfDone(tracker, articleId)
  }
  function markIfDone(tracker, articleId) {
    if (tracker.done[articleId] || (tracker.heard[articleId] || 0) < LISTEN_DONE_RATIO) return false
    tracker.done[articleId] = true
    return true
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      VOICE_STORAGE_KEY, PENDING_TEXT, DEFAULT_VOICES, normalizeManifest, resolveVoice, createTodayAudioState,
      withLoading, setIndex, step, canPrev, canNext, selectVoice, currentTrack, hasTrack, voiceOptions,
      afterEnded, formatTime, progressRatio, ratioToSeconds, statusLabel,
      LISTEN_DONE_RATIO, createListenTracker, trackListen, resetListenAnchor, finishListen
    }
    return
  }

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]))

  function readSavedVoice() {
    try { return localStorage.getItem(VOICE_STORAGE_KEY) || '' } catch { return '' }
  }
  function writeSavedVoice(voice) {
    try { localStorage.setItem(VOICE_STORAGE_KEY, voice) } catch {}
  }
  // url 是站内相对路径，用 API base 拼绝对地址。
  function absoluteUrl(path) {
    if (!path) return ''
    if (/^https?:\/\//i.test(path)) return path
    const base = window.jianwenApi && window.jianwenApi.baseUrl ? window.jianwenApi.baseUrl() : ''
    return `${String(base).replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`
  }

  const SKELETON = `<div class="ta-head"><p class="eyebrow ta-eyebrow">今日朗读</p><p class="ta-count"><span class="ta-position" data-el="position">0</span><span class="ta-total" data-el="total">/ 0 篇</span></p></div>
    <h3 class="ta-title" data-el="title"></h3>
    <p class="ta-status" data-el="status" role="status"></p>
    <div class="ta-voices" data-el="voices" role="group" aria-label="选择朗读声音"></div>
    <div class="ta-controls">
      <button class="ta-button ta-skip" type="button" data-act="prev" aria-label="上一篇"><span class="ta-icon" aria-hidden="true">‹</span><span class="ta-button-text">上一篇</span></button>
      <button class="ta-button ta-play" type="button" data-act="play" aria-label="播放"><span class="ta-icon" aria-hidden="true" data-el="play-icon">▶</span></button>
      <button class="ta-button ta-skip" type="button" data-act="next" aria-label="下一篇"><span class="ta-button-text">下一篇</span><span class="ta-icon" aria-hidden="true">›</span></button>
    </div>
    <div class="ta-track">
      <span class="ta-time" data-el="current">0:00</span>
      <input class="ta-range" type="range" min="0" max="1000" step="1" value="0" data-el="range" aria-label="播放进度" aria-valuetext="0:00 / 0:00">
      <span class="ta-time" data-el="duration">0:00</span>
    </div>
    <audio preload="metadata" data-el="audio"></audio>`

  function mount(root) {
    root.innerHTML = SKELETON
    const el = name => root.querySelector(`[data-el="${name}"]`)
    const parts = {
      position: el('position'), total: el('total'), title: el('title'), status: el('status'), voices: el('voices'),
      prev: root.querySelector('[data-act="prev"]'), play: root.querySelector('[data-act="play"]'),
      next: root.querySelector('[data-act="next"]'), playIcon: el('play-icon'),
      range: el('range'), current: el('current'), duration: el('duration')
    }
    let state = withLoading(createTodayAudioState({ ready: false, voices: DEFAULT_VOICES, articles: [] }, readSavedVoice()), true)
    let userSeeking = false
    const listen = createListenTracker()
    // 听完一篇：广播给页面，由页面按已读处理（和打开文章详情等价）。
    const announceListened = article => {
      root.dispatchEvent(new CustomEvent('today-audio:listened', { bubbles: true, detail: { articleId: article.articleId, title: article.title } }))
    }

    function audio() {
      return el('audio')
    }

    function renderVoices() {
      const options = voiceOptions(state)
      parts.voices.innerHTML = options.map(option => `<button class="ta-voice${option.active ? ' is-active' : ''}" type="button" role="radio" aria-checked="${option.active}" data-voice="${esc(option.id)}"${option.available ? '' : ' disabled aria-disabled="true" title="这篇没有这个声音"'}>${esc(option.label)}</button>`).join('')
      parts.voices.hidden = options.length <= 1
    }

    function render() {
      const track = currentTrack(state)
      const label = statusLabel(state)
      root.hidden = false
      root.dataset.ready = state.ready ? 'true' : 'false'
      parts.position.textContent = track ? String(track.index + 1) : '0'
      parts.total.textContent = `/ ${state.articles.length} 篇`
      parts.title.textContent = track ? track.title : ''
      parts.status.textContent = label
      parts.status.hidden = !label
      renderVoices()
      const playable = hasTrack(state) && !state.loading
      parts.prev.disabled = !canPrev(state) || state.loading
      parts.next.disabled = !canNext(state) || state.loading
      parts.play.disabled = !playable
      parts.range.disabled = !playable
      const playing = playable && !audio().paused
      parts.playIcon.textContent = playing ? '❚❚' : '▶'
      parts.play.setAttribute('aria-label', playing ? '暂停朗读' : '播放朗读')
      parts.play.setAttribute('aria-pressed', playing ? 'true' : 'false')
      if (!userSeeking) syncProgress()
    }

    function syncProgress() {
      const media = audio()
      const known = Number.isFinite(media.duration) && media.duration > 0 ? media.duration : (currentTrack(state) || {}).duration || 0
      const current = Number.isFinite(media.currentTime) ? media.currentTime : 0
      parts.current.textContent = formatTime(current)
      parts.duration.textContent = formatTime(known)
      parts.range.value = String(Math.round(progressRatio(current, known) * 1000))
      parts.range.setAttribute('aria-valuetext', `${formatTime(current)} / ${formatTime(known)}`)
    }

    function loadSource(keepRatio) {
      const media = audio()
      resetListenAnchor(listen)
      const track = currentTrack(state)
      const ratio = keepRatio ? progressRatio(media.currentTime, media.duration) : 0
      if (!track || !track.url) {
        media.removeAttribute('src')
        syncProgress()
        render()
        return
      }
      media.src = absoluteUrl(track.url)
      if (ratio > 0) {
        // 换声音时保留播放进度比例；元数据就绪后再定位。
        const seek = () => { try { media.currentTime = ratioToSeconds(ratio, media.duration) } catch {} }
        media.addEventListener('loadedmetadata', seek, { once: true })
      }
      syncProgress()
      render()
    }

    function play() {
      const media = audio()
      if (!hasTrack(state)) return
      const attempt = media.play()
      if (attempt && typeof attempt.catch === 'function') attempt.catch(() => { parts.status.textContent = '点一下播放按钮开始朗读'; parts.status.hidden = false })
    }

    parts.prev.addEventListener('click', () => {
      if (!canPrev(state)) return
      const wasPlaying = !audio().paused
      state = step(state, -1)
      loadSource(false)
      if (wasPlaying) play()
    })
    parts.next.addEventListener('click', () => {
      if (!canNext(state)) return
      const wasPlaying = !audio().paused
      state = step(state, 1)
      loadSource(false)
      if (wasPlaying) play()
    })
    parts.play.addEventListener('click', () => {
      const media = audio()
      if (media.paused) play()
      else media.pause()
    })
    parts.voices.addEventListener('click', event => {
      const button = event.target.closest('[data-voice]')
      if (!button || button.disabled) return
      const next = selectVoice(state, button.dataset.voice)
      if (next === state) return
      const wasPlaying = !audio().paused
      state = next
      writeSavedVoice(state.voice)
      loadSource(true)
      if (wasPlaying) play()
      render()
    })
    parts.range.addEventListener('pointerdown', () => { userSeeking = true })
    parts.range.addEventListener('input', () => {
      const media = audio()
      const known = Number.isFinite(media.duration) && media.duration > 0 ? media.duration : (currentTrack(state) || {}).duration || 0
      const seconds = ratioToSeconds(Number(parts.range.value) / 1000, known)
      parts.current.textContent = formatTime(seconds)
      parts.range.setAttribute('aria-valuetext', `${formatTime(seconds)} / ${formatTime(known)}`)
    })
    const commitSeek = () => {
      const media = audio()
      const known = Number.isFinite(media.duration) && media.duration > 0 ? media.duration : (currentTrack(state) || {}).duration || 0
      try { media.currentTime = ratioToSeconds(Number(parts.range.value) / 1000, known) } catch {}
      resetListenAnchor(listen)
      userSeeking = false
      syncProgress()
    }
    parts.range.addEventListener('change', commitSeek)
    parts.range.addEventListener('pointerup', commitSeek)

    const media = audio()
    const currentArticle = () => state.articles[state.index]
    media.addEventListener('timeupdate', () => {
      if (userSeeking) return
      syncProgress()
      const article = currentArticle()
      if (article && !media.paused && trackListen(listen, article.articleId, media.currentTime, media.duration)) announceListened(article)
    })
    media.addEventListener('seeking', () => resetListenAnchor(listen))
    media.addEventListener('durationchange', () => syncProgress())
    media.addEventListener('play', render)
    media.addEventListener('pause', render)
    media.addEventListener('ended', () => {
      // 一篇播完自动接下一篇，最后一篇播完就停。
      const article = currentArticle()
      if (article && finishListen(listen, article.articleId, media.duration)) announceListened(article)
      const result = afterEnded(state)
      if (!result.play) { render(); return }
      state = result.state
      loadSource(false)
      play()
    })

    const apply = raw => {
      state = withLoading(createTodayAudioState(raw, readSavedVoice()), false)
      loadSource(false)
    }

    render()
    root.hidden = false

    if (window.jianwenApi && window.jianwenApi.todayAudio) {
      window.jianwenApi.todayAudio().then(apply).catch(() => apply({ ready: false }))
    } else {
      apply({ ready: false })
    }
  }

  const root = document.getElementById('today-audio')
  if (root) mount(root)
})()
