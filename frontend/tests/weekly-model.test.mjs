import assert from 'node:assert/strict'
import fs from 'node:fs'
// The uni-app sources are bundled as ESM without setting package-wide type:module.
const source = fs.readFileSync(new URL('../utils/weekly-model.js', import.meta.url))
const { beijingWeekStart, weekForDate, shiftDate, selectEpisodes, publishedEpisodes, safePublicPath, timestamp } = await import(`data:text/javascript;base64,${source.toString('base64')}`)
assert.equal(beijingWeekStart(new Date('2026-01-04T15:59:59Z')), '2025-12-29')
assert.equal(beijingWeekStart(new Date('2026-01-04T16:00:00Z')), '2026-01-05')
assert.equal(weekForDate('2026-01-01'), '2025-12-29')
assert.equal(weekForDate('2026-10-18'), '2026-10-12')
assert.equal(shiftDate('2025-12-29', 7), '2026-01-05')
assert.equal(shiftDate('2026-01-05', -7), '2025-12-29')
const now = new Date('2026-10-17T12:00:00Z')
const episodes = [
  { id: 'old', status: 'published', video: 'old.mp4', publishedAt: '2026-10-01', weekStart: '2026-09-28' },
  { id: 'new', status: 'published', video: 'new.mp4', publishedAt: '2026-10-17T10:00:00Z', weekStart: '2026-10-12' },
  { id: 'future', status: 'published', video: 'future.mp4', publishedAt: '2026-10-18', weekStart: '2026-10-12' },
  { id: 'draft', status: 'draft', video: 'draft.mp4', publishedAt: '2026-10-17', weekStart: '2026-10-12' },
  { id: 'invalid', status: 'published', video: 'invalid.mp4', publishedAt: 'invalid', weekStart: '2026-10-12' },
  { id: 'no-video', status: 'published', publishedAt: '2026-10-16', weekStart: '2026-10-12' }
]
assert.deepEqual(publishedEpisodes({ episodes }, now).map(item => item.id), ['new', 'old'])
const selected = selectEpisodes({ episodes }, 'old', now)
assert.equal(selected.pinned.id, 'new')
assert.equal(selected.selected.id, 'old')
assert.deepEqual(selected.archive.map(item => item.id), ['old'])
assert.equal(selectEpisodes({ episodes }, '', now).label, '本周视频')
assert.equal(selectEpisodes({ episodes }, 'missing', now).unknownId, true)
assert.equal(selectEpisodes({ episodes: [episodes[0]] }, '', now).label, '最近一期')
assert.equal(selectEpisodes({}, '', now).selected, null)
for (const unsafe of ['javascript:alert(1)', 'data:text/html,unsafe', 'file:///tmp/test', '//host/foo']) assert.equal(safePublicPath(unsafe), '')
for (const safe of ['assets/weekly-video/episode.mp4', 'https://example.com/source', 'jianwen/article.html?id=one']) assert.equal(safePublicPath(safe), safe)
assert.equal(timestamp(293.83), '4:53')
assert.equal(timestamp(-1), '0:00')
console.log('Weekly model checks passed (Beijing boundaries, publication, fallback, archive, URL and duration).')
