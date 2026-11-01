// Mirrors the website catalogue rules. Calendar weeks always use Beijing time.
export function beijingWeekStart(now = new Date()) {
  const local = new Date(new Date(now).getTime() + 8 * 3600000)
  local.setUTCDate(local.getUTCDate() - (local.getUTCDay() + 6) % 7)
  return local.toISOString().slice(0, 10)
}
export function shiftDate(date, days) {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * 86400000).toISOString().slice(0, 10)
}
export function weekForDate(date) {
  const value = new Date(`${date}T00:00:00Z`)
  return shiftDate(date, -(value.getUTCDay() + 6) % 7)
}
export function publishedEpisodes(catalog = {}, now = new Date()) {
  return (Array.isArray(catalog.episodes) ? catalog.episodes : []).filter(item =>
    item.status === 'published' && item.video && item.publishedAt &&
    Number.isFinite(Date.parse(item.publishedAt)) && Date.parse(item.publishedAt) <= now.getTime()
  ).sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt))
}
export function selectEpisodes(catalog = {}, requestedId = '', now = new Date()) {
  const episodes = publishedEpisodes(catalog, now)
  const current = beijingWeekStart(now)
  const pinned = episodes.find(item => item.weekStart === current) || episodes[0] || null
  const selected = episodes.find(item => item.id === requestedId) || pinned
  return {
    pinned, selected,
    unknownId: Boolean(requestedId && !episodes.some(item => item.id === requestedId)),
    label: selected?.weekStart === current ? '本周视频' : selected?.id === pinned?.id ? '最近一期' : '往期节目',
    archive: episodes.filter(item => item.id !== pinned?.id)
  }
}
export function timestamp(value = 0) {
  const seconds = Math.max(0, Number(value) || 0)
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
}
export function safePublicPath(value) {
  if (typeof value !== 'string' || !value.trim() || /^(?:javascript|data|file):/i.test(value) || value.startsWith('//')) return ''
  return /^(?:https?:\/\/|[^:]+$)/i.test(value) ? value : ''
}
