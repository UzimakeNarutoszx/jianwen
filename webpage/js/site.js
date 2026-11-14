if (location.protocol === 'file:') {
  const marker = '/webpage/'
  const normalizedPath = location.pathname.replace(/\\/g, '/')
  const markerIndex = normalizedPath.toLowerCase().lastIndexOf(marker)
  const relativePath = markerIndex >= 0
    ? normalizedPath.slice(markerIndex + marker.length)
    : normalizedPath.split('/').pop()
  if (relativePath !== 'index.html') location.replace(`http://127.0.0.1:8765/${relativePath}${location.search}${location.hash}`)
}

const portalPages = [
  { href: 'index.html', label: '首页' },
  { href: 'changelog.html', label: '更新日志' }
]

const ajinPages = [
  { href: 'avatar.html', label: '阿烬' }
]

const jianwenPages = [
  { href: 'jianwen/index.html', label: '今日', key: 'today' },
  { href: 'jianwen/discover.html', label: '发现', key: 'discover' },
  { href: 'jianwen/ask.html', label: 'AI 问问', key: 'ask' },
  { href: 'jianwen/weekly.html', label: '每周', key: 'weekly' }
]

const AUTH_TOKEN_KEY = 'jianwen_auth_token'
const AUTH_USER_KEY = 'jianwen_auth_user'
const SITE_VERSION = '20261115-4'
const BUILD_VERSION_KEY = 'jianwen_web_build_version'

function versionedPage(href) {
  const [path, hash] = href.split('#')
  const [pathname, query = ''] = path.split('?')
  const params = new URLSearchParams(query)
  params.set('v', SITE_VERSION)
  return `${pathname}?${params}${hash === undefined ? '' : `#${hash}`}`
}

function canonicalCurrentUrl() {
  const params = new URLSearchParams(location.search)
  params.set('v', SITE_VERSION)
  const query = params.toString()
  return `${location.pathname}${query ? `?${query}` : ''}${location.hash}`
}

function guardStaleWindow(event) {
  let knownVersion = ''
  try { knownVersion = localStorage.getItem(BUILD_VERSION_KEY) || '' } catch {}
  const currentVersion = new URLSearchParams(location.search).get('v') || ''
  const staleWindow = Boolean(event?.persisted) || (knownVersion && knownVersion !== SITE_VERSION) || currentVersion !== SITE_VERSION
  try { localStorage.setItem(BUILD_VERSION_KEY, SITE_VERSION) } catch {}
  if (staleWindow) {
    const target = canonicalCurrentUrl()
    if (`${location.pathname}${location.search}${location.hash}` !== target) {
      if (typeof location.replace === 'function') location.replace(target)
    } else if (typeof location.reload === 'function') location.reload()
  }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[character]))
}

function readAuthUser() {
  try {
    const user = JSON.parse(localStorage.getItem(AUTH_USER_KEY) || 'null')
    return user && typeof user === 'object' ? user : null
  } catch {
    localStorage.removeItem(AUTH_USER_KEY)
    return null
  }
}

function isJianwenCurrent(key, current) {
  if (key === 'today') return ['index.html', 'article.html'].includes(current)
  if (key === 'discover') return ['discover.html', 'reader.html', 'category.html'].includes(current)
  if (key === 'weekly') return current === 'weekly.html'
  if (key === 'ask') return current === 'ask.html'
  if (key === 'account') return ['login.html', 'profile.html'].includes(current)
  return false
}

