const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (typeof window !== 'undefined' && window.location.hostname
  ? `http://${window.location.hostname}:8000`
  : 'http://127.0.0.1:8000')
const TODAY_FALLBACK_ARTICLE_LIMIT = 5

export function getApiBaseUrl() {
  return uni.getStorageSync('jianwen_api_base_url') || DEFAULT_API_BASE_URL
}

export function getAuthToken() {
  return uni.getStorageSync('jianwen_auth_token') || ''
}

export function buildFileUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//.test(path)) return path
  return `${getApiBaseUrl()}${path}`
}

function normalizeApiError(detail) {
  if (Array.isArray(detail)) return detail[0]?.msg || '请求失败'
  if (typeof detail === 'string') return detail
  return '请求失败'
}

export function apiRequest({ url, method = 'GET', data = {}, token = '' }) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${getApiBaseUrl()}${url}`,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      success(response) {
        const statusCode = response.statusCode || 0
        if (statusCode >= 200 && statusCode < 300) {
          resolve(response.data)
          return
        }
        const error = new Error(normalizeApiError(response.data && response.data.detail))
        error.status = statusCode
        reject(error)
      },
      fail(error) {
        reject(new Error(error.errMsg || '网络连接失败，请检查后端是否已启动'))
      }
    })
  })
}

export function authRequest({ url, method = 'GET', data = {} }) {
  return apiRequest({ url, method, data, token: getAuthToken() })
}

function fromContentArticle(record = {}) {
  return {
    id: record.id || record.article_id,
    articleId: record.article_id || record.id,
    category: record.category || record.topic || '',
    topic: record.topic || record.category || '',
    title: record.title || '',
    desc: record.desc || '',
    source: record.source || record.sources || '',
    sources: record.sources || record.source || '',
    readTime: record.read_time || record.readTime || '',
    image: record.image || '',
    relation: record.relation || '',
    viewed: !!record.viewed,
    summary: Array.isArray(record.summary) ? record.summary : [],
    sections: Array.isArray(record.sections) ? record.sections : [],
    references: Array.isArray(record.references) ? record.references : []
  }
}

function fromContentCategory(record = {}) {
  return {
    id: record.id,
    name: record.name || '',
    image: record.image || '',
    isPriority: !!record.is_priority,
    sortOrder: record.sort_order || 0
  }
}

function fromContentFeature(record = {}) {
  return {
    id: record.id,
    title: record.title || '',
    desc: record.desc || '',
    tags: record.tags || '',
    image: record.image || '',
    count: record.count || 0,
    categoryName: record.category_name || ''
  }
}

function fromClassicChapter(record = {}) {
  return {
    id: record.id,
    bookId: record.book_id || '',
    title: record.title || '',
    chapterOrder: record.chapter_order || 0,
    summary: record.summary || '',
    externalUrl: record.external_url || '',
    content: record.content || '',
    hasFullText: !!record.has_full_text
  }
}

function fromClassicBook(record = {}) {
  return {
    id: record.id,
    bookId: record.book_id || '',
    title: record.title || '',
    author: record.author || '',
    category: record.category || '',
    description: record.description || '',
    coverImage: record.cover_image || '',
    sourceOrg: record.source_org || '',
    externalUrl: record.external_url || '',
    isFeatured: !!record.is_featured,
    sortOrder: record.sort_order || 0,
    chapters: Array.isArray(record.chapters) ? record.chapters.map(fromClassicChapter) : []
  }
}

function fromDailyQuote(record = {}) {
  return {
    quoteId: record.quote_id || '',
    text: record.text || '',
    sourceTitle: record.source_title || '',
    sourceAuthor: record.source_author || '',
    sourceType: record.source_type || '',
    theme: record.theme || '',
    plainExplanation: record.plain_explanation || '',
    todayConnection: record.today_connection || '',
    sortOrder: record.sort_order || 0,
    isActive: record.is_active !== false
  }
}

function fromArticleRecord(record = {}) {
  return {
    id: record.article_id,
    articleId: record.article_id,
    topic: record.topic,
    title: record.title,
    desc: record.desc,
    sources: record.sources,
    source: record.sources,
    readTime: record.read_time,
    visitedAt: record.visited_at ? new Date(record.visited_at).getTime() : undefined
  }
}

function fromAiRecord(record = {}) {
  return {
    id: `${record.id}`,
    question: record.question,
    answer: record.answer,
    sources: record.sources,
    createdAt: record.created_at ? new Date(record.created_at).getTime() : undefined
  }
}

function articlePayload(articleId, article = {}) {
  return {
    article_id: articleId,
    topic: article.topic || article.category || '',
    title: article.title || '',
    desc: article.desc || '',
    sources: article.sources || article.source || '',
    read_time: article.readTime || article.read_time || ''
  }
}

export function sendSms(phone, scene) {
  return apiRequest({ url: '/api/v1/auth/send-sms', method: 'POST', data: { phone, scene } })
}

export function registerWithSms(data) {
  return apiRequest({ url: '/api/v1/auth/register', method: 'POST', data })
}

export function loginWithPassword(phone, password) {
  return apiRequest({ url: '/api/v1/auth/login', method: 'POST', data: { phone, password } })
}

export function resetPasswordBySms(phone, code, newPassword) {
  return apiRequest({
    url: '/api/v1/auth/forgot-password',
    method: 'POST',
    data: { phone, sms_code: code, new_password: newPassword }
  })
}

export function getMyProfile() {
  return authRequest({ url: '/api/v1/profile/me' })
}

export function updateMyProfile(data) {
  return authRequest({ url: '/api/v1/profile/me', method: 'PATCH', data })
}

export function uploadMyAvatar(filePath) {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${getApiBaseUrl()}/api/v1/profile/me/avatar`,
      filePath,
      name: 'file',
      header: { Authorization: `Bearer ${getAuthToken()}` },
      success(response) {
        const statusCode = response.statusCode || 0
        let data = response.data
        try {
          data = typeof data === 'string' ? JSON.parse(data) : data
        } catch (error) {
          reject(new Error('头像上传响应解析失败'))
          return
        }
        if (statusCode >= 200 && statusCode < 300) {
          resolve(data)
          return
        }
        reject(new Error(normalizeApiError(data && data.detail)))
      },
      fail(error) { reject(new Error(error.errMsg || '头像上传失败')) }
    })
  })
}

