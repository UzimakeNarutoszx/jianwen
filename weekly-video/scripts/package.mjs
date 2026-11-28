import {readFile, writeFile, mkdir, stat} from 'node:fs/promises'
import {createHash} from 'node:crypto'
import {fileURLToPath, pathToFileURL} from 'node:url'
import {resolve, relative} from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const repoRoot = resolve(root, '..')

export const MAX_TITLE_LENGTH = 30
export const DURATION_TOLERANCE_SECONDS = 0.2
export const DISCLAIMER = 'AI 辅助整理，信息以官方来源为准'
export const SIGNATURE = '见闻'

const epilogue = `\n\n——\n署名：${SIGNATURE}\n免责声明：${DISCLAIMER}`

export function formatMmSs(seconds) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) {
    throw new TypeError(`seconds must be a non-negative finite number, got: ${seconds}`)
  }
  const total = Math.floor(seconds)
  const minutes = Math.floor(total / 60)
  return `${String(minutes).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

export function safeTitle(rawTitle, maxLength = MAX_TITLE_LENGTH) {
  const text = String(rawTitle ?? '').replace(/\s+/g, ' ').trim()
  if (!text) throw new Error('标题不能为空')
  const characters = Array.from(text)
  return characters.length <= maxLength ? text : characters.slice(0, maxLength).join('')
}

export function timelineChapters(timeline) {
  return (timeline.chapters ?? []).map(({title, seconds}) => ({title, seconds}))
}

export function soundtrackCredit(timeline, catalogEpisode = null) {
  return timeline.soundtrack?.credit ?? catalogEpisode?.music ?? '未标注配乐'
}

export function countVttCues(text) {
  return String(text)
    .split(/\r?\n/)
    .filter(line => line.includes('-->')).length
}

export function buildReleaseCopy({id, timeline, catalogEpisode = null}) {
  const title = safeTitle(timeline.title)
  const description = String(timeline.description ?? '').trim() || `${title}，见闻每周视频。`
  const chapters = timelineChapters(timeline)
  const sources = timeline.sources ?? []
  const lines = [
    `见闻每周视频 · 第 ${timeline.number ?? '?'} 期（${id}）`,
    '',
    `标题：${title}`,
    '',
    '简介：',
    description,
    '',
    '章节：',
    ...chapters.map(chapter => `${formatMmSs(chapter.seconds)} ${chapter.title}`),
    '',
    '来源：',
    ...sources.map(source => `- ${source.date ?? '日期未标注'} ${source.title ?? '未命名来源'}`.trim()),
    '',
    `配乐：${soundtrackCredit(timeline, catalogEpisode)}`
  ]
  return `${lines.join('\n')}${epilogue}\n`
}

export function buildManifest({id, timeline, files, generatedAt}) {
  return {
    id,
    durationSeconds: timeline.durationSeconds,
    chapters: timelineChapters(timeline),
    cueCount: (timeline.cues ?? []).length,
    files,
    generatedAt,
    platforms: []
  }
}

const REQUIRED_FILES = ['video', 'cover', 'captions']

export function validatePackage({id, timeline, catalogEpisode, vttCueCount, files = {}, manifest = null}) {
  const errors = []
  if (!timeline || timeline.id !== id) errors.push(`timeline 与 ${id} 不匹配: ${timeline?.id ?? '(missing)'}`)
  if (!Array.isArray(timeline?.cues) || timeline.cues.length === 0) errors.push('timeline 没有字幕 cues')
  if (!catalogEpisode) {
    errors.push(`catalog 中找不到 ${id}`)
  } else {
    const drift = Math.abs(timeline.durationSeconds - catalogEpisode.durationSeconds)
    if (!(drift <= DURATION_TOLERANCE_SECONDS)) {
      errors.push(`时长与 catalog 相差 ${drift.toFixed(3)}s，超过 ${DURATION_TOLERANCE_SECONDS}s`)
    }
    const expectedChapters = timelineChapters(timeline)
    if (JSON.stringify(expectedChapters) !== JSON.stringify(catalogEpisode.chapters)) {
      errors.push('catalog 章节与 timeline 不一致')
    }
  }
  for (const name of REQUIRED_FILES) {
    const file = files[name]
    if (!file) errors.push(`缺少文件：${name}`)
    else if (!file.exists) errors.push(`缺少文件：${name} (${file.path ?? '路径未知'})`)
  }
  for (const [name, file] of Object.entries(files)) {
    if (!file?.exists) continue
    const recorded = manifest?.files?.[name]
    if (recorded?.sha256 && file.sha256 && recorded.sha256 !== file.sha256) {
      errors.push(`文件哈希不一致：${name}`)
    }
  }
  if (vttCueCount !== (timeline?.cues ?? []).length) {
    errors.push(`VTT 条目数 ${vttCueCount} 与 timeline cues ${(timeline?.cues ?? []).length} 不一致`)
  }
  if (manifest) {
    if (manifest.id !== id) errors.push(`发布清单 id ${manifest.id ?? '(missing)'} 与 ${id} 不一致`)
    if (manifest.cueCount !== (timeline?.cues ?? []).length) {
      errors.push(`发布清单 cueCount ${manifest.cueCount ?? '(missing)'} 与 cues ${(timeline?.cues ?? []).length} 不一致`)
    }
    if (manifest.durationSeconds !== timeline?.durationSeconds) {
      errors.push(`发布清单 durationSeconds ${manifest.durationSeconds ?? '(missing)'} 与 timeline ${timeline?.durationSeconds} 不一致`)
    }
    if (JSON.stringify(manifest.chapters) !== JSON.stringify(timelineChapters(timeline))) {
      errors.push('发布清单 chapters 与 timeline 不一致')
    }
    if (!Array.isArray(manifest.platforms) || manifest.platforms.length !== 0) {
      errors.push('发布清单 platforms 必须为空数组')
    }
    if (manifest.files && typeof manifest.files === 'object') {
      for (const name of Object.keys(manifest.files)) {
        if (!files[name]?.exists) errors.push(`发布清单中的文件不存在：${name}`)
      }
    }
  }
  return {ok: errors.length === 0, errors}
}

const sha256 = async path => {
  const hash = createHash('sha256')
  hash.update(await readFile(path))
  return hash.digest('hex')
}

const fileState = async (name, path) => {
  const absolute = resolve(repoRoot, path)
  try {
    const info = await stat(absolute)
    if (!info.isFile()) return {name, path, absolute, exists: false}
    return {name, path, absolute, exists: true, sha256: await sha256(absolute)}
  } catch {
    return {name, path, absolute, exists: false}
  }
}

const beijingTimestamp = (date = new Date()) => {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })
      .formatToParts(date)
      .map(part => [part.type, part.value])
  )
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}.${String(date.getMilliseconds()).padStart(3, '0')}+08:00`
}

