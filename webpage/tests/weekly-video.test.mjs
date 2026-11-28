import assert from 'node:assert/strict'
import test from 'node:test'
import {readFile} from 'node:fs/promises'
import {beijingWeekStart, selectEpisodes, mediaUrl} from '../js/weekly-video-model.mjs'

const now = new Date('2026-10-17T10:30:00Z')
const episode = (id, weekStart, publishedAt) => ({id, weekStart, publishedAt, video:'assets/test.mp4', status:'published'})
const old = episode('2026-W41', '2026-10-05', '2026-10-11T12:00:00+08:00')
const current = episode('2026-W42', '2026-10-12', '2026-10-17T18:00:00+08:00')

test('weeks roll over at Monday 00:00 Beijing, including year boundaries', () => {
  assert.equal(beijingWeekStart(new Date('2026-10-18T15:59:59Z')), '2026-10-12')
  assert.equal(beijingWeekStart(new Date('2026-10-18T16:00:00Z')), '2026-10-19')
  assert.equal(beijingWeekStart(new Date('2027-01-01T00:00:00Z')), '2026-12-28')
})

test('current week is pinned; past episodes stay in publication order without duplicating the pin', () => {
  const catalog = {episodes:[old, current]}
  const result = selectEpisodes(catalog, null, now)
  assert.equal(result.selected.id, current.id)
  assert.equal(result.label, '本周视频')
  assert.deepEqual(result.archive.map(item => item.id), [old.id])
  const linked = selectEpisodes(catalog, old.id, now)
  assert.equal(linked.selected.id, old.id)
  assert.equal(linked.pinned.id, current.id)
  assert.equal(linked.label, '往期节目')
})

test('a week without a new release shows the latest episode honestly', () => {
  const result = selectEpisodes({episodes:[current, old]}, null, new Date('2026-10-20T00:00:00Z'))
  assert.equal(result.selected.id, current.id)
  assert.equal(result.label, '最近一期')
})

test('drafts, future releases and missing video files never become published episodes', () => {
  const result = selectEpisodes({episodes:[
    {...current, status:'draft'}, {...current, video:null},
    {...current, publishedAt:'not a date'},
    episode('future', '2026-10-19', '2026-10-20T00:00:00Z')
  ]}, 'missing', now)
  assert.equal(result.selected, null)
  assert.equal(result.unknownId, true)
  assert.deepEqual(result.archive, [])
})

test('unknown direct links recover to the pin; empty catalogs are valid', () => {
  const result = selectEpisodes({episodes:[old, current]}, 'unknown', now)
  assert.equal(result.unknownId, true)
  assert.equal(result.selected.id, current.id)
  assert.equal(selectEpisodes({}, null, now).selected, null)
})

test('links reject executable and malformed URLs', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,hello', 'file:///etc/passwd', 'http://[']) assert.equal(mediaUrl(url), '')
  assert.equal(mediaUrl('assets/video.mp4'), 'assets/video.mp4')
  assert.equal(mediaUrl('https://example.org/video.mp4'), 'https://example.org/video.mp4')
})

test('W42 has a continuous 3–5 minute timeline and non-overlapping readable subtitles', async () => {
  const episode = JSON.parse(await readFile(new URL('../../weekly-video/episodes/2026-W42/timeline.json', import.meta.url), 'utf8'))
  assert.ok(episode.durationSeconds >= 180 && episode.durationSeconds <= 300)
  assert.equal(episode.durationInFrames, Math.round(episode.durationSeconds * 30))
  assert.equal(episode.chapters.length, 5)
  assert.equal(episode.slides[0].start, 0)
  for (let index = 1; index < episode.slides.length; index++) assert.equal(episode.slides[index].start, episode.slides[index - 1].end)
  let end = 0
  for (const cue of episode.cues) {
    assert.ok(cue.start >= end && cue.end > cue.start)
    assert.ok(cue.text.length <= 30)
    end = cue.end
  }
  assert.ok(end <= episode.durationSeconds)
  for (const source of episode.sources) assert.ok(source.date <= episode.cutoff.slice(0, 10))
})

test('every published episode fits its own durationTarget (default 180–300s)', async () => {
  const catalog = JSON.parse(await readFile(new URL('../data/weekly-videos.json', import.meta.url), 'utf8'))
  const episodes = catalog.episodes.filter(item => item.status === 'published')
  assert.ok(episodes.length >= 1)
  for (const item of episodes) {
    const {min = 180, max = 300} = item.durationTarget || {}
    assert.ok(item.durationSeconds >= min && item.durationSeconds <= max, `${item.id} ${item.durationSeconds}s outside ${min}–${max}s`)
  }
})

test('published catalog time fields match each episode timeline', async () => {
  const catalog = JSON.parse(await readFile(new URL('../data/weekly-videos.json', import.meta.url), 'utf8'))
  for (const episode of catalog.episodes) {
    const timeline = JSON.parse(await readFile(new URL(`../../weekly-video/episodes/${episode.id}/timeline.json`, import.meta.url), 'utf8'))
    assert.equal(episode.durationSeconds, timeline.durationSeconds, `${episode.id}: catalog duration matches timeline`)
    assert.deepEqual(episode.chapters, timeline.chapters.map(({title, seconds}) => ({title, seconds})), `${episode.id}: catalog chapters match timeline`)
  }
})

test('published captions are ordered, non-overlapping and fit inside their episode', async () => {
  const catalog = JSON.parse(await readFile(new URL('../data/weekly-videos.json', import.meta.url), 'utf8'))
  const published = catalog.episodes.filter(episode => episode.status === 'published')
  assert.ok(published.length >= 1)
  for (const episode of published) {
    const timeline = JSON.parse(await readFile(new URL(`../../weekly-video/episodes/${episode.id}/timeline.json`, import.meta.url), 'utf8'))
    let previousEnd = 0
    for (const [index, cue] of timeline.cues.entries()) {
      assert.ok(Number.isFinite(cue.start) && cue.start >= 0, `${episode.id} cue ${index + 1}: start is a non-negative number`)
      assert.ok(cue.start >= previousEnd - 0.2, `${episode.id} cue ${index + 1}: starts ${(previousEnd - cue.start).toFixed(3)}s before the previous cue ends`)
      assert.ok(cue.end > cue.start, `${episode.id} cue ${index + 1}: end after start`)
      assert.ok(cue.text.length <= 30, `${episode.id} cue ${index + 1}: text is ${cue.text.length} characters (>30)`)
      assert.ok(cue.end <= episode.durationSeconds, `${episode.id} cue ${index + 1}: ends at ${cue.end}s after duration ${episode.durationSeconds}s`)
      previousEnd = cue.end
    }
  }
})

test('every published captions.vtt has exactly one entry per timeline cue', async () => {
  const catalog = JSON.parse(await readFile(new URL('../data/weekly-videos.json', import.meta.url), 'utf8'))
  for (const episode of catalog.episodes.filter(item => item.status === 'published')) {
    const timeline = JSON.parse(await readFile(new URL(`../../weekly-video/episodes/${episode.id}/timeline.json`, import.meta.url), 'utf8'))
    const vtt = await readFile(new URL(`../assets/weekly-video/${episode.id}/captions.vtt`, import.meta.url), 'utf8')
    const entries = vtt.split(/\r?\n/).filter(line => line.includes('-->')).length
    assert.equal(entries, timeline.cues.length, `${episode.id}: VTT entries match cues`)
  }
})
