// 离线缓存：今日清单 JSON + 当天连续音轨 MP3，落盘到 _doc/jianwen/offline/<YYYY-MM-DD>/。
//
// 这一层刻意分成两半：
// 1) 纯逻辑（日期目录、元数据规范化、新鲜度、清理计划、离线回退选择）不引用 uni/plus，
//    可以直接在 Node 里单测，见 tests/offline.test.mjs；
// 2) 平台调用全部收在 createAppPlatform()，测试通过 createOfflineCache({ platform }) 注入内存实现。
//
// 约束：缓存失败一律不抛给页面，在线优先，离线才回退；H5/小程序没有 plus 时自动降级为 unsupported。
export const OFFLINE_ROOT = '_doc/jianwen/offline'
export const CHECKLIST_FILE = 'today.json'
export const META_FILE = 'meta.json'
export const AUDIO_FILE_PREFIX = 'continuous-'
export const OFFLINE_VERSION = 1
// 缓存新鲜度：今日清单半天内视为在线内容；离线回退允许更旧的缓存但会标记 stale。
export const CHECKLIST_TTL_MS = 12 * 60 * 60 * 1000
export const FALLBACK_MAX_AGE_DAYS = 7
export const TODAY_ARTICLE_LIMIT = 5
export const NETWORK_WIFI_ONLY = true
const DAY_MS = 24 * 60 * 60 * 1000
// 连续音轨是 64 kbps 单声道：1 秒约 8 KB，用来在按钮上提前告诉用户要下多大。
const AUDIO_BYTES_PER_SECOND = 8192

function pad2(value) {
  return String(value).padStart(2, '0')
}

// YYYY-MM-DD 且必须是真实存在的日历日（2026-02-30 这类不算）。
export function isDateKey(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  if (year < 1970 || month < 1 || month > 12 || day < 1 || day > 31) return false
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

export function normalizeDateKey(value) {
  return isDateKey(value) ? value : ''
}

// 设备本地日期。服务端日期按北京时间，跨零点时缓存目录按设备日期也能被“最近一天”兜住。
export function dateKey(value = Date.now()) {
  if (isDateKey(value)) return value
  const date = value instanceof Date ? value : new Date(value)
  const usable = date && Number.isFinite(date.getTime()) ? date : new Date()
  return `${usable.getFullYear()}-${pad2(usable.getMonth() + 1)}-${pad2(usable.getDate())}`
}

export function shiftDateKey(date, days) {
  const key = normalizeDateKey(date)
  if (!key) return ''
  const [year, month, day] = key.split('-').map(Number)
  const value = new Date(Date.UTC(year, month - 1, day) + Math.round(Number(days) || 0) * DAY_MS)
  return `${value.getUTCFullYear()}-${pad2(value.getUTCMonth() + 1)}-${pad2(value.getUTCDate())}`
}

// 连续音轨路径里带日期：/uploads/tts/2026-11-14/continuous-jianwen.mp3；离线路径同样适用。
export function dateFromAudioUrl(url) {
  const match = /(?:tts|offline)\/(\d{4}-\d{2}-\d{2})\//.exec(String(url || ''))
  return match && isDateKey(match[1]) ? match[1] : ''
}

function normalizeRoot(root) {
  return String(root || OFFLINE_ROOT).replace(/\/+$/, '')
}

export function offlineDateDir(date, root = OFFLINE_ROOT) {
  const key = normalizeDateKey(date)
  if (!key) throw new Error(`无效的离线缓存日期：${String(date)}`)
  return `${normalizeRoot(root)}/${key}`
}

export function offlineFilePath(date, fileName, root = OFFLINE_ROOT) {
  const name = String(fileName || '')
  if (!name || /[\\/]/.test(name) || name === '.' || name === '..') {
    throw new Error(`无效的离线缓存文件名：${name}`)
  }
  return `${offlineDateDir(date, root)}/${name}`
}

// 声音 id 来自后端，仍然做白名单收敛，避免拼出 ../ 之类的路径。
export function voiceAudioFileName(voice) {
  const safe = String(voice || '')
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, '')
    .slice(0, 32)
  return `${AUDIO_FILE_PREFIX}${safe || 'default'}.mp3`
}

