(function () {
  const DEFAULT_API_BASE_URL = `http://${window.location.hostname || '127.0.0.1'}:8000`
  const TOKEN_KEY = 'jianwen_auth_token'
  const USER_KEY = 'jianwen_auth_user'
  const EXPIRES_KEY = 'jianwen_login_expires_at'
  const LEGACY_ACCOUNT_KEY = 'jianwen_local_account'
  const READ_KEY = 'jianwen_read_articles'
  const SESSION_DURATION_MS = 7 * 24 * 60 * 60 * 1000

  function baseUrl() {
    return (localStorage.getItem('jianwen_api_base_url') || DEFAULT_API_BASE_URL).replace(/\/$/, '')
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(EXPIRES_KEY)
    localStorage.removeItem(LEGACY_ACCOUNT_KEY)
    window.dispatchEvent(new Event('jianwen-session-change'))
  }

  function getToken() {
    const token = localStorage.getItem(TOKEN_KEY) || ''
    const expiresAt = Number(localStorage.getItem(EXPIRES_KEY) || 0)
    if (token.startsWith('local-') || (expiresAt && expiresAt <= Date.now())) {
      clearSession()
      return ''
    }
    return token
  }

  function getSessionUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
    } catch {
      localStorage.removeItem(USER_KEY)
      return null
    }
  }

  function setSession(data) {
    if (!data || !data.access_token) throw new Error('后端未返回登录凭证。')
    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(EXPIRES_KEY, String(Date.now() + SESSION_DURATION_MS))
    localStorage.removeItem(LEGACY_ACCOUNT_KEY)
    if (data.user) localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    window.dispatchEvent(new Event('jianwen-session-change'))
  }

  function getReadArticleIds() {
    try {
      const value = JSON.parse(localStorage.getItem(READ_KEY) || '[]')
      return Array.isArray(value) ? value : []
    } catch {
      return []
    }
  }

  function markArticleRead(articleId) {
    const ids = getReadArticleIds()
    if (!ids.includes(articleId)) {
      ids.unshift(articleId)
      localStorage.setItem(READ_KEY, JSON.stringify(ids.slice(0, 200)))
    }
  }

  function errorMessage(detail) {
    if (Array.isArray(detail)) return detail[0] && detail[0].msg ? detail[0].msg : '请求失败'
    return typeof detail === 'string' ? detail : '请求失败'
  }

  function articlePayload(articleId, article) {
    const item = article || {}
    return {
      article_id: articleId,
      topic: item.topic || item.category || '',
      title: item.title || '',
      desc: item.desc || '',
      sources: item.sources || item.source || '',
      read_time: item.read_time || item.readTime || ''
    }
  }

  async function request(path, options, requiresAuth) {
    const requestOptions = Object.assign({}, options || {})
    const headers = Object.assign({}, requestOptions.headers || {})
    const token = getToken()

    if (requiresAuth && !token) throw new Error('请先登录见闻账号。')
    if (requiresAuth) headers.Authorization = `Bearer ${token}`
    if (requestOptions.body && !(requestOptions.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json'
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 15000)
    requestOptions.signal = requestOptions.signal || controller.signal

    let response
    try {
      response = await fetch(`${baseUrl()}${path}`, Object.assign(requestOptions, { headers }))
    } catch (error) {
      if (error && error.name === 'AbortError') throw new Error(`请求超时：${path}`)
      throw new Error(`无法连接见闻服务，请确认后端已在 ${baseUrl()} 启动。`)
    } finally {
      clearTimeout(timeoutId)
    }

    const contentType = response.headers.get('content-type') || ''
    const data = contentType.includes('application/json')
      ? await response.json().catch(() => ({}))
      : await response.text().catch(() => '')

    if (response.status === 401 && requiresAuth) {
      if (getToken() === token) clearSession()
      throw new Error('登录已失效，请重新登录。')
    }
    if (!response.ok) { const error = new Error(errorMessage(data && data.detail)); error.status = response.status; throw error }
    return data
  }

  const publicRequest = (path, options) => request(path, options, false)
  const authRequest = (path, options) => request(path, options, true)
  async function streamRequest(path, body) {
    const token = getToken()
    if (!token) throw new Error('请先登录见闻账号。')
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 15000)
    try {
      const response = await fetch(`${baseUrl()}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
        signal: controller.signal
      })
      if (response.status === 401) {
        clearSession()
        throw new Error('登录已失效，请重新登录。')
      }
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(errorMessage(payload.detail))
      }
      return response
    } catch (error) {
      if (error && error.name === 'AbortError') throw new Error(`请求超时：${path}`)
      throw error
    } finally {
      clearTimeout(timeoutId)
    }
  }
  const withQuery = params => {
    const entries = Object.entries(params || {}).filter(([, value]) => value !== '' && value != null)
    return entries.length ? `?${new URLSearchParams(entries).toString()}` : ''
  }

  window.getToken = getToken
  window.getSessionUser = getSessionUser
  window.setSession = setSession
  window.clearSession = clearSession
  window.getReadArticleIds = getReadArticleIds
  window.markArticleRead = markArticleRead
  window.jianwenApi = {
    baseUrl,
    weeklyReport: week => authRequest(`/api/v1/profile/weekly-report${week ? `?week_start=${encodeURIComponent(week)}` : ''}`, { cache: 'no-store' }),
    readingActivity: data => authRequest('/api/v1/profile/reading-activity', { method: 'POST', body: JSON.stringify(data), keepalive: true }),
    today: () => publicRequest('/api/v1/content/today'),
    personalizedToday: () => authRequest('/api/v1/content/today/personalized'),
    dailyQuote: date => publicRequest(`/api/v1/content/daily-quote${date ? `?date=${encodeURIComponent(date)}` : ''}`),
    categories: () => publicRequest('/api/v1/content/categories'),
    discover: () => publicRequest('/api/v1/content/discover'),
    articles: params => publicRequest(`/api/v1/content/articles${withQuery(params)}`),
    article: id => publicRequest(`/api/v1/content/articles/${encodeURIComponent(id)}`),
    relatedArticles: id => publicRequest(`/api/v1/content/articles/${encodeURIComponent(id)}/related`),
    readingProgress: bookId => authRequest(`/api/v1/profile/reading-positions/${encodeURIComponent(bookId)}`).then(value => value ? { ...value, scroll_progress: value.scroll_progress / 100 } : null),
    saveReadingProgress: (bookId, data) => authRequest(`/api/v1/profile/reading-positions/${encodeURIComponent(bookId)}`, { method: 'PUT', body: JSON.stringify({ ...data, scroll_progress: Math.round(data.scroll_progress * 100) }) }),
    classicBooks: () => publicRequest('/api/v1/content/classic-books'),
    classicBook: id => publicRequest(`/api/v1/content/classic-books/${encodeURIComponent(id)}`),
    classicChapter: (bookId, chapterId) => publicRequest(`/api/v1/content/classic-books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`),
    contentPage: key => publicRequest(`/api/v1/content/pages/${encodeURIComponent(key)}`),
    askBootstrap: () => publicRequest('/api/v1/content/ask/bootstrap'),
    ask: (question, articleId) => authRequest('/api/v1/content/ask', {
      method: 'POST',
      body: JSON.stringify({ question, article_id: articleId || '' })
    }),
    ajinChat: (question, history) => authRequest('/api/v1/content/ajin/chat', {
      method: 'POST',
      body: JSON.stringify({ question, history: Array.isArray(history) ? history.slice(-20) : [] })
    }),
    askStream: (question, articleId) => streamRequest('/api/v1/content/ask/stream', { question, article_id: articleId || '' }),
    profile: () => authRequest('/api/v1/profile/me'),
    updateProfile: data => authRequest('/api/v1/profile/me', { method: 'PATCH', body: JSON.stringify(data) }),
    uploadAvatar: file => {
      const form = new FormData()
      form.append('file', file)
      return authRequest('/api/v1/profile/me/avatar', { method: 'POST', body: form })
    },
    topics: () => authRequest('/api/v1/profile/topics'),
    saveTopics: topics => authRequest('/api/v1/profile/topics', { method: 'PUT', body: JSON.stringify({ topics }) }),
    favorite: id => authRequest(`/api/v1/profile/favorites/${encodeURIComponent(id)}`),
    favorites: () => authRequest('/api/v1/profile/favorites'),
    saveFavorite: (id, article) => authRequest('/api/v1/profile/favorites', { method: 'POST', body: JSON.stringify(articlePayload(id, article)) }),
    deleteFavorite: id => authRequest(`/api/v1/profile/favorites/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    history: () => authRequest('/api/v1/profile/history'),
    saveHistory: (id, article) => authRequest('/api/v1/profile/history', { method: 'POST', body: JSON.stringify(articlePayload(id, article)) }),
    clearHistory: () => authRequest('/api/v1/profile/history', { method: 'DELETE' }),
    aiRecords: () => authRequest('/api/v1/profile/ai-records'),
    clearAiRecords: () => authRequest('/api/v1/profile/ai-records', { method: 'DELETE' }),
    sendSms: (phone, scene) => publicRequest('/api/v1/auth/send-sms', { method: 'POST', body: JSON.stringify({ phone, scene }) }),
    register: data => publicRequest('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(data) }).then(data => {
      setSession(data)
      return data
    }),
    resetPassword: (phone, smsCode, newPassword) => publicRequest('/api/v1/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ phone, sms_code: smsCode, new_password: newPassword })
    }),
    login: (phone, password) => publicRequest('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ phone, password }) }).then(data => {
      setSession(data)
      return data
    })
  }
})()
