// Public, account-independent programme selection. Week boundaries are Beijing time.
export function beijingWeekStart(now = new Date()) {
  const local = new Date(now.getTime() + 8 * 60 * 60 * 1000)
  local.setUTCDate(local.getUTCDate() - (local.getUTCDay() + 6) % 7)
  return local.toISOString().slice(0, 10)
}

export function publishedEpisodes(catalog, now = new Date()) {
  return (catalog.episodes || []).filter(episode =>
    episode.status === 'published' && episode.video && episode.publishedAt &&
    Number.isFinite(Date.parse(episode.publishedAt)) && Date.parse(episode.publishedAt) <= now.getTime()
  ).sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt))
}

export function selectEpisodes(catalog, requestedId, now = new Date()) {
  const episodes = publishedEpisodes(catalog, now)
  const currentWeek = beijingWeekStart(now)
  const pinned = episodes.find(episode => episode.weekStart === currentWeek) || episodes[0] || null
  const selected = episodes.find(episode => episode.id === requestedId) || pinned
  return {
    pinned, selected,
    unknownId: Boolean(requestedId && !episodes.some(episode => episode.id === requestedId)),
    label: selected?.weekStart === currentWeek ? '本周视频' : selected && selected.id === pinned?.id ? '最近一期' : '往期节目',
    // The pinned episode is never duplicated in the archive, even while watching an older one.
    archive: episodes.filter(episode => episode.id !== pinned?.id)
  }
}

export function mediaUrl(value) {
  if (typeof value !== 'string' || !value.trim()) return ''
  try {
    const url = new URL(value, 'https://jianwen.invalid/')
    return ['https:', 'http:'].includes(url.protocol) ? value : ''
  } catch { return '' }
}

export function timestamp(seconds) {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
}
