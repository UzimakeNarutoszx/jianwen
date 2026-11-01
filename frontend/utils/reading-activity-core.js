// Dependency-injected clock, storage and transport keep timing/identity rules testable.
export function createReadingCollector({ now = Date.now, identity, read, write, send,
  uuid = () => `${now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}` }) {
  let session = {}, target = null, foreground = false, segment = null
  let last = now(), interaction = last, queue = [], sending = false, blockedToken = ''
  const key = owner => `jianwen_reading_queue_${owner}`
  function persist() { if (session.owner) write(key(session.owner), queue) }
  function syncIdentity() {
    const next = identity() || {}
    if (next.token !== session.token || next.owner !== session.owner) {
      // Seal under the preceding owner before loading another account's queue.
      close()
      session = next
      const saved = next.owner && next.token ? read(key(next.owner)) : []
      queue = (Array.isArray(saved) ? saved : []).filter(item =>
        now() - Date.parse(item.ended_at) < 7 * 86400000 && Date.parse(item.ended_at) <= now())
      last = now(); interaction = last
    }
    return Boolean(session.owner && session.token && session.token !== blockedToken)
  }
  function close() {
    if (!segment) return
    if (Date.parse(segment.ended_at) > Date.parse(segment.started_at)) {
      queue.push({ ...segment, batch_id: uuid() }); persist()
    }
    segment = null
  }
  function sample() {
    const end = now(), start = last
    if (!syncIdentity()) { last = end; segment = null; return }
    // Identity changes reset last: never attribute another account's preceding interval.
    if (last !== start) return
    last = end
    if (!target || !foreground || end <= start || end - start > 2500 || start >= interaction + 60000) {
      close(); return
    }
    const capped = Math.min(end, interaction + 60000)
    if (segment && (Date.parse(segment.ended_at) !== start || capped - Date.parse(segment.started_at) > 15000)) close()
    if (!segment) segment = { ...target, started_at: new Date(start).toISOString() }
    segment.ended_at = new Date(capped).toISOString()
    segment.scroll_progress = target.scroll_progress || 0
    if (capped - Date.parse(segment.started_at) >= 14000) close()
  }
  async function upload() {
    if (sending || !syncIdentity() || !queue.length) return
    sending = true
    const expected = { ...session }
    try {
      while (queue.length && syncIdentity() && session.token === expected.token && session.owner === expected.owner) {
        const item = queue[0]
        try { await send(item, expected.token) }
        catch (error) {
          syncIdentity()
          if (session.token !== expected.token || session.owner !== expected.owner) break
          if (error.status === 404 || error.status === 422) { queue.shift(); persist(); continue }
          // Session clearing and the login redirect are centralised in utils/api.js
          // (handleUnauthorized); here we only stop collecting under the dead token.
          if (Number(error.status) === 401) { blockedToken = expected.token; segment = null }
          break
        }
        syncIdentity()
        if (session.token !== expected.token || session.owner !== expected.owner) break
        queue.shift(); persist()
      }
    } finally { sending = false }
  }
  return {
    sample, upload,
    setTarget(value) { sample(); close(); target = value; last = now(); interaction = last; upload() },
    clear() { sample(); close(); target = null; upload() },
    resume() { syncIdentity(); foreground = true; last = now(); interaction = last; upload() },
    pause() { sample(); close(); foreground = false; upload() },
    interact() { sample(); interaction = now() },
    progress(value) { if (target) target.scroll_progress = Math.max(0, Math.min(100, Math.round(value))) },
    flush() { sample(); close(); return upload() }
  }
}