export function getTodayContent() {
  return apiRequest({ url: '/api/v1/content/today' }).then(data => {
    const records = Array.isArray(data) ? data : (data.articles || [])
    const articles = records.slice(0, TODAY_FALLBACK_ARTICLE_LIMIT).map(fromContentArticle)
    const banners = data.banners || articles.slice(0, 2).map(item => ({
      id: `today-${item.id}`,
      type: 'article',
      articleId: item.id,
      title: item.title,
      desc: item.desc,
      image: item.image
    }))
    return { articles, banners }
  })
}

export function getRemoteTodayChecklist() {
  return authRequest({ url: '/api/v1/content/today/personalized' }).then(data => {
    const articles = (data.articles || []).map(fromContentArticle)
    const banners = articles.slice(0, 2).map(item => ({
      id: `today-${item.id}`,
      type: 'article',
      articleId: item.id,
      title: item.title,
      desc: item.desc,
      image: item.image
    }))
    return {
      articles,
      banners,
      totalCount: data.total_count || articles.length,
      readCount: data.read_count || articles.filter(item => item.viewed).length,
      isComplete: !!data.is_complete
    }
  })
}

export function getDailyQuote(date) {
  const suffix = date ? `?date=${encodeURIComponent(date)}` : ''
  return apiRequest({ url: `/api/v1/content/daily-quote${suffix}` }).then(fromDailyQuote)
}

export function getArticleDetail(id) {
  return apiRequest({ url: `/api/v1/content/articles/${encodeURIComponent(id)}` }).then(fromContentArticle)
}

export function getDiscoverContent() {
  return apiRequest({ url: '/api/v1/content/discover' }).then(data => ({
    topics: (data.topics || []).map(fromContentCategory),
    features: (data.features || []).map(fromContentFeature),
    updates: (data.updates || []).map(fromContentArticle)
  }))
}

export function getClassicBooks() {
  return apiRequest({ url: '/api/v1/content/classic-books' }).then(records => records.map(fromClassicBook))
}

export function getClassicBookDetail(bookId) {
  // 空 bookId 会请求到书目列表接口，把数组当成一本书渲染
  if (!bookId) return Promise.reject(new Error('未指定经典文献'))
  return apiRequest({ url: `/api/v1/content/classic-books/${encodeURIComponent(bookId)}` }).then(fromClassicBook)
}

export function getClassicBookChapter(bookId, chapterId) {
  return apiRequest({
    url: `/api/v1/content/classic-books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`
  }).then(fromClassicChapter)
}

export function getCategories() {
  return apiRequest({ url: '/api/v1/content/categories' }).then(records => records.map(fromContentCategory))
}

