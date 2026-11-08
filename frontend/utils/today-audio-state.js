// 今日朗读的纯状态逻辑：不碰 uni API、不碰网络，App 和网站用同一套规则。
// 约定见 docs/today-audio-contract.md：manifest.articles 只在当日范围内切换，声音缺失时禁用并回退。
export const VOICE_STORAGE_KEY = 'jianwen_tts_voice'

export const DEFAULT_VOICES = [
  { id: 'jianwen', label: '见闻' },
  { id: 'dylan', label: '男声·京味' }
]

export const PENDING_TEXT = '今日朗读生成中'

function normalizeVoices(voices) {
  const list = (Array.isArray(voices) ? voices : [])
    .filter(item => item && typeof item.id === 'string' && item.id)
    .map(item => ({ id: item.id, label: String(item.label || item.id) }))
  if (list.length) return list
  return DEFAULT_VOICES.map(item => ({ id: item.id, label: item.label }))
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
export function normalizeManifest(raw) {
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

// 当前文章有音频的声音；一篇都没音频时返回空数组，界面据此禁用播放。
export function playableVoices(state) {
  const article = state.articles[state.index]
  if (!article) return []
  return state.voices.filter(voice => Boolean(article.audio[voice.id]))
}

// 首选声音：用户保存过且当前文章有就沿用，否则回退到第一个可用声音（默认见闻）。
export function resolveVoice(state, index, preferred) {
  const article = state.articles[index]
  const available = article ? state.voices.filter(voice => Boolean(article.audio[voice.id])) : []
  if (!available.length) return state.voices.length ? state.voices[0].id : ''
  if (preferred && available.some(voice => voice.id === preferred)) return preferred
  return available[0].id
}

export function voiceOptions(state) {
  const article = state.articles[state.index]
  return state.voices.map(voice => ({
    id: voice.id,
    label: voice.label,
    available: Boolean(article && article.audio[voice.id]),
    active: voice.id === state.voice
  }))
}

export function createTodayAudioState(raw, savedVoice = '') {
  const manifest = normalizeManifest(raw)
  const state = Object.assign({}, manifest, { index: 0, voice: '' })
  state.voice = resolveVoice(state, 0, savedVoice)
  return state
}

export function setIndex(state, index) {
  const last = state.articles.length - 1
  if (last < 0) return state
  const value = Number(index)
  const next = Math.min(Math.max(Number.isFinite(value) ? Math.round(value) : 0, 0), last)
  if (next === state.index) return state
  return Object.assign({}, state, { index: next, voice: resolveVoice(state, next, state.voice) })
}

export function step(state, delta) {
  return setIndex(state, state.index + (Number(delta) || 0))
}

export function canPrev(state) {
  return state.ready === true && state.articles.length > 0 && state.index > 0
}

export function canNext(state) {
  return state.ready === true && state.index < state.articles.length - 1
}

export function selectVoice(state, voiceId) {
  const voice = resolveVoice(state, state.index, voiceId)
  return voice === state.voice ? state : Object.assign({}, state, { voice })
}

export function currentTrack(state) {
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

export function hasTrack(state) {
  const track = currentTrack(state)
  return Boolean(track && track.url)
}

// 自动续播只发生在当日清单内；最后一篇播完就停在原地。
export function afterEnded(state) {
  if (!canNext(state)) return { state, play: false, finished: true }
  return { state: step(state, 1), play: true, finished: false }
}

export function formatTime(seconds) {
  const value = Number(seconds)
  if (!Number.isFinite(value) || value <= 0) return '0:00'
  const total = Math.floor(value)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

// 切换声音时保留播放进度比例，不因为换了音源回到开头。
export function progressRatio(current, duration) {
  const total = Number(duration)
  const value = Number(current)
  if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(value) || value <= 0) return 0
  return Math.min(Math.max(value / total, 0), 1)
}

export function ratioToSeconds(ratio, duration) {
  const total = Number(duration)
  const value = Number(ratio)
  if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(value) || value <= 0) return 0
  return Math.min(Math.max(value, 0), 1) * total
}

export function statusLabel(state, loading = false) {
  if (loading) return '正在读取今日朗读'
  if (state.ready !== true) return PENDING_TEXT
  if (!state.articles.length) return '今日暂无可朗读的文章'
  const article = state.articles[state.index]
  const available = article && Object.keys(article.audio).length > 0
  return available ? '' : '这篇暂无可播放音频'
}

// 「听完即读完」：只累计真实播放推进的比例（拖动跳过的不算），按比例记录，换声音不清零。
// 累计到 LISTEN_DONE_RATIO 即视为这篇已读；每篇只触发一次。
export const LISTEN_DONE_RATIO = 0.9
export function createListenTracker() {
  return { heard: {}, last: null, done: {} }
}
// 每次 timeupdate 调用；delta 只在 0~2 秒内才计入，超出视为拖动或换源。返回 true 表示这次刚好听完。
export function trackListen(tracker, articleId, current, duration) {
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
export function resetListenAnchor(tracker) {
  tracker.last = null
}
// ended 时调用：尾部最后一次 timeupdate 到结束之间的空档补齐后再判断。
export function finishListen(tracker, articleId, duration) {
  const last = tracker.last
  if (last && last.id === articleId) return trackListen(tracker, articleId, Math.min(Number(duration), last.time + 2), duration)
  return markIfDone(tracker, articleId)
}
function markIfDone(tracker, articleId) {
  if (tracker.done[articleId] || (tracker.heard[articleId] || 0) < LISTEN_DONE_RATIO) return false
  tracker.done[articleId] = true
  return true
}
