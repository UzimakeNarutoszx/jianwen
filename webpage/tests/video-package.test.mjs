import assert from 'node:assert/strict'
import test from 'node:test'
import {readFile} from 'node:fs/promises'
import {
  DISCLAIMER,
  MAX_TITLE_LENGTH,
  buildManifest,
  buildReleaseCopy,
  countVttCues,
  formatMmSs,
  safeTitle,
  validatePackage
} from '../../weekly-video/scripts/package.mjs'

const timeline = JSON.parse(await readFile(new URL('../../weekly-video/episodes/2026-W47/timeline.json', import.meta.url), 'utf8'))
const catalog = JSON.parse(await readFile(new URL('../data/weekly-videos.json', import.meta.url), 'utf8'))
const catalogEpisode = catalog.episodes.find(item => item.id === timeline.id)
const vttText = await readFile(new URL('../assets/weekly-video/2026-W47/captions.vtt', import.meta.url), 'utf8')
const vttCueCount = countVttCues(vttText)

const mediaFiles = ({exists = true} = {}) => ({
  video: {path: `webpage/assets/weekly-video/${timeline.id}/episode.mp4`, exists, sha256: 'a'.repeat(64)},
  cover: {path: `webpage/assets/weekly-video/${timeline.id}/cover.jpg`, exists, sha256: 'b'.repeat(64)},
  captions: {path: `webpage/assets/weekly-video/${timeline.id}/captions.vtt`, exists, sha256: 'c'.repeat(64)}
})

test('chapter timestamps use mm:ss and reject invalid seconds', () => {
  assert.equal(formatMmSs(0), '00:00')
  assert.equal(formatMmSs(5.9), '00:05')
  assert.equal(formatMmSs(65.5), '01:05')
  assert.equal(formatMmSs(3599.9), '59:59')
  assert.equal(formatMmSs(3600), '60:00')
  for (const invalid of [-1, Number.NaN, Number.POSITIVE_INFINITY, '12']) {
    assert.throws(() => formatMmSs(invalid), TypeError)
  }
})

test('titles are trimmed and capped at 30 characters', () => {
  assert.equal(safeTitle('  从深圳，到一个入口  '), '从深圳，到一个入口')
  assert.equal(safeTitle('见'.repeat(MAX_TITLE_LENGTH)), '见'.repeat(MAX_TITLE_LENGTH))
  assert.equal(Array.from(safeTitle('见'.repeat(MAX_TITLE_LENGTH + 5))).length, MAX_TITLE_LENGTH)
  assert.throws(() => safeTitle('   '), /标题不能为空/)
  assert.throws(() => safeTitle(null), /标题不能为空/)
})

test('release copy carries title, chapters, sources, signature, music credit and disclaimer', () => {
  const copy = buildReleaseCopy({id: timeline.id, timeline, catalogEpisode})
  const titleLine = copy.split('\n').find(line => line.startsWith('标题：'))
  assert.ok(titleLine, 'release copy has a title line')
  assert.ok(Array.from(titleLine.slice('标题：'.length)).length <= MAX_TITLE_LENGTH)
  assert.ok(copy.includes(timeline.title))
  assert.ok(copy.includes(timeline.description))
  assert.ok(copy.includes('章节：'))
  for (const chapter of timeline.chapters) {
    assert.ok(copy.includes(`${formatMmSs(chapter.seconds)} ${chapter.title}`), `chapter line for ${chapter.title}`)
  }
  assert.ok(copy.includes('来源：'))
  for (const source of timeline.sources) {
    assert.ok(copy.includes(source.title), `source title ${source.title}`)
    assert.ok(copy.includes(source.date), `source date ${source.date}`)
  }
  assert.ok(copy.includes(`署名：${'见闻'}`))
  assert.ok(copy.includes(`配乐：${timeline.soundtrack.credit}`))
  assert.ok(copy.includes(DISCLAIMER))
})

test('the real W47 caption VTT has exactly one entry per timeline cue', () => {
  assert.equal(vttCueCount, timeline.cues.length)
  assert.ok(vttCueCount > 0)
})

test('a consistent package validates, including duration tolerance and manifest fields', () => {
  const files = mediaFiles()
  const manifest = buildManifest({id: timeline.id, timeline, files, generatedAt: '2026-11-28T19:30:00.000+08:00'})
  const result = validatePackage({id: timeline.id, timeline, catalogEpisode, vttCueCount, files, manifest})
  assert.deepEqual(result.errors, [])
  assert.equal(result.ok, true)
  assert.equal(manifest.platforms.length, 0)
  assert.equal(manifest.cueCount, timeline.cues.length)
  assert.deepEqual(manifest.chapters, timeline.chapters.map(({title, seconds}) => ({title, seconds})))
  assert.equal(manifest.durationSeconds, timeline.durationSeconds)
  const withinTolerance = validatePackage({
    id: timeline.id,
    timeline,
    catalogEpisode: {...catalogEpisode, durationSeconds: catalogEpisode.durationSeconds + 0.15},
    vttCueCount,
    files
  })
  assert.equal(withinTolerance.ok, true)

  const overTolerance = validatePackage({
    id: timeline.id,
    timeline,
    catalogEpisode: {...catalogEpisode, durationSeconds: catalogEpisode.durationSeconds + 0.21},
    vttCueCount,
    files
  })
  assert.equal(overTolerance.ok, false)
  assert.ok(overTolerance.errors.some(error => error.includes('时长')), overTolerance.errors.join('; '))
})

test('validation rejects catalog chapter, duration and VTT mismatches', () => {
  const files = mediaFiles()
  const shiftedChapters = timeline.chapters.map((chapter, index) => index === 1 ? {...chapter, seconds: chapter.seconds + 1} : chapter)
  const chapterDrift = validatePackage({
    id: timeline.id,
    timeline: {...timeline, chapters: shiftedChapters},
    catalogEpisode,
    vttCueCount,
    files
  })
  assert.equal(chapterDrift.ok, false)
  assert.ok(chapterDrift.errors.some(error => error.includes('章节')), chapterDrift.errors.join('; '))

  const durationDrift = validatePackage({
    id: timeline.id,
    timeline,
    catalogEpisode: {...catalogEpisode, durationSeconds: catalogEpisode.durationSeconds + 0.3},
    vttCueCount,
    files
  })
  assert.equal(durationDrift.ok, false)
  assert.ok(durationDrift.errors.some(error => error.includes('时长')), durationDrift.errors.join('; '))

  const cueDrift = validatePackage({id: timeline.id, timeline, catalogEpisode, vttCueCount: vttCueCount - 1, files})
  assert.equal(cueDrift.ok, false)
  assert.ok(cueDrift.errors.some(error => error.includes('VTT')), cueDrift.errors.join('; '))
})

test('validation rejects missing media files and a non-empty platform list', () => {
  const files = mediaFiles()
  files.video.exists = false
  const missing = validatePackage({id: timeline.id, timeline, catalogEpisode, vttCueCount, files})
  assert.equal(missing.ok, false)
  assert.ok(missing.errors.some(error => error.includes('video')), missing.errors.join('; '))

  const validFiles = mediaFiles()
  const manifest = buildManifest({id: timeline.id, timeline, files: validFiles, generatedAt: '2026-11-28T19:30:00.000+08:00'})
  manifest.platforms = ['bilibili']
  const platforms = validatePackage({id: timeline.id, timeline, catalogEpisode, vttCueCount, files: validFiles, manifest})
  assert.equal(platforms.ok, false)
  assert.ok(platforms.errors.some(error => error.includes('platforms')), platforms.errors.join('; '))
})