const ARTICLE_FIELDS = [
  'id', 'articleId', 'topic', 'title', 'desc', 'sources', 'source', 'readTime', 'image',
  'publishedDate', 'updatedAt', 'updateLabel', 'relation', 'viewed', 'summary', 'sections', 'references'
]

function pickArticle(raw) {
  const article = {}
  for (const field of ARTICLE_FIELDS) {
    if (raw[field] !== undefined) article[field] = raw[field]
  }
  return article
}

function hasArticleId(item) {
  const id = item.id != null && item.id !== '' ? item.id : item.articleId
  return id != null && id !== ''
}

// 缓存只存渲染需要的字段，最多 5 篇；id/articleId 都没有的脏数据直接丢弃。
export function normalizeChecklist(raw) {
  const record = raw && typeof raw === 'object' ? raw : {}
  const articles = (Array.isArray(record.articles) ? record.articles : [])
    .filter(item => item && typeof item === 'object' && hasArticleId(item))
    .slice(0, TODAY_ARTICLE_LIMIT)
    .map(pickArticle)
  if (!articles.length) return null
  const banners = (Array.isArray(record.banners) ? record.banners : [])
    .filter(item => item && typeof item === 'object')
    .slice(0, 4)
    .map(item => Object.assign({}, item))
  const savedAt = Number(record.savedAt)
  return {
    date: normalizeDateKey(record.date),
    savedAt: Number.isFinite(savedAt) && savedAt > 0 ? savedAt : 0,
    articles,
    banners
  }
}

function normalizeAudioEntry(entry) {
  if (!entry || typeof entry !== 'object' || !entry.file) return null
  const size = Number(entry.size)
  const savedAt = Number(entry.savedAt)
  return {
    file: String(entry.file),
    size: Number.isFinite(size) && size > 0 ? Math.floor(size) : 0,
    savedAt: Number.isFinite(savedAt) && savedAt > 0 ? savedAt : 0,
    url: String(entry.url || '')
  }
}

export function normalizeMeta(raw) {
  const record = raw && typeof raw === 'object' ? raw : null
  if (!record) return null
  const date = normalizeDateKey(record.date)
  const updatedAt = Number(record.updatedAt)
  if (!date || !Number.isFinite(updatedAt) || updatedAt <= 0) return null
  const checklist = record.checklist && typeof record.checklist === 'object'
    ? {
        file: String(record.checklist.file || CHECKLIST_FILE),
        savedAt: Number(record.checklist.savedAt) > 0 ? Number(record.checklist.savedAt) : 0,
        count: Math.max(0, Math.floor(Number(record.checklist.count) || 0))
      }
    : null
  const audio = {}
  const rawAudio = record.audio && typeof record.audio === 'object' && !Array.isArray(record.audio) ? record.audio : {}
  for (const voice of Object.keys(rawAudio)) {
    const entry = normalizeAudioEntry(rawAudio[voice])
    if (entry) audio[voice] = entry
  }
  return {
    version: Number(record.version) > 0 ? Number(record.version) : OFFLINE_VERSION,
    date,
    updatedAt,
    checklist,
    audio
  }
}

// 元数据是否新鲜：日期对得上、更新时间在 TTL 内。时钟回拨（未来时间）一律判旧。
export function isMetaFresh(meta, { now = Date.now(), ttlMs = CHECKLIST_TTL_MS, date = '' } = {}) {
  const normalized = normalizeMeta(meta)
  if (!normalized) return false
  if (date) {
    const expected = normalizeDateKey(date)
    if (!expected || normalized.date !== expected) return false
  }
  const age = Number(now) - normalized.updatedAt
  return Number.isFinite(age) && age >= 0 && age <= ttlMs
}

