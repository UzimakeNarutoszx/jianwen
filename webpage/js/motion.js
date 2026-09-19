(function () {
  'use strict'
  const script = document.currentScript
  const assets = new URL('../assets/motion/', script ? script.src : location.href)
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
  const connection = navigator.connection
  const films = []
  const gently = () => reduced.matches || !!connection?.saveData

  function initialize(container) {
    if (container.dataset.motionReady) return
    container.dataset.motionReady = 'true'
    container.classList.add('motion-film')
    const variant = container.dataset.motionFilm === 'ambient' ? 'ajin-ambient' : 'ajin-studio'
    container.style.backgroundImage = `url("${new URL(`${variant}-poster.jpg`, assets).href}")`
    const video = document.createElement('video')
    video.className = 'motion-film-video'
    video.poster = new URL(`${variant}-poster.jpg`, assets).href
    video.muted = true
    video.defaultMuted = true
    video.loop = true
    video.playsInline = true
    video.preload = 'none'
    video.setAttribute('aria-hidden', 'true')
    video.setAttribute('tabindex', '-1')
    video.setAttribute('playsinline', '')
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'motion-film-toggle'
    button.setAttribute('aria-label', '播放展示短片')
    button.textContent = '播放短片'
    const status = document.createElement('span')
    status.className = 'motion-film-status'
    status.setAttribute('role', 'status')
    container.append(video, button, status)
    if (!container.hasAttribute('aria-label')) container.setAttribute('aria-label', '阿烬原创产品展示短片')
    if (!container.hasAttribute('role')) container.setAttribute('role', 'group')
    const item = { container, video, button, status, visible: false, userPaused: false, userAllowed: false, failed: false, pending: false }
    films.push(item)

    function reflect() {
      const playing = !video.paused
      button.textContent = playing ? '暂停短片' : '播放短片'
      button.setAttribute('aria-label', playing ? '暂停展示短片' : '播放展示短片')
      container.classList.toggle('is-playing', playing)
    }
    item.update = async () => {
      const allowed = item.visible && !document.hidden && !item.userPaused && (!gently() || item.userAllowed) && !item.failed
      if (!allowed) { video.pause(); reflect(); return }
      if (!video.paused || item.pending) return
      if (!video.getAttribute('src')) video.src = new URL(`${variant}.mp4`, assets).href
      item.pending = true
      try {
        await video.play()
        if (!item.visible || document.hidden || item.userPaused || (gently() && !item.userAllowed)) video.pause()
      } catch (error) {
        if (error.name !== 'AbortError') {
          item.userPaused = true
          status.textContent = '点击播放短片，或欣赏静态画面。'
        }
      } finally { item.pending = false; reflect() }
    }
    video.addEventListener('play', reflect)
    video.addEventListener('pause', reflect)
    video.addEventListener('error', () => {
      item.failed = true
      video.pause()
      container.classList.add('has-video-error')
      status.textContent = '短片暂不可用，已展示静态画面。'
      button.hidden = true
    })
    button.addEventListener('click', () => {
      if (!video.paused || item.pending) item.userPaused = true
      else { item.userPaused = false; item.userAllowed = true; item.visible = true; status.textContent = '' }
      item.update()
    })
  }
  document.querySelectorAll('[data-motion-film]').forEach(initialize)
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        const item = films.find(film => film.container === entry.target)
        if (item) { item.visible = entry.isIntersecting; item.update() }
      }
    }, { threshold: 0.15 })
    films.forEach(item => observer.observe(item.container))
    if (!gently()) {
      const reveals = new IntersectionObserver(entries => {
        for (const entry of entries) if (entry.isIntersecting) {
          entry.target.classList.add('motion-entered')
          reveals.unobserve(entry.target)
        }
      }, { threshold: 0.12 })
      document.querySelectorAll('[data-motion-reveal]').forEach(element => reveals.observe(element))
    }
  }
  const refresh = () => films.forEach(item => item.update())
  document.addEventListener('visibilitychange', refresh)
  window.addEventListener('pagehide', () => films.forEach(item => item.video.pause()))
  reduced.addEventListener?.('change', () => { films.forEach(item => { item.userAllowed = false }); refresh() })
  connection?.addEventListener?.('change', () => { films.forEach(item => { item.userAllowed = false }); refresh() })
})()