function renderShell() {
  const inJianwen = location.pathname.includes('/jianwen/')
  const root = inJianwen ? '../' : ''
  const pathName = location.pathname.split('/').pop() || ''
  const current = pathName.includes('.') ? pathName : 'index.html'
  const header = document.querySelector('[data-site-header]')
  const footer = document.querySelector('[data-site-footer]')
  const storedToken = localStorage.getItem(AUTH_TOKEN_KEY) || ''
  const expiresAt = Number(localStorage.getItem('jianwen_login_expires_at') || 0)
  const token = storedToken.startsWith('local-') || (expiresAt && expiresAt <= Date.now()) ? '' : storedToken
  if (storedToken && !token) {
    localStorage.removeItem(AUTH_TOKEN_KEY)
    localStorage.removeItem(AUTH_USER_KEY)
    localStorage.removeItem('jianwen_login_expires_at')
    localStorage.removeItem('jianwen_local_account')
  }
  const user = token ? readAuthUser() : null
  const nickname = user && (user.nickname || user.name) ? ` · ${escapeHtml(user.nickname || user.name)}` : ''
  const accountLabel = token ? `账号已登录${nickname}` : '登录'
  const accountHref = versionedPage(token ? `${root}jianwen/profile.html` : `${root}jianwen/login.html`)

  if (header) {
    header.className = 'site-header'
    header.id = 'site-navigation'
    const portalNav = portalPages.map(page => { const pagePath = page.href.split('#')[0]; return `<a href="${versionedPage(`${root}${page.href}`)}" ${!inJianwen && current === pagePath ? 'aria-current="page"' : ''}>${page.label}</a>` }).join('')
    const ajinNav = ajinPages.map(page => { const pagePath = page.href.split('#')[0]; return `<a href="${versionedPage(`${root}${page.href}`)}" ${!inJianwen && current === pagePath ? 'aria-current="page"' : ''}>${page.label}</a>` }).join('')
    const jianwenNav = jianwenPages.map(page => `<a href="${versionedPage(`${root}${page.href}`)}" ${inJianwen && isJianwenCurrent(page.key, current) ? 'aria-current="page"' : ''}>${page.label}</a>`).join('')
    const accountCurrent = inJianwen && isJianwenCurrent('account', current) ? ' aria-current="page"' : ''
    header.innerHTML = `<div class="header-top"><a class="brand" href="${versionedPage(`${root}index.html`)}"><span class="brand-mark"><img src="${root}assets/agents-96.png?v=agents-1" alt=""></span><span>见闻 <small>JIANWEN</small></span></a><span class="header-caption">保持好奇，也保持思考。</span><a class="nav-account" href="${accountHref}"${accountCurrent}>${token ? '我的见闻' : '登录 / 注册'} <span aria-hidden="true">↗</span></a></div><nav class="site-nav" aria-label="全站导航"><div class="nav-group">${portalNav}</div><div class="nav-group">${jianwenNav}</div><div class="nav-group">${ajinNav}</div></nav>`
    const main = document.querySelector('main')
    if (main && !document.querySelector('.skip-link')) {
      main.id ||= 'main-content'
      const skip = document.createElement('a')
      skip.className = 'skip-link'
      skip.href = `#${main.id}`
      skip.textContent = '跳到主要内容'
      document.body.prepend(skip)
    }
  }

  if (footer) {
    footer.className = 'site-footer'
    footer.innerHTML = `<p>© 2026 见闻 · 个人门户 · <a class="site-icp" href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">京ICP备2026077702号-1</a></p><div class="footer-links"><a href="${versionedPage(`${root}index.html`)}">门户首页</a><a href="${versionedPage(`${root}jianwen/index.html`)}">见闻今日</a><a href="${versionedPage(`${root}jianwen/ask.html`)}">AI 问问</a><a href="${versionedPage(`${root}changelog.html`)}">更新日志</a></div>`
  }
}

document.querySelectorAll('img[data-fallback]').forEach(image => {
  image.addEventListener('error', () => {
    image.classList.add('is-fallback')
    image.alt = image.dataset.fallback
  }, { once: true })
})

function stripHeadingPeriods(root) {
  const headings = root.querySelectorAll('title, h1, h2, h3')
  headings.forEach(heading => {
    const cleanTextNodes = node => {
      node.childNodes.forEach(child => {
        if (child.nodeType === 3) child.nodeValue = child.nodeValue.replace(/。+$/u, '')
        else cleanTextNodes(child)
      })
    }
    cleanTextNodes(heading)
  })
}


guardStaleWindow()
renderShell()
window.addEventListener('jianwen-session-change', renderShell)
window.addEventListener('pageshow', guardStaleWindow)
stripHeadingPeriods(document)
if (location.pathname.endsWith('/avatar.html')) {
  const apiScript = document.createElement('script')
  apiScript.src = 'js/api-browser.js?v=20261115-4'
  apiScript.onload = () => {
    const chatScript = document.createElement('script')
    chatScript.src = 'js/ajin-chat.js?v=20261115-4'
    document.body.appendChild(chatScript)
  }
  document.body.appendChild(apiScript)
}
const titleObserver = new MutationObserver(() => stripHeadingPeriods(document))
titleObserver.observe(document.documentElement, { childList: true, subtree: true })