const findCatalogEpisode = (catalog, id) => (catalog.episodes ?? []).find(item => item.id === id) ?? null

const loadEpisode = async id => {
  const timeline = JSON.parse(await readFile(resolve(root, 'episodes', id, 'timeline.json'), 'utf8'))
  const catalog = JSON.parse(await readFile(resolve(repoRoot, 'webpage/data/weekly-videos.json'), 'utf8'))
  const catalogEpisode = findCatalogEpisode(catalog, id)
  const mediaBase = `webpage/assets/weekly-video/${id}`
  const files = {}
  for (const [name, file] of Object.entries({
    video: `${mediaBase}/episode.mp4`,
    cover: `${mediaBase}/cover.jpg`,
    captions: `${mediaBase}/captions.vtt`
  })) {
    const state = await fileState(name, file)
    files[name] = {path: state.path, exists: state.exists, ...(state.sha256 ? {sha256: state.sha256} : {})}
    files[name].absolute = state.absolute
  }
  let vttCueCount = 0
  if (files.captions.exists) {
    vttCueCount = countVttCues(await readFile(files.captions.absolute, 'utf8'))
  }
  return {timeline, catalogEpisode, files, vttCueCount}
}

const manifestPathFor = id => resolve(repoRoot, 'output/weekly-video', id, 'package/发布清单.json')
const copyPathFor = id => resolve(repoRoot, 'output/weekly-video', id, 'package/发布文案.txt')