export function isChecklistFresh(meta, { now = Date.now(), ttlMs = CHECKLIST_TTL_MS, date = '' } = {}) {
  const normalized = normalizeMeta(meta)
  if (!normalized || !normalized.checklist || normalized.checklist.count <= 0) return false
  if (!isMetaFresh(normalized, { now, ttlMs, date })) return false
  const savedAt = normalized.checklist.savedAt || normalized.updatedAt
  const age = Number(now) - savedAt
  return Number.isFinite(age) && age >= 0 && age <= ttlMs
}

// 离线时跨过零点也能读到“今天或之前最近一天”的缓存，而不是直接空页。
export function selectFallbackDate(dates, today = dateKey(), { maxAgeDays = FALLBACK_MAX_AGE_DAYS } = {}) {
  const current = normalizeDateKey(today)
  if (!current) return ''
  const candidates = [...new Set((Array.isArray(dates) ? dates : []).filter(isDateKey))]
    .filter(date => date <= current)
  const limit = Number(maxAgeDays)
  const cutoff = Number.isFinite(limit) && limit >= 0 ? shiftDateKey(current, -limit) : ''
  const usable = cutoff ? candidates.filter(date => date >= cutoff) : candidates
  return usable.length ? usable.sort()[usable.length - 1] : ''
}

// 清理计划是纯函数：不传 includeAll 时只删“早于 maxAgeDays”的目录，keepDates 永不删。
export function selectCleanupDates(dates, { keepDates = [], maxAgeDays = FALLBACK_MAX_AGE_DAYS, today = dateKey(), includeAll = false } = {}) {
  const current = normalizeDateKey(today)
  if (!current) return []
  const keep = new Set((Array.isArray(keepDates) ? keepDates : []).filter(isDateKey))
  const limit = Number(maxAgeDays)
  const cutoff = Number.isFinite(limit) && limit >= 0 ? shiftDateKey(current, -limit) : ''
  return (Array.isArray(dates) ? dates : [])
    .filter(isDateKey)
    .filter(date => !keep.has(date))
    .filter(date => (includeAll ? true : Boolean(cutoff) && date < cutoff))
}

// 离线回退选择：在线结果优先；在线为空/失败时用缓存，过期缓存默认不读，allowStale 时读并标 stale。
export function resolveTodayContent({ remote, cached, now = Date.now(), ttlMs = CHECKLIST_TTL_MS, date = '', allowStale = false } = {}) {
  const online = normalizeChecklist(remote)
  if (online) {
    return { source: 'remote', offline: false, stale: false, articles: online.articles, banners: online.banners, date: online.date, savedAt: 0 }
  }
  const offline = normalizeChecklist(cached)
  if (!offline) {
    return { source: 'none', offline: false, stale: false, articles: [], banners: [], date: '', savedAt: 0 }
  }
  const expected = normalizeDateKey(date)
  const sameDay = !expected || !offline.date || offline.date === expected
  const age = Number(now) - offline.savedAt
  const fresh = sameDay && offline.savedAt > 0 && Number.isFinite(age) && age >= 0 && age <= ttlMs
  if (!fresh && !allowStale) {
    return { source: 'none', offline: false, stale: false, articles: [], banners: [], date: '', savedAt: 0 }
  }
  return {
    source: 'cache',
    offline: true,
    stale: !fresh,
    articles: offline.articles,
    banners: offline.banners,
    date: offline.date,
    savedAt: offline.savedAt
  }
}

// 连续音轨：本地有就优先本地，没缓存时才走网络。
export function chooseAudioUrl(remoteUrl, localPath) {
  const local = typeof localPath === 'string' ? localPath.trim() : ''
  if (local) return { url: local, local: true }
  return { url: typeof remoteUrl === 'string' ? remoteUrl : '', local: false }
}

// 播放器吃的是原生文件路径：_doc/... 在 App 里转成绝对路径更稳；没有 plus 时原样返回（便于单测）。
export function resolveLocalPlayablePath(path) {
  const value = typeof path === 'string' ? path.trim() : ''
  if (!value) return ''
  try {
    if (typeof plus !== 'undefined' && plus && plus.io && typeof plus.io.convertLocalFileSystemURL === 'function') {
      const absolute = plus.io.convertLocalFileSystemURL(value)
      if (absolute) return absolute
    }
  } catch (error) {}
  return value
}

