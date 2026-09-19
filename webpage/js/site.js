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
  { href: 'about.html', label: '关于我' },
  { href: 'links.html', label: '网址与应用' }
]

const ajinPages = [
  { href: 'avatar.html', label: '阿烬产品' },
  { href: 'avatar-features.html', label: '功能与对话' },
  { href: 'avatar-growth.html', label: '成长理念' },
  { href: 'avatar.html#contact', label: '购买与体验' }
]

const jianwenPages = [
  { href: 'jianwen/index.html', label: '今日', key: 'today' },
  { href: 'jianwen/discover.html', label: '发现', key: 'discover' },
  { href: 'jianwen/search.html', label: '搜索', key: 'search' },
  { href: 'jianwen/classics.html', label: '经典', key: 'classics' },
  { href: 'jianwen/ask.html', label: 'AI 问问', key: 'ask' }
]

const AUTH_TOKEN_KEY = 'jianwen_auth_token'
const AUTH_USER_KEY = 'jianwen_auth_user'
const SITE_VERSION = '20260919-3'

function versionedPage(href) {
  return `${href}${href.includes('?') ? '&' : '?'}v=${SITE_VERSION}`
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
  if (key === 'discover') return current === 'discover.html'
  if (key === 'search') return current === 'search.html'
  if (key === 'classics') return ['classics.html', 'reader.html'].includes(current)
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
    const portalNav = portalPages.map(page => `<a href="${root}${page.href}" ${!inJianwen && current === page.href ? 'aria-current="page"' : ''}>${page.label}</a>`).join('')
    const ajinNav = ajinPages.map(page => `<a href="${root}${page.href}" ${!inJianwen && current === page.href ? 'aria-current="page"' : ''}>${page.label}</a>`).join('')
    const jianwenNav = jianwenPages.map(page => `<a href="${versionedPage(`${root}${page.href}`)}" ${inJianwen && isJianwenCurrent(page.key, current) ? 'aria-current="page"' : ''}>${page.label}</a>`).join('')
    const accountCurrent = inJianwen && isJianwenCurrent('account', current) ? ' aria-current="page"' : ''
    header.innerHTML = `<div class="header-top"><a class="brand" href="${root}index.html"><span class="brand-mark"><img src="${root}assets/brand.webp" alt=""></span><span>见闻 <small>JIANWEN</small></span></a><span class="header-caption">保持好奇，也保持思考。</span><a class="nav-account" href="${accountHref}"${accountCurrent}>${token ? '我的见闻' : '登录 / 注册'} <span aria-hidden="true">↗</span></a></div><nav class="site-nav" aria-label="全站导航"><div class="nav-group"><span class="nav-label">门户</span>${portalNav}</div><div class="nav-group"><span class="nav-label">阅读</span>${jianwenNav}</div><div class="nav-group"><span class="nav-label">阿烬</span>${ajinNav}</div></nav>`
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
    footer.innerHTML = `<p>© 2026 见闻 · 个人门户</p><div class="footer-links"><a href="${root}index.html">门户首页</a><a href="${versionedPage(`${root}jianwen/index.html`)}">见闻今日</a><a href="${versionedPage(`${root}jianwen/ask.html`)}">AI 问问</a></div>`
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

function initializeGlobalBgm() {
  if (document.getElementById('site-bgm')) return
  const inJianwen = location.pathname.includes('/jianwen/')
  const root = inJianwen ? '../' : ''
  if (!document.getElementById('global-bgm-style')) {
    const style = document.createElement('style')
    style.id = 'global-bgm-style'
    style.textContent = '.bgm-control{position:fixed;right:24px;bottom:24px;z-index:30}.bgm-toggle{display:inline-flex;align-items:center;gap:8px;padding:10px 15px;border:1px solid rgba(255,255,255,.92);border-radius:999px;background:rgba(255,255,255,.9);box-shadow:0 12px 30px rgba(31,47,58,.18);backdrop-filter:blur(14px);color:#143e52;font:800 13px/1.2 inherit;cursor:pointer;transition:transform .2s ease,box-shadow .2s ease}.bgm-toggle:hover{transform:translateY(-2px);box-shadow:0 16px 36px rgba(31,47,58,.24)}.bgm-toggle:focus-visible{outline:3px solid rgba(212,170,78,.6);outline-offset:3px}.bgm-icon{font-size:16px;line-height:1}.bgm-toggle.is-muted{color:#667780}@media(max-width:620px){.bgm-control{right:16px;bottom:16px}.bgm-toggle{padding:9px 12px}}@media(prefers-reduced-motion:reduce){.bgm-toggle{transition:none}}@media(prefers-color-scheme:dark){.bgm-toggle{border-color:rgba(219,239,241,.2);background:rgba(20,50,63,.92);color:#edf5f4}.bgm-toggle.is-muted{color:#c2d1d4}}'
    document.head.appendChild(style)
  }
  const control = document.createElement('div')
  control.className = 'bgm-control'
  control.innerHTML = '<button id="bgm-toggle" class="bgm-toggle" type="button" aria-label="静音背景音乐" title="静音背景音乐"><span class="bgm-icon" aria-hidden="true">🔊</span><span class="bgm-label">静音</span></button>'

  const audio = document.createElement('audio')
  audio.id = 'site-bgm'
  audio.autoplay = true
  audio.loop = true
  audio.playsInline = true
  audio.preload = 'auto'
  audio.src = `${root}assets/Vastness.mp3`
  audio.setAttribute('aria-hidden', 'true')

  document.body.append(control, audio)
  const toggle = control.querySelector('#bgm-toggle')
  const icon = control.querySelector('.bgm-icon')
  const label = control.querySelector('.bgm-label')
  const storageKey = 'jianwen_bgm_muted'
  let storedMuted = null

  try { storedMuted = localStorage.getItem(storageKey) } catch {}
  audio.volume = 0.2
  audio.muted = storedMuted !== 'false'

  function updateToggle() {
    const muted = audio.muted
    toggle.classList.toggle('is-muted', muted)
    icon.textContent = muted ? '🔇' : '🔊'
    label.textContent = muted ? '开启声音' : '静音'
    toggle.setAttribute('aria-label', muted ? '开启背景音乐' : '静音背景音乐')
    toggle.title = muted ? '开启背景音乐' : '静音背景音乐'
  }

  function savePreference() {
    try { localStorage.setItem(storageKey, String(audio.muted)) } catch {}
  }

  updateToggle()
  audio.play().catch(() => {
    audio.muted = true
    updateToggle()
    audio.play().catch(() => {})
  })
  toggle.addEventListener('click', () => {
    audio.muted = !audio.muted
    savePreference()
    updateToggle()
    audio.play().catch(() => {})
  })
}

renderShell()
window.addEventListener('jianwen-session-change', renderShell)
stripHeadingPeriods(document)
initializeGlobalBgm()
if (location.pathname.endsWith('/avatar-features.html')) {
  const apiScript = document.createElement('script')
  apiScript.src = 'js/api-browser.js?v=20260919-3'
  apiScript.onload = () => {
    const chatScript = document.createElement('script')
    chatScript.src = 'js/ajin-chat.js?v=20260919-3'
    document.body.appendChild(chatScript)
  }
  document.body.appendChild(apiScript)
}
const titleObserver = new MutationObserver(() => stripHeadingPeriods(document))
titleObserver.observe(document.documentElement, { childList: true, subtree: true })