export function getArticleList(params = {}) {
  const query = []
  if (params.category) query.push(`category=${encodeURIComponent(params.category)}`)
  if (params.q) query.push(`q=${encodeURIComponent(params.q)}`)
  const suffix = query.length ? `?${query.join('&')}` : ''
  return apiRequest({ url: `/api/v1/content/articles${suffix}` }).then(records => records.map(fromContentArticle))
}

export function getContentPage(pageKey) {
  return apiRequest({ url: `/api/v1/content/pages/${encodeURIComponent(pageKey)}` })
}

export function getAskBootstrap() {
  return apiRequest({ url: '/api/v1/content/ask/bootstrap' }).then(data => ({
    prompts: data.prompts || [],
    followups: data.followups || [],
    welcomeMessage: data.welcome_message || ''
  }))
}

export function askQuestion(question, options = {}) {
  return authRequest({
    url: '/api/v1/content/ask',
    method: 'POST',
    data: {
      question,
      article_id: options.articleId || ''
    }
  })
}

export async function askQuestionStream(question, options = {}, onDelta = () => {}) {
  if (typeof fetch !== 'function') {
    throw new Error('当前运行环境不支持流式请求')
  }

  const response = await fetch(`${getApiBaseUrl()}/api/v1/content/ask/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {})
    },
    body: JSON.stringify({
      question,
      article_id: options.articleId || ''
    })
  })

  if (!response.ok) {
    let detail = ''
    try {
      const data = await response.json()
      detail = normalizeApiError(data && data.detail)
    } catch (error) {
      detail = response.statusText || '流式回答失败'
    }
    throw new Error(detail)
  }

  if (!response.body || typeof response.body.getReader !== 'function') {
    const text = await response.text()
    if (text) onDelta(text)
    return text
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let fullText = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value, { stream: true })
    if (!chunk) continue
    fullText += chunk
    onDelta(chunk)
  }

  const tail = decoder.decode()
  if (tail) {
    fullText += tail
    onDelta(tail)
  }

  return fullText
}

export function getRemoteFavorites() {
  return authRequest({ url: '/api/v1/profile/favorites' }).then(records => records.map(fromArticleRecord))
}

export function getRemoteFavorite(articleId) {
  return authRequest({ url: `/api/v1/profile/favorites/${articleId}` })
}

export function saveRemoteFavorite(articleId, article) {
  return authRequest({ url: '/api/v1/profile/favorites', method: 'POST', data: articlePayload(articleId, article) })
}

export function deleteRemoteFavorite(articleId) {
  return authRequest({ url: `/api/v1/profile/favorites/${articleId}`, method: 'DELETE' })
}

export function getRemoteHistory() {
  return authRequest({ url: '/api/v1/profile/history' }).then(records => records.map(fromArticleRecord))
}

export function saveRemoteHistory(articleId, article) {
  return authRequest({ url: '/api/v1/profile/history', method: 'POST', data: articlePayload(articleId, article) })
}

export function getRemoteAiRecords() {
  return authRequest({ url: '/api/v1/profile/ai-records' }).then(records => records.map(fromAiRecord))
}

export function saveRemoteAiRecord(question, answer, sources = '') {
  return authRequest({ url: '/api/v1/profile/ai-records', method: 'POST', data: { question, answer, sources } })
}

export function getRemoteFollowTopics() {
  return authRequest({ url: '/api/v1/profile/topics' })
}

export function saveRemoteFollowTopics(topics) {
  return authRequest({ url: '/api/v1/profile/topics', method: 'PUT', data: { topics } })
}

export function getWeeklyReport(week = '') {
  return authRequest({ url: `/api/v1/profile/weekly-report${week ? `?week_start=${encodeURIComponent(week)}` : ''}` })
}

export function postReadingActivity(data, token = getAuthToken()) {
  return apiRequest({ url: '/api/v1/profile/reading-activity', method: 'POST', data, token })
}

// Public resources share a root so relative media paths resolve identically in App and H5.
export function buildPublicUrl(path = '') {
  const root = `${getApiBaseUrl().replace(/\/$/, '')}/public/`
  if (/^https?:\/\//i.test(path)) return path
  return `${root}${path.replace(/^\/+/, '')}`
}

export function getWeeklyCatalog() {
  return apiRequest({ url: '/public/data/weekly-videos.json', data: { _t: Date.now() } })
}

export function getChangelog() {
  return apiRequest({ url: '/public/data/changelog.json', data: { _t: Date.now() } })
}
