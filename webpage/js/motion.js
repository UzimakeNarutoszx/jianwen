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
    const variant = 'ajin-ambient'
    container.style.backgroundImage = `url("${new URL(`${variant}-poster.jpg`, assets).href}")`
    const video = document.createElement('video')
    video.className = 'motion-film-video'
    video.poster = new URL(`${variant}-poster.jpg`, assets).href
    video.muted = true
    video.defaultMuted = true
    video.loop = false
    video.playsInline = true
    video.preload = 'none'
    video.setAttribute('aria-hidden', 'true')
    video.setAttribute('tabindex', '-1')
    video.setAttribute('playsinline', '')
    container.append(video)
    const item = { container, video, visible: false, finished: false, failed: false, pending: false }
    films.push(item)

    function reflect() { container.classList.toggle('is-playing', !video.paused) }
    item.update = async () => {
      const allowed = item.visible && !document.hidden && !item.finished && !gently() && !item.failed
      if (!allowed) { video.pause(); reflect(); return }
      if (!video.paused || item.pending) return
      if (!video.getAttribute('src')) video.src = new URL(`${variant}.mp4`, assets).href
      item.pending = true
      try {
        await video.play()
        if (!item.visible || document.hidden || item.finished || gently()) video.pause()
      } catch (error) {
        if (error.name !== 'AbortError') {
          item.failed = true
        }
      } finally { item.pending = false; reflect() }
    }
    video.addEventListener('play', reflect)
    video.addEventListener('pause', reflect)
    video.addEventListener('error', () => {
      item.failed = true
      video.pause()
      container.classList.add('has-video-error')

    })
    video.addEventListener('timeupdate', () => {
      if (video.currentTime >= 4.5) { item.finished = true; video.pause(); reflect() }
    })

  }
  document.querySelectorAll('[data-motion-film=ambient]').forEach(initialize)
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
  reduced.addEventListener?.('change', refresh)
  connection?.addEventListener?.('change', refresh)
})()
