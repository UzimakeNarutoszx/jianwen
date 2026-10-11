// 宣传片卡片：带控件、用户点播（有旁白，不自动播放）
// 滚出视口或切到后台时暂停；减少动态效果或省流量模式下不预加载；加载失败只留海报
;(() => {
  const films = document.querySelectorAll('[data-promo-film]')
  if (!films.length) return
  const quiet = () => matchMedia('(prefers-reduced-motion: reduce)').matches || Boolean(navigator.connection?.saveData)

  films.forEach(film => {
    const video = film.querySelector('video')
    if (!video) return
    video.preload = quiet() ? 'none' : 'metadata'
    video.addEventListener('error', () => film.classList.add('has-video-error'), true)
    video.querySelectorAll('source').forEach(source => source.addEventListener('error', () => film.classList.add('has-video-error')))
    video.addEventListener('play', () => film.classList.add('is-playing'))
    video.addEventListener('pause', () => film.classList.remove('is-playing'))
    video.addEventListener('ended', () => film.classList.remove('is-playing'))

    if ('IntersectionObserver' in window) {
      new IntersectionObserver(entries => entries.forEach(entry => {
        if (!entry.isIntersecting && !video.paused) video.pause()
      }), { threshold: 0.2 }).observe(film)
    }
  })

  const pauseAll = () => films.forEach(film => { const v = film.querySelector('video'); if (v && !v.paused) v.pause() })
  document.addEventListener('visibilitychange', () => { if (document.hidden) pauseAll() })
  addEventListener('pagehide', pauseAll)
})()