// 自动缓存只在 Wi-Fi 下发生；manual=true 代表用户显式触发，可以走移动网络（调用方自己确认流量）。
export function shouldDownload({ networkType = '', manual = false, wifiOnly = NETWORK_WIFI_ONLY } = {}) {
  if (manual) return true
  if (!wifiOnly) return true
  return String(networkType || '').toLowerCase() === 'wifi'
}

export function estimateAudioBytes(duration) {
  const seconds = Number(duration)
  if (!Number.isFinite(seconds) || seconds <= 0) return 0
  return Math.round(seconds * AUDIO_BYTES_PER_SECOND)
}

export function formatBytes(bytes) {
  const value = Number(bytes)
  if (!Number.isFinite(value) || value <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  const rounded = index === 0 || size >= 10 ? Math.round(size) : Math.round(size * 10) / 10
  return `${rounded} ${units[index]}`
}

export function summarizeUsage(entries) {
  const byDate = {}
  let totalBytes = 0
  let totalFiles = 0
  for (const entry of Array.isArray(entries) ? entries : []) {
    if (!entry || !isDateKey(entry.date)) continue
    const bytes = Math.max(0, Math.floor(Number(entry.bytes) || 0))
    const files = Math.max(0, Math.floor(Number(entry.files) || 0))
    byDate[entry.date] = { bytes, files }
    totalBytes += bytes
    totalFiles += files
  }
  return { totalBytes, totalFiles, byDate, label: formatBytes(totalBytes) }
}

// ---------------------------------------------------------------------------
// 平台层：App 端用 plus.io 落盘到 _doc，下载仍走 uni.downloadFile（与 app-updater 一致）。
// 所有函数都只在调用时判断全局对象，H5/Node 里 import 本文件不会碰 plus/uni。
// ---------------------------------------------------------------------------

function plusAvailable() {
  try {
    return typeof plus !== 'undefined' && !!plus && !!plus.io
  } catch (error) {
    return false
  }
}

function resolveEntry(url) {
  return new Promise((resolve, reject) => {
    plus.io.resolveLocalFileSystemURL(url, resolve, reject)
  })
}

function getDirectoryEntry(parent, name, create) {
  return new Promise((resolve, reject) => {
    parent.getDirectory(name, { create: !!create, exclusive: false }, resolve, reject)
  })
}

function getFileEntry(parent, name, create) {
  return new Promise((resolve, reject) => {
    parent.getFile(name, { create: !!create, exclusive: false }, resolve, reject)
  })
}

function splitPath(path) {
  const clean = String(path || '').replace(/^\/+|\/+$/g, '')
  const parts = clean.split('/').filter(Boolean)
  const root = parts.shift() || '_doc'
  return { root: `${root}/`, parts }
}

async function resolvePath(path, { create = false, asFile = false } = {}) {
  const { root, parts } = splitPath(path)
  if (!parts.length) throw new Error('空路径')
  let entry = await resolveEntry(root)
  for (let index = 0; index < parts.length; index += 1) {
    const last = index === parts.length - 1
    if (last && asFile) return getFileEntry(entry, parts[index], create)
    entry = await getDirectoryEntry(entry, parts[index], create)
  }
  return entry
}

function readEntries(directory) {
  // HTML5+ 的 readEntries 可能分批返回：读到空数组才算结束。
  return new Promise((resolve, reject) => {
    const reader = directory.createReader()
    const all = []
    const readNext = () => {
      reader.readEntries(entries => {
        const list = Array.isArray(entries) ? entries : []
        if (!list.length) {
          resolve(all)
          return
        }
        all.push(...list)
        readNext()
      }, reject)
    }
    readNext()
  })
}

async function readTextFile(path) {
  const fileEntry = await resolvePath(path, { asFile: true }).catch(() => null)
  if (!fileEntry) return null
  const file = await new Promise((resolve, reject) => fileEntry.file(resolve, reject))
  return new Promise((resolve, reject) => {
    const reader = new plus.io.FileReader()
    reader.onloadend = event => resolve(String((event && event.target && event.target.result) || ''))
    reader.onerror = () => reject(new Error('读取缓存文件失败'))
    reader.readAsText(file, 'utf-8')
  })
}

async function writeTextFile(path, text) {
  // 先删再建：plus FileWriter 写入不会自动截断，覆盖较短的元数据会留下旧尾巴。
  const existing = await resolvePath(path, { asFile: true }).catch(() => null)
  if (existing) await new Promise(resolve => existing.remove(resolve, () => resolve()))
  const fileEntry = await resolvePath(path, { create: true, asFile: true })
  await new Promise((resolve, reject) => {
    fileEntry.createWriter(writer => {
      writer.onwrite = () => resolve()
      writer.onerror = () => reject(new Error('写入缓存文件失败'))
      writer.write(String(text))
    }, reject)
  })
}

async function ensureDirectory(path) {
  await resolvePath(path, { create: true })
}

async function removeDirectory(path) {
  const entry = await resolvePath(path).catch(() => null)
  if (!entry) return false
  await new Promise(resolve => entry.removeRecursively(() => resolve(true), () => resolve(false)))
  return true
}

async function listDirectory(path) {
  const directory = await resolvePath(path).catch(() => null)
  if (!directory) return []
  const entries = await readEntries(directory)
  const result = []
  for (const entry of entries) {
    if (entry.isDirectory) {
      result.push({ name: entry.name, isDirectory: true, size: 0 })
      continue
    }
    const file = await new Promise(resolve => entry.file(resolve, () => resolve(null)))
    result.push({ name: entry.name, isDirectory: false, size: file ? Number(file.size) || 0 : 0 })
  }
  return result
}

async function fileExists(path) {
  const entry = await resolvePath(path, { asFile: true }).catch(() => null)
  return Boolean(entry)
}

function downloadFile(url) {
  return new Promise((resolve, reject) => {
    uni.downloadFile({
      url,
      success: resolve,
      fail: () => reject(new Error('下载失败'))
    })
  })
}

async function downloadToFile(url, targetPath) {
  const result = await downloadFile(url)
  const statusCode = Number(result && result.statusCode) || 0
  const tempFilePath = result && (result.tempFilePath || result.filePath)
  if (statusCode !== 200 || !tempFilePath) throw new Error('下载失败')
  const fileName = String(targetPath).split('/').pop()
  const directoryPath = String(targetPath).replace(/\/[^/]+$/, '')
  const directory = await resolvePath(directoryPath, { create: true })
  // 已存在同名文件时 copyTo 会失败，先删掉旧缓存。
  const existing = await resolvePath(targetPath, { asFile: true }).catch(() => null)
  if (existing) await new Promise(resolve => existing.remove(resolve, () => resolve()))
  const source = await new Promise((resolve, reject) => plus.io.resolveLocalFileSystemURL(tempFilePath, resolve, reject))
  const copied = await new Promise((resolve, reject) => source.copyTo(directory, fileName, resolve, reject))
  const file = await new Promise((resolve, reject) => copied.file(resolve, reject))
  return { path: targetPath, size: Number(file.size) || 0 }
}

function currentNetworkType() {
  return new Promise(resolve => {
    try {
      uni.getNetworkType({
        success: result => resolve(String((result && result.networkType) || '')),
        fail: () => resolve('')
      })
    } catch (error) {
      resolve('')
    }
  })
}

export function createAppPlatform() {
  return {
    supported: () => plusAvailable() && typeof uni !== 'undefined',
    readText: readTextFile,
    writeText: writeTextFile,
    ensureDir: ensureDirectory,
    removeDir: removeDirectory,
    listDir: listDirectory,
    exists: fileExists,
    download: downloadToFile,
    networkType: currentNetworkType
  }
}

// ---------------------------------------------------------------------------
// 缓存门面：页面只需要和这里交互；platform 可注入，测试用内存实现。
// ---------------------------------------------------------------------------

export function createOfflineCache({ platform, now = () => Date.now(), ttlMs = CHECKLIST_TTL_MS, root = OFFLINE_ROOT } = {}) {
  const io = platform || createAppPlatform()
  const currentTime = () => {
    const value = Number(now())
    return Number.isFinite(value) ? value : Date.now()
  }
  const supported = () => {
    try {
      return typeof io.supported === 'function' ? !!io.supported() : true
    } catch (error) {
      return false
    }
  }
  const currentDate = () => dateKey(currentTime())

  async function readMeta(date) {
    const key = normalizeDateKey(date)
    if (!supported() || !key) return null
    try {
      const text = await io.readText(offlineFilePath(key, META_FILE, root))
      if (!text) return null
      return normalizeMeta(JSON.parse(text))
    } catch (error) {
      return null
    }
  }

  async function writeMeta(meta) {
    const normalized = normalizeMeta(meta)
    if (!normalized) return false
    try {
      await io.writeText(offlineFilePath(normalized.date, META_FILE, root), JSON.stringify(normalized))
      return true
    } catch (error) {
      return false
    }
  }

  async function readChecklist(date) {
    const key = normalizeDateKey(date)
    if (!supported() || !key) return null
    try {
      const text = await io.readText(offlineFilePath(key, CHECKLIST_FILE, root))
      if (!text) return null
      const checklist = normalizeChecklist(JSON.parse(text))
      if (!checklist) return null
      const meta = await readMeta(key)
      return {
        date: key,
        meta,
        checklist,
        fresh: isChecklistFresh(meta, { now: currentTime(), ttlMs, date: key })
      }
    } catch (error) {
      return null
    }
  }

  async function listDates() {
    if (!supported()) return []
    try {
      const entries = await io.listDir(normalizeRoot(root))
      return (Array.isArray(entries) ? entries : [])
        .filter(entry => entry && entry.isDirectory && isDateKey(entry.name))
        .map(entry => entry.name)
        .sort()
    } catch (error) {
      return []
    }
  }

  async function readLatestChecklist({ today = currentDate(), maxAgeDays = FALLBACK_MAX_AGE_DAYS } = {}) {
    if (!supported()) return null
    const dates = await listDates()
    const date = selectFallbackDate(dates, today, { maxAgeDays })
    if (!date) return null
    const result = await readChecklist(date)
    return result ? Object.assign(result, { fallbackDate: date }) : null
  }

  async function saveChecklist({ date, articles, banners } = {}) {
    if (!supported()) return { status: 'unsupported' }
    const key = normalizeDateKey(date) || currentDate()
    const savedAt = currentTime()
    const checklist = normalizeChecklist({ date: key, savedAt, articles, banners })
    if (!checklist) return { status: 'empty' }
    try {
      await io.ensureDir(offlineDateDir(key, root))
      const payload = Object.assign({ version: OFFLINE_VERSION }, checklist, { date: key, savedAt })
      await io.writeText(offlineFilePath(key, CHECKLIST_FILE, root), JSON.stringify(payload))
      const existing = await readMeta(key)
      const meta = {
        version: OFFLINE_VERSION,
        date: key,
        updatedAt: savedAt,
        checklist: { file: CHECKLIST_FILE, savedAt, count: checklist.articles.length },
        audio: existing ? existing.audio : {}
      }
      await writeMeta(meta)
      return { status: 'saved', date: key, savedAt, count: checklist.articles.length }
    } catch (error) {
      return { status: 'failed', error }
    }
  }

  async function cachedAudioPath(date, voice) {
    const key = normalizeDateKey(date)
    if (!supported() || !key) return ''
    try {
      const meta = await readMeta(key)
      const entry = meta && meta.audio ? meta.audio[voice] : null
      const file = entry && entry.file ? entry.file : voiceAudioFileName(voice)
      const path = offlineFilePath(key, file, root)
      return await io.exists(path) ? path : ''
    } catch (error) {
      return ''
    }
  }

  async function cacheAudio({ date, voice, url, force = false } = {}) {
    if (!supported()) return { status: 'unsupported' }
    const key = normalizeDateKey(date)
    if (!key) return { status: 'failed', reason: 'invalid-date' }
    if (!url) return { status: 'failed', reason: 'empty-url' }
    const file = voiceAudioFileName(voice)
    const path = offlineFilePath(key, file, root)
    try {
      if (!force) {
        const existingPath = await cachedAudioPath(key, voice)
        if (existingPath) {
          const meta = await readMeta(key)
          const size = meta && meta.audio && meta.audio[voice] ? meta.audio[voice].size : 0
          return { status: 'exists', date: key, path: existingPath, size }
        }
      }
      await io.ensureDir(offlineDateDir(key, root))
      const downloaded = await io.download(url, path)
      const size = downloaded && downloaded.size > 0 ? Math.floor(downloaded.size) : 0
      const meta = await readMeta(key)
      const audio = meta ? Object.assign({}, meta.audio) : {}
      audio[voice] = { file, size, savedAt: currentTime(), url: String(url) }
      await writeMeta({
        version: OFFLINE_VERSION,
        date: key,
        updatedAt: currentTime(),
        checklist: meta ? meta.checklist : null,
        audio
      })
      return { status: 'cached', date: key, path, size, voice }
    } catch (error) {
      return { status: 'failed', error, date: key, voice }
    }
  }

  async function dirUsage(date) {
    const key = normalizeDateKey(date)
    if (!supported() || !key) return { date: key, bytes: 0, files: 0 }
    try {
      const entries = await io.listDir(offlineDateDir(key, root))
      let bytes = 0
      let files = 0
      for (const entry of Array.isArray(entries) ? entries : []) {
        if (!entry || entry.isDirectory) continue
        bytes += Math.max(0, Number(entry.size) || 0)
        files += 1
      }
      return { date: key, bytes, files }
    } catch (error) {
      return { date: key, bytes: 0, files: 0 }
    }
  }

  async function usage() {
    if (!supported()) return Object.assign(summarizeUsage([]), { status: 'unsupported' })
    const dates = await listDates()
    const entries = []
    for (const date of dates) entries.push(await dirUsage(date))
    return Object.assign(summarizeUsage(entries), { status: 'ok' })
  }

  async function removeDate(date) {
    const key = normalizeDateKey(date)
    if (!supported() || !key) return { status: 'skipped', date: key, freedBytes: 0, freedFiles: 0 }
    const before = await dirUsage(key)
    try {
      await io.removeDir(offlineDateDir(key, root))
      return { status: 'removed', date: key, freedBytes: before.bytes, freedFiles: before.files }
    } catch (error) {
      return { status: 'failed', date: key, freedBytes: 0, freedFiles: 0, error }
    }
  }

  async function cleanup({ keepDates = [], maxAgeDays = FALLBACK_MAX_AGE_DAYS, today = currentDate(), includeAll = false } = {}) {
    if (!supported()) return { status: 'unsupported', removedDates: [], freedBytes: 0, freedFiles: 0, freedLabel: '0 B' }
    const dates = await listDates()
    const targets = selectCleanupDates(dates, { keepDates, maxAgeDays, today, includeAll })
    const removedDates = []
    let freedBytes = 0
    let freedFiles = 0
    for (const date of targets) {
      const result = await removeDate(date)
      if (result.status !== 'removed') continue
      removedDates.push(date)
      freedBytes += result.freedBytes
      freedFiles += result.freedFiles
    }
    return { status: 'ok', removedDates, freedBytes, freedFiles, freedLabel: formatBytes(freedBytes) }
  }

  async function networkType() {
    try {
      if (!supported() || typeof io.networkType !== 'function') return ''
      return String((await io.networkType()) || '')
    } catch (error) {
      return ''
    }
  }

  return {
    supported,
    readMeta,
    readChecklist,
    readLatestChecklist,
    saveChecklist,
    listDates,
    cachedAudioPath,
    cacheAudio,
    usage,
    removeDate,
    cleanup,
    networkType
  }
}

let sharedCache = null

// 页面共用一份：避免每次调用都重新组装平台层。
export function getOfflineCache() {
  if (!sharedCache) sharedCache = createOfflineCache()
  return sharedCache
}