const main = async () => {
  const args = process.argv.slice(2)
  const known = new Set(['--check'])
  for (const arg of args) if (arg.startsWith('-') && !known.has(arg)) throw new Error(`Unknown option: ${arg}`)
  const check = args.includes('--check')
  const positional = args.filter(arg => !arg.startsWith('-'))
  if (positional.length > 1) throw new Error(`只接受一个期号参数，收到: ${positional.join(', ')}`)
  const fallback = JSON.parse(await readFile(resolve(root, 'current.json'), 'utf8')).id
  const id = positional[0] ?? fallback
  if (!/^\d{4}-W\d{2}$/.test(id)) throw new Error(`期号格式应为 YYYY-Www，收到: ${id}`)
  const {timeline, catalogEpisode, files, vttCueCount} = await loadEpisode(id)

  const packageDir = resolve(repoRoot, 'output/weekly-video', id, 'package')
  const copyPath = copyPathFor(id)
  const manifestPath = manifestPathFor(id)
  const copyRelative = relative(repoRoot, copyPath)
  const copyState = await fileState('copy', copyRelative)
  files.copy = {path: copyState.path, exists: copyState.exists, ...(copyState.sha256 ? {sha256: copyState.sha256} : {})}

  if (check) {
    let manifest = null
    const manifestState = await fileState('manifest', relative(repoRoot, manifestPath))
    if (manifestState.exists) manifest = JSON.parse(await readFile(manifestState.absolute, 'utf8'))
    const result = validatePackage({id, timeline, catalogEpisode, vttCueCount, files, manifest})
    if (!manifestState.exists) result.errors.push(`缺少发布清单：${relative(repoRoot, manifestPath)}（先运行 node scripts/package.mjs ${id}）`)
    if (result.errors.length > 0) {
      console.error(`[package] 检查失败：${id}`)
      for (const error of result.errors) console.error(`  - ${error}`)
      process.exitCode = 1
      return
    }
    console.log(`[package] 检查通过：${id} duration=${timeline.durationSeconds}s chapters=${timeline.chapters.length} cues=${timeline.cues.length} vtt=${vttCueCount}`)
    for (const [name, file] of Object.entries(files)) console.log(`  ${name}: ${file.path} sha256=${file.sha256}`)
    return
  }

  const preflight = validatePackage({id, timeline, catalogEpisode, vttCueCount, files: {
    video: files.video,
    cover: files.cover,
    captions: files.captions
  }})
  if (!preflight.ok) {
    console.error(`[package] 无法生成发布包：${id}`)
    for (const error of preflight.errors) console.error(`  - ${error}`)
    process.exitCode = 1
    return
  }
  await mkdir(packageDir, {recursive: true})
  const releaseCopy = buildReleaseCopy({id, timeline, catalogEpisode})
  await writeFile(copyPath, releaseCopy)
  files.copy.sha256 = await sha256(copyPath)
  files.copy.exists = true
  const generatedAt = beijingTimestamp()
  const manifest = buildManifest({id, timeline, files: {
    video: {path: files.video.path, sha256: files.video.sha256},
    cover: {path: files.cover.path, sha256: files.cover.sha256},
    captions: {path: files.captions.path, sha256: files.captions.sha256},
    copy: {path: files.copy.path, sha256: files.copy.sha256}
  }, generatedAt})
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
  console.log(`[package] 发布包已生成：${id}`)
  console.log(`  ${copyRelative}`)
  console.log(`  ${relative(repoRoot, manifestPath)}`)
  for (const [name, file] of Object.entries(manifest.files)) console.log(`  ${name}: ${file.path} sha256=${file.sha256}`)
}

const invokedDirectly = process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url
if (invokedDirectly) {
  main().catch(error => {
    console.error(`[package] ${error.message}`)
    process.exitCode = 1
  })
}
