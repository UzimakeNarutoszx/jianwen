/* Foreground reading only. Per-tab session storage keeps retries across reloads. */
(function () {
  'use strict'
  let target = null, last = Date.now(), interaction = last, segment = null
  let token = window.getToken(), owner = window.getSessionUser()?.id
  let queue = [], sending = false
  const key = () => `jianwen_reading_queue_${owner}`
  function persist() { try { sessionStorage.setItem(key(), JSON.stringify(queue)) } catch {} }
  function restore() {
    if (!owner || !token) return
    try { queue = JSON.parse(sessionStorage.getItem(key()) || '[]').filter(p => Date.now() - Date.parse(p.ended_at) < 7 * 86400000) } catch { queue = [] }
  }
  function identity() {
    const current = window.getToken(), id = window.getSessionUser()?.id
    if (current !== token || id !== owner) {
      segment = null
      queue = []
      try { sessionStorage.removeItem(key()) } catch {}
      token = current; owner = id; last = Date.now(); interaction = last
      restore()
    }
    return Boolean(token && owner)
  }
  function close() {
    if (!segment) return
    queue.push({ ...segment, batch_id: crypto.randomUUID() })
    segment = null
    persist()
  }
  function sample() {
    const now = Date.now(), start = last
    last = now
    const previousToken = token
    if (!identity() || previousToken !== token) return
    const elapsed = now - start
    if (!target || document.hidden || !document.hasFocus() || elapsed <= 0 || elapsed > 2500 || start >= interaction + 60000) {
      close(); return
    }
    const end = Math.min(now, interaction + 60000)
    if (segment && Date.parse(segment.ended_at) !== start) close()
    if (segment && end - Date.parse(segment.started_at) > 15000) close()
    if (!segment) segment = { ...target, started_at: new Date(start).toISOString(), ended_at: new Date(start).toISOString() }
    segment.ended_at = new Date(end).toISOString()
    segment.scroll_progress = target.scroll_progress || 0
    if (end - Date.parse(segment.started_at) >= 14000) close()
  }
  async function upload() {
    if (sending || !identity() || !queue.length) return
    sending = true
    const expectedToken = token
    try {
      while (queue.length && window.getToken() === expectedToken) {
        const next = queue[0]
        try { await window.jianwenApi.readingActivity(next) }
        catch (error) {
          // Invalid/deleted content cannot be repaired by retry; network failures can.
          if (error.status === 404 || error.status === 422) { queue.shift(); persist(); continue }
          break
        }
        if (window.getToken() !== expectedToken) break
        queue.shift(); persist()
      }
    } finally { sending = false; identity() }
  }
  window.jianwenReading = {
    setTarget(value) { sample(); close(); target = value; last = Date.now(); interaction = last; upload() },
    setProgress(value) { if (target) target.scroll_progress = Math.round(value) }
  }
  for (const event of ['pointerdown', 'pointermove', 'scroll', 'touchstart', 'keydown']) {
    window.addEventListener(event, () => { sample(); interaction = Date.now() }, { passive: true })
  }
  for (const event of ['blur', 'focus', 'pageshow']) window.addEventListener(event, () => { sample(); close(); upload() })
  document.addEventListener('visibilitychange', () => { sample(); close(); upload() })
  window.addEventListener('pagehide', () => { sample(); close(); upload() })
  window.addEventListener('storage', identity)
  window.addEventListener('jianwen-session-change', identity)
  restore()
  setInterval(sample, 1000)
  setInterval(() => { sample(); close(); upload() }, 15000)
  upload()
})()
