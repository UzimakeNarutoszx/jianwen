const FAVORITE_KEY = 'jianwen_favorite_articles'
const READ_KEY = 'jianwen_read_articles'
const HISTORY_KEY = 'jianwen_article_history'
const ASK_RECORD_KEY = 'jianwen_ask_records'
const ASK_SESSION_KEY = 'jianwen_ask_session'

function readArray(key) {
  const value = uni.getStorageSync(key)
  return Array.isArray(value) ? value : []
}

function writeArray(key, value) {
  uni.setStorageSync(key, Array.isArray(value) ? value : [])
}

function compactArticle(id, fallback = {}) {
  return Object.assign({}, fallback, { id })
}

export function getFavoriteIds() {
  return readArray(FAVORITE_KEY)
}

export function isArticleFavorite(id) {
  return getFavoriteIds().includes(id)
}

export function toggleArticleFavorite(id, article = {}) {
  const ids = getFavoriteIds()
  const nextIds = ids.includes(id) ? ids.filter(item => item !== id) : [id].concat(ids)
  writeArray(FAVORITE_KEY, nextIds)
  return nextIds.includes(id)
}

export function getFavoriteArticles() {
  return readArray(FAVORITE_KEY)
    .map(item => (typeof item === 'string' ? null : item))
    .filter(Boolean)
}

export function addArticleHistory(id, article = {}) {
  const item = Object.assign(compactArticle(id, article), {
    visitedAt: Date.now()
  })
  const history = readArray(HISTORY_KEY).filter(record => record.id !== id)
  writeArray(HISTORY_KEY, [item].concat(history).slice(0, 50))
}

export function getReadArticleIds() {
  return readArray(READ_KEY)
}

export function markArticleRead(id) {
  const readIds = readArray(READ_KEY)
  if (!readIds.includes(id)) {
    writeArray(READ_KEY, readIds.concat(id))
  }
}

export function getArticleHistory() {
  return readArray(HISTORY_KEY)
}

export function addAskRecord(question, answer, sources = '') {
  const text = question.trim()
  if (!text) return

  const records = readArray(ASK_RECORD_KEY)
  writeArray(ASK_RECORD_KEY, [
    {
      id: `${Date.now()}`,
      question: text,
      answer,
      sources,
      createdAt: Date.now()
    }
  ].concat(records).slice(0, 80))
}

export function getAskRecords() {
  return readArray(ASK_RECORD_KEY)
}

export function getAskSession() {
  const value = uni.getStorageSync(ASK_SESSION_KEY)
  return value && typeof value === 'object' ? value : { messages: [], linkedArticle: null }
}

export function saveAskSession(session) {
  uni.setStorageSync(ASK_SESSION_KEY, {
    messages: Array.isArray(session?.messages) ? session.messages.slice(-40) : [],
    linkedArticle: session?.linkedArticle || null,
    savedAt: Date.now()
  })
}
